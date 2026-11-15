# -*- coding: utf-8 -*-
"""
AGENTE DE BANCO — MULTI-BANCO (SQLite, PostgreSQL, MySQL, SQL Server, MongoDB)
Uso: python agentes_banco/agente_portabilidade.py
Especialista nos bancos que a plataforma usa (SQLite) e nos que ela pode vir a usar. Mede a prontidão para migrar:
trechos presos ao SQLite, tipos sem tamanho, comparações de texto, configuração do endereço do banco e drivers.
Entrega, para cada banco de destino, os bloqueios, o esforço e o roteiro de migração. Quando precisa conhecer um banco
novo, o Gerente de Banco de Dados busca a documentação oficial (fica pendente de aprovação na Governança).
"""
import os
import re
import json
from importlib import metadata

from base import AgenteBanco, RAIZ_PROJETO

DRIVERS = {"postgresql": ("psycopg", "psycopg2", "psycopg2-binary"), "mysql": ("pymysql", "mysqlclient", "mysql-connector-python"),
           "mssql": ("pyodbc", "pymssql"), "mongodb": ("pymongo", "mongoengine")}
NOMES = {"sqlite": "SQLite", "postgresql": "PostgreSQL", "mysql": "MySQL", "mssql": "SQL Server", "mongodb": "MongoDB"}
ROTEIRO_MIGRACAO = {
    "postgresql": "1) DATABASE_URL por variável de ambiente; 2) Flask-Migrate (Alembic) com o esquema atual; 3) criar o banco no PostgreSQL "
                  "(PythonAnywhere tem PostgreSQL pago; ou serviço gerenciado); 4) copiar os dados (pgloader sqlite → postgres); "
                  "5) trocar .like() por .ilike() onde a busca deve ignorar maiúsculas; 6) rodar os agentes fim a fim e de banco.",
    "mysql": "1) DATABASE_URL por variável de ambiente (mysql+pymysql://); 2) dar tamanho a todos os String; 3) Flask-Migrate; "
             "4) charset utf8mb4 e collation *_ai_ci; 5) copiar os dados; 6) rodar os agentes. O PythonAnywhere oferece MySQL em todos os planos.",
    "mssql": "1) DATABASE_URL (mssql+pyodbc:// com ODBC Driver 18); 2) Flask-Migrate; 3) revisar ALTER TABLE (SQL Server usa 'ADD' sem 'COLUMN') "
             "e LIMIT/OFFSET (o SQLAlchemy traduz); 4) copiar os dados (SSMA para SQLite ou exportação CSV); 5) rodar os agentes.",
    "mongodb": "Não é troca de driver: o modelo é relacional (chaves estrangeiras e junções). Exige reescrever a camada de dados com um ODM "
               "(MongoEngine/Beanie), desnormalizar coleções e refazer relatórios. Recomendado só se houver um motivo forte (ex.: documentos sem esquema fixo).",
}


class AgentePortabilidade(AgenteBanco):
    chave = "portabilidade"
    nome = "Agente Multi-banco (SQLite, PostgreSQL, MySQL, SQL Server, MongoDB)"
    especialidade = "portabilidade e migração entre bancos de dados"
    ROTEIRO = ["Banco em uso, endereço do banco (DATABASE_URL) e drivers instalados",
               "Trechos presos ao SQLite (sqlite3, PRAGMA, SQL escrito à mão)",
               "Tipos e comparações que mudam de comportamento em outros bancos",
               "Prontidão e roteiro para PostgreSQL, MySQL, SQL Server e MongoDB",
               "Documentação oficial aprendida dos outros bancos"]

    def rodar(self):
        from app import app
        with app.app_context():
            from app import db
            self.db = db
            self.motor = db.engine.dialect.name
            self.banco_e_configuracao(app)
            self.trechos_especificos()
            self.tipos(db)
            self.prontidao()
            self.conhecimento_aprendido()

    def banco_e_configuracao(self, app):
        self.etapa("Banco em uso e configuração")
        self.ok(f"Banco em uso: {NOMES.get(self.motor, self.motor)}")
        app_py = open(os.path.join(RAIZ_PROJETO, "app.py"), encoding="utf-8").read()
        if re.search(r"SQLALCHEMY_DATABASE_URI'\]\s*=\s*'sqlite", app_py) and "DATABASE_URL" not in app_py:
            self.achado("Endereço do banco fixo no código", "Baixa", "POR", "app.py: SQLALCHEMY_DATABASE_URI",
                        "Trocar de banco (ou usar um banco de testes) exige editar o código.",
                        "Ler de variável de ambiente com padrão SQLite: os.environ.get('DATABASE_URL', 'sqlite:///mentoria.db').",
                        ["https://flask-sqlalchemy.readthedocs.io/en/stable/config/"],
                        "app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///mentoria.db')")
        instalados = {d.metadata["Name"].lower() for d in metadata.distributions() if d.metadata["Name"]}
        self.drivers = {m: [p for p in pacotes if p in instalados] for m, pacotes in DRIVERS.items()}
        presentes = {m: p for m, p in self.drivers.items() if p}
        self.log("Drivers de outros bancos: " + (", ".join(f"{NOMES[m]} ({', '.join(p)})" for m, p in presentes.items()) or "nenhum"))

    def trechos_especificos(self):
        self.etapa("Trechos presos ao SQLite")
        achados = {"sqlite3": [], "pragma": [], "sql_manual": [], "alter": 0, "like": []}
        for nome in os.listdir(RAIZ_PROJETO):
            if not nome.endswith(".py"):
                continue
            texto = open(os.path.join(RAIZ_PROJETO, nome), encoding="utf-8", errors="ignore").read()
            for i, linha in enumerate(texto.splitlines(), 1):
                if re.match(r"\s*import sqlite3|\s*from sqlite3", linha):
                    achados["sqlite3"].append(f"{nome}:{i}")
                if "PRAGMA" in linha and not linha.strip().startswith("#"):
                    achados["pragma"].append(f"{nome}:{i}")
                if re.search(r"exec_driver_sql\(|\btext\(\s*[\"']|\.execute\(\s*f?[\"'](SELECT|INSERT|UPDATE|DELETE)", linha):
                    achados["sql_manual"].append(f"{nome}:{i}")
                if re.search(r"\.like\(", linha):
                    achados["like"].append(f"{nome}:{i}")
            achados["alter"] += len(re.findall(r'"ALTER TABLE \w+ ADD COLUMN', texto))
        self.especificos = achados
        if achados["sqlite3"] or achados["pragma"]:
            self.achado(f"{len(achados['sqlite3']) + len(achados['pragma'])} trecho(s) usam recursos exclusivos do SQLite", "Informativa", "POR",
                        "; ".join((achados["sqlite3"] + achados["pragma"])[:12]),
                        "Backup por cópia de arquivo (sqlite3.backup) e PRAGMA não existem em PostgreSQL/MySQL/SQL Server.",
                        "Numa migração: trocar o backup por pg_dump/mysqldump/BACKUP DATABASE e isolar os PRAGMA num listener só para SQLite.")
        if achados["like"]:
            self.achado(f"{len(achados['like'])} busca(s) com .like()", "Informativa", "POR", "; ".join(achados["like"][:10]),
                        "No SQLite e no MySQL (collation padrão) LIKE ignora maiúsculas; no PostgreSQL não.",
                        "Usar .ilike() nas buscas que devem ignorar maiúsculas (o SQLAlchemy traduz para cada banco).")
        if achados["alter"]:
            self.achado(f"{achados['alter']} ALTER TABLE manuais na inicialização", "Baixa", "POR", "app.py: colunas_novas",
                        "Funcionam no SQLite; no SQL Server a sintaxe é 'ADD' (sem COLUMN) e tipos como BOOLEAN DEFAULT 1 mudam.",
                        "Migrar para Flask-Migrate (Alembic), que gera o DDL certo para cada banco.", ["https://alembic.sqlalchemy.org/"])

    def tipos(self, db):
        self.etapa("Tipos de dados")
        sem_tamanho = [f"{t}.{c.name}" for t, tabela in db.metadata.tables.items() for c in tabela.columns
                       if type(c.type).__name__ == "String" and not getattr(c.type, "length", None)]
        self.sem_tamanho = sem_tamanho
        if sem_tamanho:
            self.achado(f"{len(sem_tamanho)} coluna(s) String sem tamanho", "Informativa", "POR", ", ".join(sem_tamanho[:12]),
                        "MySQL exige tamanho em VARCHAR; o SQL Server usa VARCHAR(1) por padrão em alguns contextos.", "Definir db.String(N) ou usar db.Text.")
        else:
            self.ok("Todas as colunas String têm tamanho")
        datas = [f"{t}.{c.name}" for t, tabela in db.metadata.tables.items() for c in tabela.columns
                 if type(c.type).__name__ == "DateTime" and not getattr(c.type, "timezone", False)]
        self.achado(f"{len(datas)} coluna(s) DateTime sem fuso horário", "Informativa", "POR", ", ".join(datas[:8]),
                    "O app grava hora local e UTC misturados (datetime.now e datetime.utcnow); no PostgreSQL isso vira 'timestamp without time zone'.",
                    "Padronizar em UTC (DateTime(timezone=True)) e converter só na exibição.")

    def prontidao(self):
        self.etapa("Prontidão para cada banco de destino")
        bloqueios_base = len(self.especificos["sqlite3"]) + len(self.especificos["pragma"])
        notas = {}
        for destino in ("postgresql", "mysql", "mssql", "mongodb"):
            if destino == self.motor:
                continue
            nota = 100
            pontos = []
            if bloqueios_base:
                nota -= 15
                pontos.append(f"{bloqueios_base} trecho(s) exclusivos do SQLite (backup/PRAGMA)")
            if self.especificos["alter"]:
                nota -= 10
                pontos.append("ALTER TABLE manuais sem Alembic")
            if destino == "postgresql" and self.especificos["like"]:
                nota -= 5
                pontos.append(f"{len(self.especificos['like'])} .like() que passam a diferenciar maiúsculas")
            if destino in ("mysql", "mssql") and self.sem_tamanho:
                nota -= 10
                pontos.append(f"{len(self.sem_tamanho)} String sem tamanho")
            if destino == "mssql":
                nota -= 5
                pontos.append("driver ODBC no servidor")
            if destino == "mongodb":
                nota = 20
                pontos = ["modelo relacional com chaves estrangeiras e junções: exige reescrever a camada de dados"]
            if not self.drivers.get(destino):
                pontos.append(f"driver não instalado ({' ou '.join(DRIVERS[destino][:2])})")
            notas[destino] = max(0, nota)
            esforco = "baixo" if nota >= 80 else "médio" if nota >= 55 else "alto"
            self.achado(f"Prontidão para {NOMES[destino]}: {notas[destino]}/100 (esforço {esforco})", "Informativa", "POR", NOMES[destino],
                        "; ".join(pontos) or "nenhum bloqueio encontrado", ROTEIRO_MIGRACAO[destino])
        self.extras["prontidao"] = notas

    def conhecimento_aprendido(self):
        self.etapa("Documentação oficial aprendida dos outros bancos")
        refs = self.referencias_aprovadas()
        motores = [json.loads(a.conteudo) for a in self.aprendizados_do_tipo("db_motor")]
        if motores:
            ultima = motores[-1]
            self.achado(f"O banco mudou de {ultima['antes']['nome']} para {ultima['depois']['nome']}", "Média", "POR", "SQLALCHEMY_DATABASE_URI",
                        "Mudança aprendida pelo Gerente de Banco de Dados.", "Rodar todos os agentes (fim a fim, segurança e banco) no novo banco.")
        if refs:
            self.ok(f"{len(refs)} referência(s) oficial(is) aprovada(s) para consulta: " + "; ".join(r["titulo"] for r in refs[:4]))
        else:
            self.log("Nenhuma documentação de outros bancos aprovada ainda (use 'Aprender sobre outro banco' na tela)")


if __name__ == "__main__":
    AgentePortabilidade().executar()
