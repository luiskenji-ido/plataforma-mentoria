"""MFA no login, primeiro acesso, log do catálogo de IA e fim das Solicitações de Mentoria

Revision ID: f3c8a1d6e2b4
Revises: e5b2c9d4a1f7
Create Date: 2026-11-21 10:00:00

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = 'f3c8a1d6e2b4'
down_revision = 'e5b2c9d4a1f7'
branch_labels = None
depends_on = None

TEXTO_LONGO = sa.Text().with_variant(mysql.LONGTEXT(), 'mysql', 'mariadb')


def upgrade():
    conexao = op.get_bind()
    inspetor = sa.inspect(conexao)
    tabelas = inspetor.get_table_names()

    colunas = {c['name'] for c in inspetor.get_columns('usuario')}
    with op.batch_alter_table('usuario') as tabela:
        if 'mfa_ativo' not in colunas:
            tabela.add_column(sa.Column('mfa_ativo', sa.Boolean(), nullable=False, server_default=sa.false()))
        if 'mfa_segredo' not in colunas:
            tabela.add_column(sa.Column('mfa_segredo', sa.String(length=255), nullable=True))
        if 'mfa_codigos_recuperacao' not in colunas:
            tabela.add_column(sa.Column('mfa_codigos_recuperacao', TEXTO_LONGO, nullable=True))
        if 'mfa_ultimo_passo' not in colunas:
            tabela.add_column(sa.Column('mfa_ultimo_passo', sa.Integer(), nullable=True))
        if 'mfa_ativado_em' not in colunas:
            tabela.add_column(sa.Column('mfa_ativado_em', sa.DateTime(), nullable=True))

    if 'configuracao_sistema' not in tabelas:
        op.create_table('configuracao_sistema',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('chave', sa.String(length=60), nullable=False),
            sa.Column('valor', TEXTO_LONGO, nullable=False),
            sa.Column('atualizado_em', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('chave'))

    if 'log_catalogo_ia' not in tabelas:
        op.create_table('log_catalogo_ia',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('data', sa.DateTime(), nullable=False),
            sa.Column('tipo', sa.String(length=30), nullable=False),
            sa.Column('provedor', sa.String(length=20), nullable=True),
            sa.Column('modelo', sa.String(length=80), nullable=True),
            sa.Column('antes', sa.String(length=120), nullable=True),
            sa.Column('depois', sa.String(length=120), nullable=True),
            sa.Column('aplicado', sa.Boolean(), nullable=False),
            sa.Column('detalhe', TEXTO_LONGO, nullable=True),
            sa.Column('fonte', sa.String(length=255), nullable=True),
            sa.PrimaryKeyConstraint('id'))
        op.create_index('ix_log_catalogo_ia_data', 'log_catalogo_ia', ['data'])

    # Solicitações de Mentoria saíram da plataforma: o módulo sai dos perfis personalizados e a tabela é apagada
    if 'perfil_personalizado' in tabelas:
        perfis = sa.table('perfil_personalizado', sa.column('id', sa.Integer), sa.column('modulos', sa.Text))
        for id_perfil, modulos in conexao.execute(sa.select(perfis.c.id, perfis.c.modulos)).fetchall():
            try:
                lista = json.loads(modulos or '[]')
            except ValueError:
                continue
            if 'solicitacoes' in lista:
                lista = [m for m in lista if m != 'solicitacoes']
                conexao.execute(perfis.update().where(perfis.c.id == id_perfil).values(modulos=json.dumps(lista)))
    if 'solicitacao_mentoria' in tabelas:
        op.drop_table('solicitacao_mentoria')


def downgrade():
    tabelas = sa.inspect(op.get_bind()).get_table_names()
    if 'solicitacao_mentoria' not in tabelas:
        op.create_table('solicitacao_mentoria',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('nome', sa.String(length=100), nullable=False),
            sa.Column('email', sa.String(length=120), nullable=False),
            sa.Column('motivo', TEXTO_LONGO, nullable=False),
            sa.Column('status', sa.String(length=20), nullable=True),
            sa.Column('data_solicitacao', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'))
    if 'log_catalogo_ia' in tabelas:
        op.drop_index('ix_log_catalogo_ia_data', table_name='log_catalogo_ia')
        op.drop_table('log_catalogo_ia')
    if 'configuracao_sistema' in tabelas:
        op.drop_table('configuracao_sistema')
    with op.batch_alter_table('usuario') as tabela:
        for coluna in ('mfa_ativado_em', 'mfa_ultimo_passo', 'mfa_codigos_recuperacao', 'mfa_segredo', 'mfa_ativo'):
            tabela.drop_column(coluna)
