# -*- coding: utf-8 -*-
"""
CONFIGURAÇÃO DO BANCO DE DADOS (vários motores, sem mudar o código)
==================================================================
O endereço vem de DATABASE_URL (arquivo .env ou variável de ambiente). Sem ela, usa o SQLite de desenvolvimento
(instance/mentoria.db). Todo o acesso aos dados passa pelo SQLAlchemy, então trocar de motor é trocar o endereço:

  SQLite (padrão)   sqlite:///mentoria.db
  MySQL / MariaDB   mysql+pymysql://usuario:senha@localhost:3306/mentoria?charset=utf8mb4   (driver PyMySQL)
  PostgreSQL        postgresql+psycopg://usuario:senha@localhost:5432/mentoria              (pip install psycopg[binary])
  SQL Server        mssql+pyodbc://usuario:senha@servidor/mentoria?driver=ODBC+Driver+18+for+SQL+Server

Para trocar de motor numa instalação que já tem dados: copiar_banco.py (copia tudo de um endereço para outro).
As mudanças de estrutura do banco ficam em migrations/ (Flask-Migrate / Alembic): flask db upgrade.

A senha do banco nunca aparece em telas, relatórios ou logs: use endereco_sem_senha().
"""
import os

PADRAO = 'sqlite:///mentoria.db'


def endereco_do_banco():
    """DATABASE_URL normalizada (ver normalizar)."""
    return normalizar((os.environ.get('DATABASE_URL') or '').strip() or PADRAO)


def normalizar(url):
    """mysql:// e mariadb:// usam o PyMySQL e o conjunto de caracteres utf8mb4 (acentos e emojis); postgres:// vira postgresql://."""
    url = url.strip()
    if url.startswith('mysql://'):
        url = 'mysql+pymysql://' + url[len('mysql://'):]
    if url.startswith('mariadb://'):
        url = 'mysql+pymysql://' + url[len('mariadb://'):]
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if url.startswith('mysql') and 'charset=' not in url:
        url += ('&' if '?' in url else '?') + 'charset=utf8mb4'
    return url


def dialeto(url=None):
    """'sqlite', 'mysql', 'postgresql', 'mssql'..."""
    url = url or endereco_do_banco()
    return url.split(':', 1)[0].split('+', 1)[0]


def eh_sqlite(url=None):
    return dialeto(url) == 'sqlite'


def opcoes_do_motor(url):
    """Opções do pool de conexões. Servidores de banco (MySQL, PostgreSQL) fecham conexões paradas: o pool testa
    cada conexão antes de usar (pool_pre_ping) e renova as antigas (pool_recycle), evitando o erro
    "MySQL server has gone away" depois de uma madrugada sem acessos."""
    if eh_sqlite(url):
        return {}
    opcoes = {
        'pool_pre_ping': True,
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', '280')),
        'pool_size': int(os.environ.get('DB_POOL_SIZE', '5')),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', '10')),
        # espera máxima por uma conexão livre do pool (segundos): sem ela, um pico trava o pedido indefinidamente
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', '30')),
    }
    if dialeto(url) == 'mysql':
        # tempo-limite para abrir a conexão e para cada leitura/escrita (PyMySQL), em segundos
        opcoes['connect_args'] = {'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '10')),
                                  'read_timeout': int(os.environ.get('DB_READ_TIMEOUT', '60')),
                                  'write_timeout': int(os.environ.get('DB_WRITE_TIMEOUT', '60'))}
    return opcoes


def endereco_sem_senha(url=None):
    """Endereço para mostrar em telas e relatórios, com a senha trocada por ***."""
    from sqlalchemy.engine import make_url
    try:
        return make_url(url or endereco_do_banco()).render_as_string(hide_password=True)
    except Exception:
        return dialeto(url)


def caminho_banco_sqlite():
    """Arquivo do banco SQLite em uso (DBA, agentes e conhecimento do banco). Rodar dentro de um app_context."""
    from flask import current_app
    from models import db

    banco = db.engine.url.database or ''
    return banco if os.path.isabs(banco) else os.path.join(current_app.instance_path, 'mentoria.db')
