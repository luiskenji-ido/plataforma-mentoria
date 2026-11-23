# -*- coding: utf-8 -*-
"""
AGENTE DE BANCO — DBA: MANUTENÇÃO E LOGS
Uso: python agentes_banco/agente_dba.py
Rotina do DBA: integridade do arquivo, estatísticas do otimizador (ANALYZE), espaço livre (VACUUM), modo de diário
(journal/WAL), timeout de bloqueio, versão do SQLite, crescimento do banco (com previsão), tabelas de log/auditoria
(retenção) e arquivos de log no disco. As ações (ANALYZE, VACUUM) são feitas pelo administrador na tela, com backup antes.
"""
import os
import sqlite3
from datetime import datetime, timedelta

from base import AgenteBanco, RAIZ_PROJETO, tamanho_legivel

# Tabelas que crescem como log/auditoria (nome, coluna de data)
TABELAS_LOG = [("registro_backup", "data_registro"), ("alteracao_agendamento_backup", "data"), ("evento_aprendizado", "data"),
               ("historico_progresso", "data_registro"), ("historico_senha", "data_registro"), ("historico_perfil_acesso", "data"),
               ("historico_data_banca", "data_alteracao"), ("manutencao_banco_dados", "data"), ("notificacao", "data_criacao")]
PASTAS_LOG = ["Log_auditoria_backup", "instance/agentes_conhecimento/auditoria", "instance/backups/auditoria", "Agent Reports"]
LIMITE_LINHAS_LOG = 50_000
LIMITE_DIAS_LOG = 365


def _tamanho_pasta(caminho):
    total, arquivos = 0, 0
    for raiz, _, nomes in os.walk(caminho):
        for n in nomes:
            try:
                total += os.path.getsize(os.path.join(raiz, n))
                arquivos += 1
            except OSError:
                pass
    return total, arquivos


class AgenteDBA(AgenteBanco):
    chave = "dba"
    nome = "Agente DBA (Manutenção e Logs)"
    especialidade = "manutenção do banco, capacidade e logs"
    ROTEIRO = ["Integridade do arquivo do banco e versão do SQLite",
               "Estatísticas do otimizador (ANALYZE) e espaço livre (VACUUM)",
               "Configuração: modo de diário (WAL), timeout de bloqueio e arquivos temporários",
               "Crescimento do banco e previsão de capacidade",
               "Tabelas de log/auditoria (retenção) e arquivos de log no disco",
               "Histórico de manutenção (ações do DBA)",
               "Mudanças aprendidas: estatísticas do esquema novo e espaço previsto para os backups agendados"]

    def rodar(self):
        from app import app
        with app.app_context():
            from app import db
            import banco_manutencao
            from banco_config import caminho_banco_sqlite
            self.db, self.bm = db, banco_manutencao
            if db.engine.dialect.name != "sqlite":
                self.achado(f"Motor {db.engine.dialect.name}: rotina do DBA para SQLite não se aplica", "Informativa", "CFG", "SQLALCHEMY_DATABASE_URI",
                            "As verificações abaixo são específicas do SQLite.", "Usar as ferramentas de manutenção do motor em uso (ver o Agente Multi-banco).")
                return
            self.caminho = caminho_banco_sqlite()
            self.con = sqlite3.connect(f"file:{self.caminho}?mode=ro", uri=True)
            try:
                self.integridade()
                self.estatisticas_e_espaco()
                self.configuracao(app)
                self.capacidade()
                self.logs()
                self.historico_manutencao()
                self.mudancas_aprendidas()
            finally:
                self.con.close()

    def pragma(self, nome):
        return self.con.execute(f"PRAGMA {nome}").fetchone()[0]

    def integridade(self):
        self.etapa("Integridade e versão")
        resultado = [r[0] for r in self.con.execute("PRAGMA integrity_check").fetchall()]
        if resultado != ["ok"]:
            self.achado("Banco com páginas corrompidas", "Crítica", "INT", self.caminho, "; ".join(resultado[:5]),
                        "Restaurar o último backup íntegro (Manutenção (DB) › Restaurar) e investigar o disco.", ["https://www.sqlite.org/pragma.html#pragma_integrity_check"])
        else:
            self.ok("integrity_check: ok")
        versao = sqlite3.sqlite_version
        if tuple(int(x) for x in versao.split(".")[:2]) < (3, 35):
            self.achado(f"SQLite {versao} antigo", "Baixa", "CFG", "python/sqlite3", "Versões antes da 3.35 não têm DROP COLUMN nem RETURNING.",
                        "Atualizar o Python do ambiente.", ["https://www.sqlite.org/changes.html"])
        else:
            self.ok(f"SQLite {versao}")

    def estatisticas_e_espaco(self):
        self.etapa("Estatísticas do otimizador e espaço livre")
        tem_stat = self.con.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_stat1'").fetchone()
        ultima = self.bm.ultima("otimizar")
        if not tem_stat:
            self.achado("Estatísticas do otimizador nunca coletadas (ANALYZE)", "Média", "MAN", "sqlite_stat1 ausente",
                        "Sem estatísticas, o SQLite escolhe índices às cegas em consultas com vários filtros.",
                        "Botão 'Atualizar estatísticas' na tela (ANALYZE + PRAGMA optimize, com backup antes); repetir todo mês.",
                        ["https://www.sqlite.org/lang_analyze.html"], "ANALYZE;\nPRAGMA optimize;")
        elif ultima and ultima.data < datetime.now() - timedelta(days=30):
            self.achado(f"Estatísticas desatualizadas (último ANALYZE em {ultima.data:%d/%m/%Y})", "Baixa", "MAN", "sqlite_stat1",
                        "Os dados mudaram desde então.", "Rodar 'Atualizar estatísticas' na tela.", ["https://www.sqlite.org/lang_analyze.html"], "PRAGMA optimize;")
        else:
            self.ok("Estatísticas do otimizador presentes")
        paginas, livres, tamanho = self.pragma("page_count"), self.pragma("freelist_count"), self.pragma("page_size")
        proporcao = livres / paginas if paginas else 0
        recuperavel = livres * tamanho
        if proporcao > 0.2 and recuperavel > 1024 * 1024:
            self.achado(f"{proporcao:.0%} do arquivo é espaço livre ({tamanho_legivel(recuperavel)})", "Média" if proporcao > 0.4 else "Baixa", "MAN",
                        self.caminho, f"{livres} de {paginas} páginas livres.", "Botão 'Compactar (VACUUM)' na tela, fora do horário de uso, com backup antes.",
                        ["https://www.sqlite.org/lang_vacuum.html"], "VACUUM;")
        else:
            self.ok(f"Espaço livre no arquivo: {proporcao:.0%} ({tamanho_legivel(recuperavel)})")

    def configuracao(self, app):
        self.etapa("Configuração do banco")
        modo = self.pragma("journal_mode")
        if modo.lower() != "wal":
            self.achado(f"Modo de diário '{modo}' (WAL é melhor para leituras simultâneas)", "Informativa", "CFG", "PRAGMA journal_mode",
                        "No modo 'delete', uma gravação bloqueia as leituras; no WAL, leitores e escritor trabalham juntos.",
                        "Avaliar PRAGMA journal_mode=WAL num listener de conexão. No PythonAnywhere, confirmar antes na ajuda oficial "
                        "(WAL exige memória compartilhada e não funciona em sistemas de arquivos de rede).",
                        ["https://www.sqlite.org/wal.html", "https://help.pythonanywhere.com/"], "PRAGMA journal_mode=WAL;")
        else:
            self.ok("journal_mode=WAL")
        opcoes = app.config.get("SQLALCHEMY_ENGINE_OPTIONS") or {}
        if "timeout" not in str(opcoes.get("connect_args", {})):
            self.achado("Sem timeout de bloqueio configurado no SQLite", "Baixa", "CFG", "app.py: SQLALCHEMY_ENGINE_OPTIONS",
                        "Com acessos simultâneos (backup, tarefa agendada e usuários), surge 'database is locked' em vez de esperar.",
                        "app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'timeout': 15}} (segundos de espera pelo bloqueio).",
                        ["https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#database-locking-behavior-concurrency"])
        else:
            self.ok("Timeout de bloqueio configurado")
        pasta = os.path.dirname(self.caminho)
        sobras = [n for n in os.listdir(pasta) if n.endswith(("-journal", ".tmp")) and n.startswith(os.path.basename(self.caminho))]
        if sobras:
            self.achado("Arquivos temporários do banco esquecidos", "Baixa", "MAN", pasta, ", ".join(sobras),
                        "Sobra de uma gravação interrompida.", "Com o app parado, conferir a integridade e remover as sobras.")

    def capacidade(self):
        self.etapa("Crescimento e previsão de capacidade")
        import conhecimento_banco
        tamanho = os.path.getsize(self.caminho)
        historico = [h for h in conhecimento_banco.historico() if h.get("bytes")]
        maiores = []
        for (tabela,) in self.con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
            maiores.append((self.con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0], tabela))
        maiores.sort(reverse=True)
        previsao = ""
        if len(historico) >= 2:
            primeiro, ultimo = historico[0], historico[-1]
            dias = max(1, (datetime.fromisoformat(ultimo["dia"]) - datetime.fromisoformat(primeiro["dia"])).days)
            por_dia = (ultimo["bytes"] - primeiro["bytes"]) / dias
            previsao = f" Crescimento: {tamanho_legivel(max(0, por_dia))}/dia; em 1 ano ≈ {tamanho_legivel(tamanho + max(0, por_dia) * 365)}."
        else:
            previsao = " Previsão disponível após alguns dias de histórico (o Gerente guarda uma foto por dia)."
        self.achado(f"Banco com {tamanho_legivel(tamanho)}", "Informativa", "CAP", self.caminho,
                    "Maiores tabelas: " + ", ".join(f"{t} ({n})" for n, t in maiores[:6]) + "." + previsao,
                    "SQLite atende bem até alguns GB com poucos escritores simultâneos; acima disso, planejar PostgreSQL (ver Agente Multi-banco).")
        self.extras["maiores_tabelas"] = [{"tabela": t, "linhas": n} for n, t in maiores[:15]]
        if tamanho > 1024 ** 3:
            self.achado("Banco acima de 1 GB", "Média", "CAP", self.caminho, tamanho_legivel(tamanho),
                        "Avaliar arquivamento de dados antigos e a migração para PostgreSQL.")

    def logs(self):
        self.etapa("Tabelas de log/auditoria e arquivos de log")
        existentes = {r[0] for r in self.con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        inventario, crescendo = [], []
        for tabela, coluna in TABELAS_LOG:
            if tabela not in existentes:
                continue
            linhas = self.con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]
            try:
                mais_antigo = self.con.execute(f'SELECT MIN("{coluna}") FROM "{tabela}"').fetchone()[0]
            except sqlite3.OperationalError:
                mais_antigo = None
            inventario.append(f"{tabela}: {linhas} linha(s)" + (f", desde {str(mais_antigo)[:10]}" if mais_antigo else ""))
            idade = (datetime.now() - datetime.fromisoformat(str(mais_antigo)[:19])).days if mais_antigo else 0
            if linhas > LIMITE_LINHAS_LOG or idade > LIMITE_DIAS_LOG:
                crescendo.append(f"{tabela} ({linhas} linhas, {idade} dias)")
        self.achado(f"Inventário de logs no banco ({len(inventario)} tabela(s))", "Informativa", "LOG", "tabelas de histórico e auditoria",
                    "; ".join(inventario), "Definir a retenção de cada log com a gestão (ex.: 2 anos para auditoria, 1 ano para histórico).")
        if crescendo:
            self.achado(f"{len(crescendo)} tabela(s) de log sem política de retenção", "Baixa", "RET", "; ".join(crescendo),
                        f"Mais de {LIMITE_LINHAS_LOG} linhas ou registros com mais de {LIMITE_DIAS_LOG} dias.",
                        "Arquivar (exportar CSV) e apagar os registros antigos periodicamente, mantendo a trilha exigida pela LGPD.")
        else:
            self.ok("Tabelas de log dentro dos limites de retenção")
        pastas = []
        for rel in PASTAS_LOG:
            caminho = os.path.join(RAIZ_PROJETO, rel)
            if os.path.isdir(caminho):
                tamanho, arquivos = _tamanho_pasta(caminho)
                pastas.append((tamanho, rel, arquivos))
        if pastas:
            grandes = [p for p in pastas if p[0] > 200 * 1024 * 1024]
            self.achado("Arquivos de log e relatórios no disco", "Baixa" if grandes else "Informativa", "LOG",
                        "; ".join(f"{rel}: {tamanho_legivel(t)} em {n} arquivo(s)" for t, rel, n in sorted(pastas, reverse=True)),
                        "Relatórios de agentes e cópias de auditoria acumulam no disco.",
                        "Apagar relatórios antigos dos agentes (mais de 90 dias) e manter as cópias de auditoria pelo prazo definido.")
        app_py = open(os.path.join(RAIZ_PROJETO, "app.py"), encoding="utf-8").read()
        if "RotatingFileHandler" not in app_py and "TimedRotatingFileHandler" not in app_py:
            self.achado("Sem log de erros e de consultas lentas em arquivo", "Baixa", "LOG", "app.py (logging)",
                        "Erros e lentidão do banco só aparecem no log do servidor (no PythonAnywhere: error log), sem histórico próprio nem rotação.",
                        "Configurar logging com RotatingFileHandler (ex.: instance/logs/app.log, 5 MB × 5 arquivos) e um listener do SQLAlchemy "
                        "que registre consultas acima de 500 ms.",
                        ["https://docs.python.org/3/library/logging.handlers.html#rotatingfilehandler",
                         "https://docs.sqlalchemy.org/en/20/core/events.html#sqlalchemy.events.ConnectionEvents"],
                        "# app.py\nfrom logging.handlers import RotatingFileHandler\n"
                        "manipulador = RotatingFileHandler('instance/logs/app.log', maxBytes=5_000_000, backupCount=5)\n"
                        "app.logger.addHandler(manipulador)")

    def historico_manutencao(self):
        self.etapa("Histórico de manutenção")
        historico = self.bm.historico(10)
        if not historico:
            self.achado("Nenhuma manutenção registrada", "Informativa", "MAN", "manutencao_banco_dados",
                        "Ainda não houve ANALYZE, VACUUM ou criação de índices pela tela.", "Usar as ações do DBA na tela Agentes de Banco de Dados.")
            return
        falhas = [m for m in historico if m.status == "Falha"]
        self.ok(f"{len(historico)} manutenção(ões) recente(s); última: {historico[0].acao} em {historico[0].data:%d/%m/%Y %H:%M}")
        if falhas:
            self.achado(f"{len(falhas)} manutenção(ões) com falha", "Média", "MAN", "manutencao_banco_dados",
                        "; ".join(f"{m.acao} {m.data:%d/%m %H:%M}: {(m.detalhes or '')[:80]}" for m in falhas[:5]), "Ver o detalhe e repetir a ação.")

    # ------------------------------------------------------------------ aprendido com o Gerente de Banco de Dados
    def mudancas_aprendidas(self):
        """Usa o que o Gerente ensinou: estatísticas dos índices/tabelas novos e o espaço que os backups agendados vão ocupar."""
        import json
        import shutil
        self.etapa("Mudanças aprendidas: estatísticas do esquema novo e espaço dos backups")
        esquema = self.aprendizados_do_tipo("db_esquema")
        backups = self.aprendizados_do_tipo("db_backup")
        if not esquema and not backups:
            self.log("Nenhuma mudança de esquema ou de backup aprendida desde a linha de base")
            return
        if esquema:
            tem_stat = self.con.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_stat1'").fetchone()
            com_estatistica = {(t, i) for t, i in self.con.execute("SELECT tbl, idx FROM sqlite_stat1").fetchall()} if tem_stat else set()
            tabelas_com = {t for t, _ in com_estatistica}
            indices_com = {i for _, i in com_estatistica if i}
            sem = []
            for a in esquema:
                dados = json.loads(a.conteudo)
                for tabela, indices in dados.get("indices_novos", {}).items():
                    for descricao in indices:
                        nome = descricao.split("(", 1)[0]
                        existe = self.con.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (nome,)).fetchone()
                        linhas = self.con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0] if existe else 0
                        if existe and linhas and nome not in indices_com:
                            sem.append(f"índice {nome} ({a.codigo})")
                for tabela in dados.get("tabelas_novas", []):
                    existe = self.con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabela,)).fetchone()
                    if existe and tabela not in tabelas_com and self.con.execute(f'SELECT COUNT(*) FROM "{tabela}"').fetchone()[0]:
                        sem.append(f"tabela {tabela} ({a.codigo})")
            if sem:
                self.achado(f"{len(sem)} índice(s)/tabela(s) novo(s) sem estatísticas do otimizador", "Baixa", "MAN", "; ".join(sem[:12]),
                            "Mudanças de esquema aprendidas pelo Gerente de Banco de Dados depois do último ANALYZE: o otimizador ainda não "
                            "sabe quão seletivos são esses índices.",
                            "Rodar 'Atualizar estatísticas (ANALYZE + optimize)' na tela.", ["https://www.sqlite.org/lang_analyze.html"],
                            "ANALYZE;\nPRAGMA optimize;")
            else:
                self.ok(f"{len(esquema)} mudança(s) de esquema aprendida(s) já com estatísticas atualizadas")
        if backups:
            agendamentos = json.loads(backups[-1].conteudo).get("depois", {})
            ativos = [a for a in agendamentos.values() if a.get("status") == "Ativo"]
            tamanho = os.path.getsize(self.caminho)
            historico = [h for h in __import__("conhecimento_banco").historico() if h.get("bytes")]
            por_dia = 0
            if len(historico) >= 2:
                dias = max(1, (datetime.fromisoformat(historico[-1]["dia"]) - datetime.fromisoformat(historico[0]["dia"])).days)
                por_dia = max(0, (historico[-1]["bytes"] - historico[0]["bytes"]) / dias)
            daqui_1_ano = tamanho + por_dia * 365
            copias = sum(int(a.get("retencao") or 0) for a in ativos)
            previsto = daqui_1_ano * copias
            livre = shutil.disk_usage(os.path.dirname(self.caminho)).free
            evidencia = (f"{len(ativos)} agendamento(s) ativo(s) ({backups[-1].codigo}) retendo {copias} cópia(s); banco hoje {tamanho_legivel(tamanho)}, "
                         f"em 1 ano ≈ {tamanho_legivel(daqui_1_ano)}; backups em 1 ano ≈ {tamanho_legivel(previsto)}; livre {tamanho_legivel(livre)}.")
            if not ativos:
                self.achado("Agendamentos de backup aprendidos estão todos pausados ou removidos", "Média", "BKP", "agendamento_backup", evidencia,
                            "Sem backup automático, as ações do DBA (VACUUM, índices) são a única cópia recente. Reativar um agendamento.")
            elif previsto > livre * 0.5:
                self.achado("Backups agendados vão ocupar mais da metade do espaço livre em 1 ano", "Média", "CAP", "instance/backups", evidencia,
                            "Reduzir a retenção, arquivar cópias antigas fora do servidor ou ampliar o disco.")
            else:
                self.ok("Espaço para os backups agendados em 1 ano: " + evidencia)


if __name__ == "__main__":
    AgenteDBA().executar()
