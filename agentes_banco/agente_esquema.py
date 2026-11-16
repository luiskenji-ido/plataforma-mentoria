# -*- coding: utf-8 -*-
"""
AGENTE DE BANCO — ESQUEMA E ÍNDICES
Uso: python agentes_banco/agente_esquema.py
Compara o modelo (models.py) com o banco real, procura chaves estrangeiras sem índice (priorizando as que o código
usa em filtros e junções), índices redundantes, tabelas sem chave primária, registros órfãos, datas gravadas como texto
e a ausência de ferramenta de migração. Só lê o banco: os índices são criados pelo administrador na tela.
"""
import os
import re
import json
from collections import Counter

from base import AgenteBanco, RAIZ_PROJETO

COLUNAS_JSON = re.compile(r"preferencias|_json$|conteudo$|agentes_destino|lista_|modulos$", re.I)


def uso_no_codigo(db):
    """Uso real de (tabela, coluna) em consultas: filtros por modelo no código e relacionamentos um-para-muitos
    do SQLAlchemy (cada acesso a pai.filhos consulta a tabela filha pela chave estrangeira)."""
    tabela_do_modelo = {m.class_.__name__: m.local_table.name for m in db.Model.registry.mappers}
    uso = Counter()
    for nome in os.listdir(RAIZ_PROJETO):
        if not nome.endswith(".py"):
            continue
        texto = open(os.path.join(RAIZ_PROJETO, nome), encoding="utf-8", errors="ignore").read()
        for modelo, argumentos in re.findall(r"\b([A-Z]\w+)\.query(?:\.\w+\([^()]*\))*?\.filter_by\(([^)]*)\)", texto):
            if modelo in tabela_do_modelo:
                uso.update((tabela_do_modelo[modelo], c) for c in re.findall(r"(\w+)\s*=", argumentos))
        for modelo, coluna in re.findall(r"\b([A-Z]\w+)\.(\w+)\s*(?:==|!=|\.in_\(|\.is_\(|\.isnot\(|>=|<=|>|<)", texto):
            if modelo in tabela_do_modelo:
                uso[(tabela_do_modelo[modelo], coluna)] += 1
    for mapper in db.Model.registry.mappers:
        for rel in mapper.relationships:
            if rel.direction.name == "ONETOMANY":
                for _, remota in rel.local_remote_pairs:
                    if getattr(remota, "table", None) is not None:
                        uso[(remota.table.name, remota.name)] += 1
            elif rel.direction.name == "MANYTOMANY":
                # Tabela de associação: carregar pai.filhos filtra a associação pela coluna do lado do pai
                for _, coluna in rel.synchronize_pairs:
                    if getattr(coluna, "table", None) is not None:
                        uso[(coluna.table.name, coluna.name)] += 1
    return uso


class AgenteEsquema(AgenteBanco):
    chave = "esquema"
    nome = "Agente Esquema e Índices"
    especialidade = "modelagem, índices e integridade do esquema do banco"
    ROTEIRO = ["Modelo (models.py) × banco real: tabelas e colunas faltando ou sobrando",
               "Chaves estrangeiras sem índice, priorizadas pelo uso no código",
               "Índices redundantes e tabelas sem chave primária",
               "Registros órfãos, datas como texto, JSON em texto e ferramenta de migração",
               "Mudanças de esquema aprendidas com o Gerente de Banco de Dados"]

    def rodar(self):
        from app import app
        with app.app_context():
            from sqlalchemy import inspect
            from app import db
            self.db = db
            self.insp = inspect(db.engine)
            self.tabelas = set(self.insp.get_table_names())
            self.modelo_x_banco()
            self.indices()
            self.integridade_e_tipos()
            self.mudancas_aprendidas()
            self.regras_de_negocio_aprendidas()

    def modelo_x_banco(self):
        self.etapa("Modelo × banco real")
        modelo = self.db.metadata.tables
        faltando_tabela = sorted(t for t in modelo if t not in self.tabelas)
        sem_modelo = sorted(t for t in self.tabelas if t not in modelo and not t.startswith("sqlite_"))
        faltando_coluna, sobrando_coluna = [], []
        for nome, tabela in modelo.items():
            if nome not in self.tabelas:
                continue
            reais = {c["name"] for c in self.insp.get_columns(nome)}
            declaradas = {c.name for c in tabela.columns}
            faltando_coluna += [f"{nome}.{c}" for c in sorted(declaradas - reais)]
            sobrando_coluna += [f"{nome}.{c}" for c in sorted(reais - declaradas)]
        if faltando_tabela or faltando_coluna:
            self.achado("Modelo declara tabelas/colunas que não existem no banco", "Alta", "ESQ", "; ".join((faltando_tabela + faltando_coluna)[:12]),
                        "As telas que usam estes campos quebram com erro 500.",
                        "Rodar atualizar_estrutura_banco() (reinício do app) ou incluir o ALTER TABLE na lista colunas_novas do app.py.")
        else:
            self.ok(f"Modelo e banco alinhados ({len(modelo)} tabelas)")
        if sobrando_coluna or sem_modelo:
            self.achado(f"{len(sobrando_coluna) + len(sem_modelo)} coluna(s)/tabela(s) no banco sem uso no modelo", "Baixa", "ESQ",
                        "; ".join((sem_modelo + sobrando_coluna)[:12]),
                        "Sobras de versões antigas ocupam espaço e confundem quem mantém o banco.",
                        "Confirmar que não são usadas (nem em relatórios externos), fazer backup e removê-las numa migração.")

    def indices(self):
        self.etapa("Chaves estrangeiras sem índice e índices redundantes")
        import conhecimento
        uso = uso_no_codigo(self.db)
        # Varreduras vistas pelo Agente Consultas e Desempenho também contam como uso
        for item in conhecimento._estado("db_indices_sugeridos", []):
            if item.get("origem") == "consultas":
                for coluna in item.get("colunas", []):
                    uso[(item["tabela"], coluna)] += 1
        prioritarias, demais = [], []
        redundantes, sem_pk = [], []
        for tabela in sorted(self.tabelas):
            if tabela.startswith("sqlite_"):
                continue
            indices = self.insp.get_indexes(tabela)
            pk = self.insp.get_pk_constraint(tabela).get("constrained_columns") or []
            if not pk:
                sem_pk.append(tabela)
            primeiros = {tuple(i["column_names"][:1]) for i in indices if i["column_names"]} | ({(pk[0],)} if pk else set())
            primeiros |= {tuple(u["column_names"][:1]) for u in self.insp.get_unique_constraints(tabela)}
            for fk in self.insp.get_foreign_keys(tabela):
                coluna = fk["constrained_columns"][0]
                if (coluna,) in primeiros:
                    continue
                vezes = uso.get((tabela, coluna), 0)
                item = (vezes, tabela, coluna, fk["referred_table"])
                (prioritarias if vezes else demais).append(item)
            colunas_idx = [tuple(i["column_names"]) for i in indices if i["column_names"]]
            for a in colunas_idx:
                for b in colunas_idx:
                    if a != b and len(a) < len(b) and b[:len(a)] == a:
                        redundantes.append(f"{tabela}({', '.join(a)}) ⊂ ({', '.join(b)})")
        prioritarias.sort(reverse=True)
        if prioritarias:
            scripts = [f'CREATE INDEX IF NOT EXISTS "ix_{t}_{c}" ON "{t}" ("{c}");' for _, t, c, _ in prioritarias[:20]]
            self.achado(f"{len(prioritarias)} chave(s) estrangeira(s) usadas nas consultas sem índice", "Média", "IDX",
                        "; ".join(f"{t}.{c} → {r} ({n} uso(s))" for n, t, c, r in prioritarias[:12]),
                        "Filtros e junções por estas colunas varrem a tabela inteira; o custo cresce com o volume.",
                        "Criar os índices (botão 'Criar índices sugeridos' na tela, com backup antes) e rodar ANALYZE.",
                        ["https://www.sqlite.org/queryplanner.html", "https://www.sqlite.org/foreignkeys.html#fk_indexes"], "\n".join(scripts))
        else:
            self.ok("Chaves estrangeiras usadas nas consultas têm índice")
        if demais:
            self.achado(f"{len(demais)} chave(s) estrangeira(s) pouco usadas sem índice", "Informativa", "IDX",
                        ", ".join(f"{t}.{c}" for _, t, c, _ in demais[:20]),
                        "Colunas de auditoria (criado_por_id, revisado_por_id…) quase não aparecem em filtros.",
                        "Indexar só se passarem a ser usadas em filtros ou relatórios.")
        if redundantes:
            self.achado(f"{len(redundantes)} índice(s) redundante(s)", "Baixa", "IDX", "; ".join(redundantes[:8]),
                        "O índice menor é prefixo do maior: ocupa espaço e deixa as gravações mais lentas.", "Remover o índice menor (DROP INDEX), com backup antes.")
        if sem_pk:
            self.achado(f"{len(sem_pk)} tabela(s) sem chave primária", "Baixa", "ESQ", ", ".join(sem_pk[:10]),
                        "Tabelas de associação sem PK aceitam linhas duplicadas.", "Criar PK composta ou UNIQUE nas colunas da associação.")
        conhecimento._gravar_estado("db_indices_sugeridos",
                                    [i for i in conhecimento._estado("db_indices_sugeridos", []) if i.get("origem") != "esquema"]
                                    + [{"tabela": t, "colunas": [c], "motivo": f"chave estrangeira para {r} com {n} uso(s) em consultas", "origem": "esquema"}
                                       for n, t, c, r in prioritarias])
        self.db.session.commit()
        self.extras["fk_prioritarias"] = [{"tabela": t, "coluna": c, "referencia": r, "uso": n} for n, t, c, r in prioritarias]

    def integridade_e_tipos(self):
        self.etapa("Órfãos, tipos de dados e migrações")
        con = self.db.engine.raw_connection()
        try:
            orfaos = con.cursor().execute("PRAGMA foreign_key_check").fetchall() if self.db.engine.dialect.name == "sqlite" else []
        finally:
            con.close()
        if orfaos:
            por_tabela = Counter(f"{o[0]}→{o[2]}" for o in orfaos)
            self.achado(f"{len(orfaos)} registro(s) órfão(s) (apontam para linha que não existe)", "Média", "INT",
                        "; ".join(f"{k}: {v}" for k, v in por_tabela.most_common(10)),
                        "Exclusões antigas deixaram referências quebradas; podem causar erro 500 ou dados sumindo das telas.",
                        "Revisar caso a caso: apagar os órfãos ou recriar a linha referenciada (com backup antes).",
                        ["https://www.sqlite.org/pragma.html#pragma_foreign_key_check"],
                        "PRAGMA foreign_key_check;")
        else:
            self.ok("Nenhum registro órfão")
        datas_texto, json_texto = [], []
        for nome, tabela in self.db.metadata.tables.items():
            for coluna in tabela.columns:
                tipo = str(coluna.type).upper()
                if re.match(r"(data|dt)_", coluna.name) and ("VARCHAR" in tipo or "TEXT" in tipo or "STRING" in tipo):
                    datas_texto.append(f"{nome}.{coluna.name}")
                if COLUNAS_JSON.search(coluna.name) and ("TEXT" in tipo or "VARCHAR" in tipo):
                    json_texto.append(f"{nome}.{coluna.name}")
        if datas_texto:
            self.achado(f"{len(datas_texto)} data(s) gravada(s) como texto", "Baixa", "ESQ", ", ".join(datas_texto[:10]),
                        "Datas em texto não ordenam nem filtram corretamente por período.", "Migrar para DateTime (db.DateTime) convertendo os valores.")
        if json_texto:
            self.achado(f"{len(json_texto)} coluna(s) com JSON em texto", "Informativa", "ESQ", ", ".join(json_texto[:10]),
                        "Funciona bem no SQLite; no PostgreSQL prefira JSONB para consultar dentro do JSON.", "Manter; avaliar JSON/JSONB numa migração de banco.")
        migracoes = any(os.path.isdir(os.path.join(RAIZ_PROJETO, p)) for p in ("migrations", "alembic"))
        if not migracoes:
            self.achado("Esquema evolui sem ferramenta de migração", "Baixa", "ESQ", "app.py: atualizar_estrutura_banco() / colunas_novas",
                        "Os ALTER TABLE ficam numa lista no app.py, sem versão nem volta (rollback).",
                        "Adotar Flask-Migrate (Alembic): cada mudança vira uma migração versionada, com upgrade e downgrade.",
                        ["https://flask-migrate.readthedocs.io/", "https://alembic.sqlalchemy.org/"])

    def regras_de_negocio_aprendidas(self):
        """Regras ensinadas pelo Gerente de Funcionalidades: o banco também garante a faixa (CHECK) ou só a aplicação?"""
        import conhecimento_funcional as cf
        verificacoes = cf.verificacoes_para(self.aprendizados, "db_esquema")
        self.etapa("Regras de negócio aprendidas com o Gerente de Funcionalidades")
        if not verificacoes:
            self.log("Nenhuma regra de negócio ensinada ainda")
            return
        con = self.db.engine.raw_connection()
        try:
            for v in verificacoes:
                if v["tipo"] != "faixa_numerica":
                    continue
                sem_check, fora = [], []
                for tabela, colunas in v["colunas"].items():
                    if tabela not in self.tabelas:
                        continue
                    existentes = [c["name"] for c in self.insp.get_columns(tabela)]
                    ddl = (con.cursor().execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone() or [""])[0] or ""
                    for coluna in colunas:
                        if coluna not in existentes:
                            continue
                        if not re.search(r"CHECK\s*\([^)]*" + coluna, ddl, re.I):
                            sem_check.append(f"{tabela}.{coluna}")
                        n = con.cursor().execute('SELECT COUNT(*) FROM "' + tabela + '" WHERE "' + coluna + '" < ? OR "' + coluna + '" > ?',
                                                 (v["min"], v["max"])).fetchone()[0]
                        if n:
                            fora.append(f"{tabela}.{coluna}: {n}")
                if fora:
                    self.achado("Dados fora da faixa da regra de negócio", "Média", "INT", "; ".join(fora),
                                f"Regra aprendida em {v['codigo']}: {v['regra']}.", "Corrigir os registros (com backup antes).")
                if sem_check:
                    scripts = [f'-- {c}: CHECK ({c.split(".")[1]} BETWEEN {v["min"]} AND {v["max"]})' for c in sem_check[:12]]
                    self.achado(f"Regra {v['min']}–{v['max']} garantida só pela aplicação ({len(sem_check)} coluna(s))", "Informativa", "ESQ",
                                ", ".join(sem_check[:12]), f"Regra aprendida em {v['codigo']}: {v['regra']}. O banco aceitaria valores fora da faixa "
                                "vindos de importações, scripts ou rotas novas.",
                                "Na próxima migração (Flask-Migrate), criar as colunas com CHECK; no SQLite isso exige recriar a tabela.",
                                ["https://www.sqlite.org/lang_createtable.html#ckconst"], "\n".join(scripts))
                else:
                    self.ok(f"Regra {v['min']}–{v['max']} garantida também pelo banco ({v['codigo']})")
        finally:
            con.close()

    def mudancas_aprendidas(self):
        self.etapa("Mudanças de esquema aprendidas")
        mudancas = [json.loads(a.conteudo) | {"_codigo": a.codigo} for a in self.aprendizados_do_tipo("db_esquema")]
        if not mudancas:
            self.log("Nenhuma mudança de esquema desde a linha de base")
            return
        problemas = []
        for m in mudancas:
            for tabela in m.get("tabelas_novas", []):
                if tabela not in self.tabelas:
                    continue
                if not self.insp.get_pk_constraint(tabela).get("constrained_columns"):
                    problemas.append(f"{tabela}: sem chave primária ({m['_codigo']})")
                indexadas = {tuple(i["column_names"][:1]) for i in self.insp.get_indexes(tabela)}
                for fk in self.insp.get_foreign_keys(tabela):
                    if (fk["constrained_columns"][0],) not in indexadas:
                        problemas.append(f"{tabela}.{fk['constrained_columns'][0]}: FK nova sem índice ({m['_codigo']})")
        if problemas:
            self.achado(f"{len(problemas)} ponto(s) nas tabelas novas desde a última auditoria", "Baixa", "ESQ", "; ".join(problemas[:10]),
                        "Tabelas criadas depois da linha de base, aprendidas pelo Gerente de Banco de Dados.",
                        "Criar a chave primária e os índices das chaves estrangeiras já na criação da tabela.")
        else:
            self.ok(f"{len(mudancas)} mudança(s) de esquema aprendida(s) revisada(s) sem problemas")


if __name__ == "__main__":
    AgenteEsquema().executar()
