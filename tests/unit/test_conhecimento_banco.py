"""Contagem de linhas do Gerente de Banco de Dados: as aspas precisam ser as do motor em uso."""

import sqlite3

from sqlalchemy.dialects import mysql, postgresql, sqlite

from conhecimento_banco import sql_contar_linhas


def test_mysql_usa_crase():
    # Com aspas duplas o MySQL devolvia erro 1064 na tarefa aprender_banco_de_dados
    assert sql_contar_linhas(mysql.dialect(), "acompanhamento") == "SELECT COUNT(*) FROM acompanhamento"
    assert sql_contar_linhas(mysql.dialect(), "order") == "SELECT COUNT(*) FROM `order`"
    assert sql_contar_linhas(mysql.dialect(), "a`b") == "SELECT COUNT(*) FROM `a``b`"


def test_sqlite_e_postgresql_usam_aspas_duplas():
    assert sql_contar_linhas(sqlite.dialect(), "order") == 'SELECT COUNT(*) FROM "order"'
    assert sql_contar_linhas(postgresql.dialect(), 'a"b') == 'SELECT COUNT(*) FROM "a""b"'


def test_consulta_roda_no_sqlite():
    con = sqlite3.connect(":memory:")
    con.execute('CREATE TABLE "order" (id INTEGER)')
    con.executemany('INSERT INTO "order" VALUES (?)', [(1,), (2,)])
    assert con.execute(sql_contar_linhas(sqlite.dialect(), "order")).fetchone()[0] == 2
