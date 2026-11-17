# -*- coding: utf-8 -*-
"""
COPIAR O BANCO DE DADOS DE UM MOTOR PARA OUTRO (SQLite → MySQL, MySQL → SQLite, → PostgreSQL...)
===============================================================================================
Copia todas as tabelas da plataforma de um endereço de banco para outro, pelo SQLAlchemy (sem SQL específico de
um motor). Usos:
  - levar uma instalação SQLite para o MySQL do servidor;
  - criar uma cópia SQLite do banco principal (o Agente Orquestrador testa as correções numa cópia);
  - migrar no futuro para PostgreSQL ou SQL Server.

Linha de comando (no servidor, com o ambiente virtual ativo):
  python copiar_banco.py --de sqlite:////caminho/instance/mentoria.db --para "mysql+pymysql://usuario:senha@localhost/mentoria"
  python copiar_banco.py --de sqlite:///mentoria.db --para "$DATABASE_URL" --substituir   (apaga os dados do destino antes)

Como funciona:
1. O destino recebe a estrutura completa (as mesmas tabelas de models.py) e fica marcado na versão atual das
   migrações (tabela alembic_version), pronto para o "flask db upgrade" das próximas versões.
2. O destino precisa estar vazio; com --substituir, os dados dele são apagados antes (nada é apagado na origem).
3. Cada tabela é copiada em lotes, na ordem das chaves estrangeiras (no MySQL elas ficam desligadas durante a carga).
   Colunas que só existem de um lado são ignoradas. No PostgreSQL, as sequências dos ids são acertadas no fim.
4. No fim, confere a quantidade de linhas de cada tabela nos dois lados.

As senhas dos endereços nunca são impressas. Os arquivos enviados (uploads/) não ficam no banco: copie a pasta junto.
"""
import argparse
import os
import sys

from sqlalchemy import create_engine, inspect, select, text, func

LOTE = 1000


PASTA_INSTANCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')


def _motor(url):
    """Motor do SQLAlchemy. Caminho relativo do SQLite (sqlite:///mentoria.db) fica na pasta instance/, como no app."""
    import banco_config
    url = banco_config.normalizar(url)
    if url.startswith('sqlite:///') and not url.startswith('sqlite:////') and ':memory:' not in url:
        caminho = url[len('sqlite:///'):]
        if not os.path.isabs(caminho):
            url = 'sqlite:///' + os.path.join(PASTA_INSTANCE, caminho).replace('\\', '/')
    return create_engine(url, **banco_config.opcoes_do_motor(url)), url


def _versao_das_migracoes():
    """Revisão mais nova de migrations/ (para marcar o destino)."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
        pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')
        configuracao = Config()
        configuracao.set_main_option('script_location', pasta)
        return ScriptDirectory.from_config(configuracao).get_current_head()
    except Exception:
        return None


def _desligar_chaves(conexao, dialeto, tabelas=()):
    """Sem conferência de chaves estrangeiras durante a carga (as tabelas vêm na ordem das dependências, mas há
    referências circulares e para a própria tabela)."""
    if dialeto in ('mysql', 'mariadb'):
        conexao.execute(text('SET FOREIGN_KEY_CHECKS=0'))
    elif dialeto == 'sqlite':
        conexao.execute(text('PRAGMA foreign_keys=OFF'))
    elif dialeto == 'postgresql':
        # Só o dono com permissão de superusuário pode; sem ela, vale a ordem das dependências
        try:
            with conexao.begin_nested():
                conexao.execute(text('SET LOCAL session_replication_role = replica'))
        except Exception:
            pass
    elif dialeto == 'mssql':
        for tabela in tabelas:
            conexao.execute(text(f'ALTER TABLE [{tabela.name}] NOCHECK CONSTRAINT ALL'))


def _religar_chaves(conexao, dialeto, tabelas=()):
    if dialeto in ('mysql', 'mariadb'):
        conexao.execute(text('SET FOREIGN_KEY_CHECKS=1'))
    elif dialeto == 'mssql':
        for tabela in tabelas:
            conexao.execute(text(f'ALTER TABLE [{tabela.name}] WITH CHECK CHECK CONSTRAINT ALL'))


def _com_identidade(tabela):
    """SQL Server: tabela com coluna IDENTITY (id automático) precisa de IDENTITY_INSERT para receber os ids copiados."""
    return 'id' in tabela.c and tabela.c.id.primary_key and getattr(tabela.c.id, 'autoincrement', True) is not False


def _acertar_sequencias(conexao, dialeto, tabelas):
    """PostgreSQL: o próximo id de cada tabela continua depois do maior id copiado."""
    if dialeto != 'postgresql':
        return
    for tabela in tabelas:
        if 'id' in tabela.c and getattr(tabela.c.id, 'autoincrement', False) is not False:
            conexao.execute(text(f"SELECT setval(pg_get_serial_sequence('{tabela.name}', 'id'), "
                                 f"COALESCE((SELECT MAX(id) FROM {tabela.name}), 0) + 1, false)"))


def copiar(origem_url, destino_url, substituir=False, avisar=print):
    """Copia tudo de origem_url para destino_url. Devolve {tabela: linhas copiadas}. Levanta ValueError se o destino
    já tiver dados e substituir=False."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from models import db
    import banco_config
    metadados = db.metadata
    origem, origem_url = _motor(origem_url)
    destino, destino_url = _motor(destino_url)
    dialeto = destino.dialect.name
    avisar(f'Origem:  {banco_config.endereco_sem_senha(origem_url)}')
    avisar(f'Destino: {banco_config.endereco_sem_senha(destino_url)}')

    metadados.create_all(destino)  # estrutura completa no destino (não mexe no que já existe)
    tabelas = list(metadados.sorted_tables)
    colunas_origem = {nome: {c['name'] for c in inspect(origem).get_columns(nome)} for nome in inspect(origem).get_table_names()}

    with destino.begin() as conexao:
        com_dados = [t.name for t in tabelas if conexao.execute(select(func.count()).select_from(t)).scalar()]
        if com_dados and not substituir:
            raise ValueError('O destino já tem dados (' + ', '.join(com_dados[:5]) + ('…' if len(com_dados) > 5 else '')
                             + '). Use --substituir para apagar os dados do destino antes de copiar.')
        _desligar_chaves(conexao, dialeto, tabelas)
        for tabela in reversed(tabelas):
            if tabela.name in com_dados:
                conexao.execute(tabela.delete())

        copiadas = {}
        for tabela in tabelas:
            existentes = colunas_origem.get(tabela.name)
            if not existentes:
                copiadas[tabela.name] = 0
                continue
            colunas = [c for c in tabela.c if c.name in existentes]
            total = 0
            identidade = dialeto == 'mssql' and _com_identidade(tabela)
            if identidade:
                conexao.execute(text(f'SET IDENTITY_INSERT [{tabela.name}] ON'))
            with origem.connect() as leitura:
                resultado = leitura.execution_options(stream_results=True).execute(select(*colunas))
                while True:
                    linhas = resultado.fetchmany(LOTE)
                    if not linhas:
                        break
                    conexao.execute(tabela.insert(), [dict(linha._mapping) for linha in linhas])
                    total += len(linhas)
            if identidade:
                conexao.execute(text(f'SET IDENTITY_INSERT [{tabela.name}] OFF'))
            copiadas[tabela.name] = total
            if total:
                avisar(f'  {tabela.name}: {total} linha(s)')
        _religar_chaves(conexao, dialeto, tabelas)
        _acertar_sequencias(conexao, dialeto, tabelas)

        versao = _versao_das_migracoes()
        if versao:
            # Tabela de controle das migrações, criada do jeito de cada banco (SQL Server não tem CREATE TABLE IF NOT EXISTS)
            from sqlalchemy import MetaData, Table, Column, String
            controle = Table('alembic_version', MetaData(), Column('version_num', String(32), primary_key=True))
            controle.create(conexao, checkfirst=True)
            conexao.execute(controle.delete())
            conexao.execute(controle.insert(), {'version_num': versao})

    # Conferência: mesma quantidade de linhas nos dois lados
    diferencas = []
    with origem.connect() as a, destino.connect() as b:
        for tabela in tabelas:
            if tabela.name not in colunas_origem:
                continue
            n_origem = a.execute(text(f'SELECT COUNT(*) FROM {tabela.name}')).scalar()
            n_destino = b.execute(select(func.count()).select_from(tabela)).scalar()
            if n_origem != n_destino:
                diferencas.append(f'{tabela.name}: origem {n_origem}, destino {n_destino}')
    origem.dispose()
    destino.dispose()
    if diferencas:
        raise RuntimeError('A conferência encontrou diferenças: ' + '; '.join(diferencas))
    avisar(f'Cópia concluída e conferida: {len(copiadas)} tabelas, {sum(copiadas.values())} linhas.'
           + (f' Versão das migrações: {versao}.' if versao else ''))
    return copiadas


def main():
    parser = argparse.ArgumentParser(description='Copia o banco da plataforma de um endereço para outro (SQLite, MySQL, PostgreSQL...).')
    parser.add_argument('--de', required=True, help='endereço do banco de origem (ex.: sqlite:////srv/mentoria/instance/mentoria.db)')
    parser.add_argument('--para', default=None, help='endereço do banco de destino (padrão: DATABASE_URL do .env)')
    parser.add_argument('--substituir', action='store_true', help='apaga os dados do destino antes de copiar')
    argumentos = parser.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    destino = argumentos.para or os.environ.get('DATABASE_URL')
    if not destino:
        parser.error('informe --para ou defina DATABASE_URL no .env')
    if destino.strip() == argumentos.de.strip():
        parser.error('a origem e o destino são o mesmo banco')
    try:
        copiar(argumentos.de, destino, substituir=argumentos.substituir)
    except (ValueError, RuntimeError) as erro:
        print(f'ERRO: {erro}')
        sys.exit(1)


if __name__ == '__main__':
    main()
