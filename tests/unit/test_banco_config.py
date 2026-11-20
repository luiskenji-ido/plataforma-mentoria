"""banco_config: endereço do banco vindo do ambiente, motores e opções do pool."""

import banco_config as bc


def test_sem_database_url_usa_o_sqlite_de_desenvolvimento():
    assert bc.endereco_do_banco() == "sqlite:///mentoria.db"


def test_database_url_vem_do_ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "  postgresql+psycopg://u:p@db:5432/mentoria  ")
    assert bc.endereco_do_banco() == "postgresql+psycopg://u:p@db:5432/mentoria"


def test_mysql_e_mariadb_usam_pymysql_e_utf8mb4():
    assert bc.normalizar("mysql://u:p@h/m") == "mysql+pymysql://u:p@h/m?charset=utf8mb4"
    assert bc.normalizar("mariadb://u:p@h/m?ssl=1") == "mysql+pymysql://u:p@h/m?ssl=1&charset=utf8mb4"


def test_mysql_com_charset_informado_nao_e_alterado():
    assert bc.normalizar("mysql+pymysql://u:p@h/m?charset=latin1") == "mysql+pymysql://u:p@h/m?charset=latin1"


def test_postgres_antigo_vira_postgresql():
    assert bc.normalizar("postgres://u:p@h/m") == "postgresql://u:p@h/m"


def test_dialeto_ignora_o_driver():
    assert bc.dialeto("mysql+pymysql://u:p@h/m") == "mysql"
    assert bc.dialeto("sqlite:///x.db") == "sqlite"
    assert bc.eh_sqlite("sqlite:///x.db")
    assert not bc.eh_sqlite("mssql+pyodbc://u:p@s/m")


def test_sqlite_nao_tem_opcoes_de_pool():
    assert bc.opcoes_do_motor("sqlite:///x.db") == {}


def test_servidor_de_banco_testa_e_renova_conexoes(monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "8")
    opcoes = bc.opcoes_do_motor("mysql+pymysql://u:p@h/m")
    assert opcoes == {"pool_pre_ping": True, "pool_recycle": 280, "pool_size": 8, "max_overflow": 10}


def test_endereco_sem_senha_nunca_mostra_a_senha():
    texto = bc.endereco_sem_senha("mysql+pymysql://mentoria:S3gred0!@db:3306/mentoria")
    assert "S3gred0" not in texto
    assert texto == "mysql+pymysql://mentoria:***@db:3306/mentoria"
