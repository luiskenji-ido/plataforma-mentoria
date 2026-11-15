# -*- coding: utf-8 -*-
"""
AGENTE DE BANCO — CONSULTAS E DESEMPENHO
Uso: python agentes_banco/agente_consultas.py
1. Análise do código: consultas dentro de laços (N+1), filtros feitos em Python sobre a tabela inteira, len(...all()),
   commit dentro de laço.
2. Perfil real das páginas: abre as páginas (GET, sem parâmetros) com usuários de teste pelo cliente de teste do Flask,
   captura cada consulta SQL (quantidade, tempo, repetições) e roda EXPLAIN QUERY PLAN nas consultas distintas para
   achar varreduras completas de tabela e ordenações sem índice. Só lê: nenhuma rota de ação é chamada.
"""
import os
import re
import ast
import time
from collections import defaultdict

from base import AgenteBanco, RAIZ_PROJETO

PERFIS_TESTE = ["administrador_ominitest@local.com", "aluno_ominitest@local.com", "gestorparceirob2b@local.com"]
IGNORAR = re.compile(r"agentes_ia$|agentes_seguranca$|agentes_banco$|exportar|baixar|arquivo|download|pdf|csv|json|google|oauth|autoriz|quadro|logout|sair|"
                     r"excluir|apagar|deletar|remover|executar|restaurar|limpar|desconectar|parar|iniciar|encerrar|aprovar|"
                     r"rejeitar|reabrir|cancelar|toggle|alternar|marcar|sincronizar|forcar|reset", re.I)
LIMITE_CONSULTAS = 40       # mais que isto numa página: provável N+1
LIMITE_REPETICAO = 8        # a mesma consulta repetida N vezes na mesma página
LIMITE_PAGINA_SEG = 1.0


def _normalizar(sql):
    return re.sub(r"\s+", " ", sql).strip()


def _chamadas_de_consulta(no):
    """True se o nó contém uma chamada que vai ao banco (.query, db.session.get/execute, .all/.first/.count)."""
    for sub in ast.walk(no):
        if isinstance(sub, ast.Attribute) and sub.attr in ("query",):
            return True
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            if sub.func.attr in ("get", "execute", "scalar") and isinstance(sub.func.value, ast.Attribute) and sub.func.value.attr == "session":
                return True
    return False


class AgenteConsultas(AgenteBanco):
    chave = "consultas"
    nome = "Agente Consultas e Desempenho"
    especialidade = "otimização das consultas e do uso do banco pelo código"
    ROTEIRO = ["Código: consultas dentro de laços (N+1), filtros em Python e contagens ineficientes",
               "Perfil real das páginas: número de consultas, tempo e repetições por página",
               "Plano de execução (EXPLAIN QUERY PLAN): varreduras completas e ordenações sem índice",
               "Sugestões de índices e de reescrita das consultas"]

    def rodar(self):
        self.codigo()
        self.perfil_das_paginas()

    # ------------------------------------------------------------------ código
    def codigo(self):
        self.etapa("Análise do código que acessa o banco")
        n1, filtro_python, contagem_len, commit_laco = [], [], [], []
        arquivos = 0
        for raiz, pastas, nomes in os.walk(RAIZ_PROJETO):
            pastas[:] = [p for p in pastas if not p.startswith((".", "venv")) and p not in (
                "__pycache__", "agentes_omnitest", "agentes_seguranca", "agentes_banco", "Agent Reports", "instance", "node_modules", "site-packages")]
            for nome in nomes:
                if not nome.endswith(".py"):
                    continue
                caminho = os.path.join(raiz, nome)
                rel = os.path.relpath(caminho, RAIZ_PROJETO).replace("\\", "/")
                try:
                    fonte = open(caminho, encoding="utf-8").read()
                    arvore = ast.parse(fonte)
                except (SyntaxError, UnicodeDecodeError):
                    continue
                arquivos += 1
                funcao_de = {}
                for f in ast.walk(arvore):
                    if isinstance(f, ast.FunctionDef):
                        for sub in ast.walk(f):
                            funcao_de.setdefault(id(sub), f.name)
                for no in ast.walk(arvore):
                    if isinstance(no, (ast.For, ast.While)):
                        for corpo in no.body:
                            if _chamadas_de_consulta(corpo):
                                n1.append(f"{rel}:{no.lineno} {funcao_de.get(id(no), '')}()")
                                break
                            if any(isinstance(s, ast.Call) and isinstance(s.func, ast.Attribute) and s.func.attr == "commit"
                                   for s in ast.walk(corpo)):
                                commit_laco.append(f"{rel}:{no.lineno} {funcao_de.get(id(no), '')}()")
                                break
                    if isinstance(no, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                        for gerador in no.generators:
                            iteravel = ast.get_source_segment(fonte, gerador.iter) or ""
                            if gerador.ifs and re.search(r"\.query\b.*\.all\(\)\s*$", iteravel):
                                filtro_python.append(f"{rel}:{no.lineno} {iteravel[:70]}")
                            elif _chamadas_de_consulta(getattr(no, "elt", None) or getattr(no, "value")):
                                n1.append(f"{rel}:{no.lineno} {funcao_de.get(id(no), '')}() (compreensão)")
                    if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and no.func.id == "len" and no.args:
                        trecho = ast.get_source_segment(fonte, no.args[0]) or ""
                        if re.search(r"\.query\b.*\.all\(\)$", trecho):
                            contagem_len.append(f"{rel}:{no.lineno}")
        self.ok(f"{arquivos} arquivo(s) Python analisado(s)")
        n1 = sorted(set(n1))
        if n1:
            self.achado(f"{len(n1)} laço(s) que consultam o banco a cada volta (padrão N+1)", "Média", "DES", "; ".join(n1[:12]),
                        "Cada volta do laço faz uma ou mais consultas; com mais dados, a página fica proporcionalmente mais lenta.",
                        "Buscar tudo de uma vez antes do laço: joinedload/selectinload nos relacionamentos, Model.id.in_(lista) "
                        "ou um dicionário montado com uma única consulta.",
                        ["https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html"])
        else:
            self.ok("Nenhum laço com consulta ao banco")
        if filtro_python:
            self.achado(f"{len(filtro_python)} filtro(s) feito(s) em Python sobre a tabela inteira", "Média", "DES", "; ".join(filtro_python[:10]),
                        "Lê todas as linhas da tabela para filtrar na memória (o banco faria isso com índice).",
                        "Levar a condição para o .filter()/.filter_by() da consulta.",
                        ["https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html"])
        if contagem_len:
            self.achado(f"{len(contagem_len)} contagem(ns) com len(consulta.all())", "Baixa", "DES", "; ".join(contagem_len[:10]),
                        "Carrega todos os objetos só para contar.", "Usar consulta.count() ou db.session.query(func.count(...)).scalar().")
        if commit_laco:
            self.achado(f"{len(commit_laco)} laço(s) com commit a cada volta", "Baixa", "DES", "; ".join(sorted(set(commit_laco))[:10]),
                        "Cada commit grava o arquivo do SQLite em disco; em lote é muito mais rápido.",
                        "Fazer um único db.session.commit() depois do laço (ou a cada N itens).")
        self.extras["codigo"] = {"n1": n1[:50], "filtro_python": filtro_python[:30], "len_all": contagem_len[:30]}

    # ------------------------------------------------------------------ perfil das páginas
    def perfil_das_paginas(self):
        self.etapa("Perfil real das páginas (consultas, tempo e plano de execução)")
        from datetime import datetime as _dt
        from sqlalchemy import event
        import app as modulo_app
        from app import app, db
        from models import Usuario
        app.config["TESTING"] = True
        modulo_app._ULTIMA_VERIFICACAO_BACKUP[0] = _dt.now()  # não dispara backups agendados durante a medição
        capturadas = []

        def antes(con, cursor, sql, parametros, contexto, varios):
            contexto._inicio_consulta = time.perf_counter()

        def depois(con, cursor, sql, parametros, contexto, varios):
            capturadas.append((sql, parametros, time.perf_counter() - contexto._inicio_consulta))

        with app.app_context():
            motor = db.engine
            usuarios = {e: u.get_id() for e in PERFIS_TESTE if (u := Usuario.query.filter_by(email=e, status="Ativo").first())}
            regras = [r for r in app.url_map.iter_rules() if "GET" in r.methods and not r.arguments and r.endpoint != "static"
                      and not IGNORAR.search(r.endpoint) and not IGNORAR.search(r.rule)]
        if not usuarios:
            self.achado("Perfil das páginas não realizado", "Informativa", "DES", "usuários de teste",
                        "Nenhum usuário de teste ativo (*_ominitest@local.com).", "Rodar os agentes fim a fim uma vez para criar os usuários de teste.")
            return
        event.listen(motor, "before_cursor_execute", antes)
        event.listen(motor, "after_cursor_execute", depois)
        paginas = []
        try:
            for email, uid in usuarios.items():
                cliente = app.test_client()
                with cliente.session_transaction() as sessao:
                    sessao["_user_id"], sessao["_fresh"] = uid, True
                for regra in regras:
                    capturadas.clear()
                    inicio = time.perf_counter()
                    try:
                        resposta = cliente.get(regra.rule)
                    except Exception as e:
                        self.log(f"{regra.rule}: erro {e.__class__.__name__}")
                        continue
                    tempo = time.perf_counter() - inicio
                    if resposta.status_code != 200:
                        continue
                    paginas.append({"perfil": email.split("@")[0].replace("_ominitest", ""), "rota": regra.rule, "consultas": len(capturadas),
                                    "tempo": tempo, "tempo_sql": sum(c[2] for c in capturadas), "sql": list(capturadas)})
                self.log(f"{email.split('@')[0]}: {sum(1 for p in paginas if p['perfil'] in email)} página(s) medidas")
        finally:
            event.remove(motor, "before_cursor_execute", antes)
            event.remove(motor, "after_cursor_execute", depois)
        if not paginas:
            self.log("Nenhuma página medida")
            return
        self.ok(f"{len(paginas)} página(s) medidas, {sum(p['consultas'] for p in paginas)} consultas capturadas")

        # Muitas consultas e repetição (N+1 em tempo de execução)
        pesadas, repetidas = [], []
        for p in paginas:
            if p["consultas"] > LIMITE_CONSULTAS:
                pesadas.append(f"{p['rota']} ({p['perfil']}): {p['consultas']} consultas")
            vezes = defaultdict(int)
            for sql, _, _ in p["sql"]:
                vezes[_normalizar(sql)] += 1
            pior = max(vezes.items(), key=lambda x: x[1])
            if pior[1] >= LIMITE_REPETICAO:
                repetidas.append(f"{p['rota']} ({p['perfil']}): {pior[1]}× \"{pior[0][:90]}\"")
        if pesadas:
            self.achado(f"{len(pesadas)} página(s) com mais de {LIMITE_CONSULTAS} consultas", "Média", "DES", "; ".join(sorted(set(pesadas))[:10]),
                        "Muitas idas ao banco por página: o tempo cresce com o volume de dados.",
                        "Carregar os relacionamentos com selectinload/joinedload e agregar no SQL (func.count, group_by).")
        else:
            self.ok(f"Todas as páginas com até {LIMITE_CONSULTAS} consultas")
        if repetidas:
            self.achado(f"{len(repetidas)} página(s) repetem a mesma consulta (N+1 em execução)", "Média", "DES", "; ".join(repetidas[:8]),
                        "A mesma consulta com parâmetros diferentes roda muitas vezes na mesma página.",
                        "Trocar por uma consulta com IN (...) ou por eager loading do relacionamento.",
                        ["https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html#selectin-eager-loading"])
        lentas = sorted([p for p in paginas if p["tempo"] > LIMITE_PAGINA_SEG], key=lambda p: -p["tempo"])
        if lentas:
            self.achado(f"{len(lentas)} página(s) acima de {LIMITE_PAGINA_SEG:.0f} s", "Média", "DES",
                        "; ".join(f"{p['rota']} ({p['perfil']}): {p['tempo']:.2f} s, SQL {p['tempo_sql']:.2f} s" for p in lentas[:8]),
                        "Páginas lentas no servidor de teste tendem a ficar piores em produção.",
                        "Ver quanto do tempo é SQL (acima) e aplicar os índices e o eager loading sugeridos.")
        top = sorted(paginas, key=lambda p: -p["tempo"])[:8]
        self.achado("Páginas mais pesadas (referência para acompanhar)", "Informativa", "DES",
                    "; ".join(f"{p['rota']} ({p['perfil']}): {p['consultas']} consultas, {p['tempo'] * 1000:.0f} ms" for p in top),
                    f"{len(paginas)} página(s) medidas pelo cliente de teste do Flask.", "Comparar estes números a cada auditoria.")
        self.extras["paginas"] = [{k: p[k] for k in ("perfil", "rota", "consultas", "tempo", "tempo_sql")} for p in paginas]
        self.plano_de_execucao(paginas)

    def plano_de_execucao(self, paginas):
        """EXPLAIN QUERY PLAN de cada SELECT distinto: varredura completa (SCAN) e ORDER BY sem índice."""
        from app import app, db
        import conhecimento
        distintas = {}
        for p in paginas:
            for sql, parametros, tempo in p["sql"]:
                if sql.lstrip().upper().startswith("SELECT"):
                    chave = _normalizar(sql)
                    item = distintas.setdefault(chave, {"sql": sql, "parametros": parametros, "vezes": 0, "tempo": 0.0, "rotas": set()})
                    item["vezes"] += 1
                    item["tempo"] += tempo
                    item["rotas"].add(p["rota"])
        varreduras, ordenacoes, sugestoes = [], [], {}
        with app.app_context():
            linhas_por_tabela = {}
            con = db.engine.raw_connection()
            try:
                cur = con.cursor()
                for chave, item in distintas.items():
                    try:
                        plano = [r[-1] for r in cur.execute("EXPLAIN QUERY PLAN " + item["sql"], item["parametros"] or ()).fetchall()]
                    except Exception:
                        continue
                    for passo in plano:
                        m = re.match(r"SCAN (\w+)(?: AS \w+)?$", passo.strip())
                        if m and m.group(1).startswith("sqlite_"):
                            continue  # catálogo interno do SQLite (inspeção do esquema), não é tabela da aplicação
                        if m and "WHERE" in item["sql"].upper():
                            tabela = m.group(1)
                            if tabela not in linhas_por_tabela:
                                try:
                                    linhas_por_tabela[tabela] = cur.execute('SELECT COUNT(*) FROM "' + tabela + '"').fetchone()[0]
                                except Exception:
                                    linhas_por_tabela[tabela] = 0
                            onde = item["sql"].upper().split("WHERE", 1)[1]
                            colunas = re.findall(rf'\b{tabela.upper()}\.(\w+)\s*(?:=|IN\b|>|<|IS\b)', onde)
                            varreduras.append((item["vezes"], tabela, colunas, ", ".join(sorted(item["rotas"]))[:120]))
                            chave_primaria = {r[1].lower() for r in cur.execute('PRAGMA table_info("' + tabela + '")').fetchall() if r[5]}
                            for coluna in [c for c in colunas if c.lower() not in chave_primaria][:1]:
                                sugestoes[(tabela, coluna.lower())] = f"consulta varre {tabela} inteira ({item['vezes']}× nas páginas medidas)"
                        if "USE TEMP B-TREE FOR ORDER BY" in passo:
                            ordenacoes.append(f"{item['vezes']}× {chave[:110]}")
            finally:
                con.close()
            # Guarda as sugestões para o Esquema e para a ação "Criar índices sugeridos" da tela
            existentes = [i for i in conhecimento._estado("db_indices_sugeridos", []) if i.get("origem") != "consultas"]
            conhecimento._gravar_estado("db_indices_sugeridos", existentes + [{"tabela": t, "colunas": [c], "motivo": m, "origem": "consultas"}
                                                                               for (t, c), m in sugestoes.items()])
            db.session.commit()
        self.ok(f"{len(distintas)} consulta(s) distinta(s) com plano de execução analisado")
        if varreduras:
            varreduras.sort(reverse=True)
            scripts = [f'CREATE INDEX IF NOT EXISTS "ix_{t}_{c}" ON "{t}" ("{c}");' for (t, c) in sorted(sugestoes)]
            self.achado(f"{len(sugestoes) or len(varreduras)} varredura(s) completa(s) de tabela com filtro (sem índice)", "Média", "IDX",
                        "; ".join(f"{t} por {', '.join(c[:2]).lower() or '—'} ({v}×) em {r}" for v, t, c, r in varreduras[:8]),
                        "O SQLite lê a tabela inteira para achar poucas linhas; o custo cresce com o volume.",
                        "Criar os índices sugeridos (botão 'Criar índices sugeridos' na tela, com backup antes) e rodar ANALYZE.",
                        ["https://www.sqlite.org/queryplanner.html", "https://www.sqlite.org/eqp.html"], "\n".join(scripts[:15]))
        else:
            self.ok("Nenhuma consulta com filtro varre a tabela inteira")
        if ordenacoes:
            self.achado(f"{len(ordenacoes)} consulta(s) ordenam sem índice (TEMP B-TREE)", "Baixa", "IDX", "; ".join(ordenacoes[:6]),
                        "A ordenação é feita em memória a cada execução.", "Avaliar índice composto (filtro, coluna do ORDER BY) nas mais usadas.",
                        ["https://www.sqlite.org/queryplanner.html#sorting"])
        self.extras["indices_sugeridos"] = [{"tabela": t, "coluna": c, "motivo": m} for (t, c), m in sorted(sugestoes.items())]


if __name__ == "__main__":
    AgenteConsultas().executar()
