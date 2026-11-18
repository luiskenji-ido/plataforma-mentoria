"""reunioes: convidados externos (presenca e avaliacao pelo link pessoal) e arquivo da gravacao

Revision ID: c4a1e7d2b9f0
Revises: bcec4bec808e
Create Date: 2026-11-18 09:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = 'c4a1e7d2b9f0'
down_revision = 'bcec4bec808e'
branch_labels = None
depends_on = None


def _colunas(tabela):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(tabela)}


def upgrade():
    tabelas = sa.inspect(op.get_bind()).get_table_names()
    if 'convidado_reuniao' not in tabelas:
        op.create_table('convidado_reuniao',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('reuniao_id', sa.Integer(), nullable=False),
            sa.Column('nome', sa.String(length=150), nullable=False),
            sa.Column('instituicao', sa.String(length=150), nullable=True),
            sa.Column('email', sa.String(length=150), nullable=True),
            sa.Column('codigo', sa.String(length=64), nullable=False),
            sa.Column('na_lista', sa.Boolean(), nullable=True),
            sa.Column('check_in', sa.DateTime(), nullable=True),
            sa.Column('check_out', sa.DateTime(), nullable=True),
            sa.Column('total_minutos', sa.Integer(), nullable=True),
            sa.Column('modalidade', sa.String(length=20), nullable=True),
            sa.Column('checkout_automatico', sa.Boolean(), nullable=True),
            sa.Column('registro_manual', sa.Boolean(), nullable=True),
            sa.Column('registrado_por_id', sa.Integer(), nullable=True),
            sa.Column('nota', sa.Integer(), nullable=True),
            sa.Column('comentario', sa.Text().with_variant(mysql.LONGTEXT(), 'mysql', 'mariadb'), nullable=True),
            sa.Column('avaliado_em', sa.DateTime(), nullable=True),
            sa.Column('criado_em', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['registrado_por_id'], ['usuario.id']),
            sa.ForeignKeyConstraint(['reuniao_id'], ['reuniao_institucional.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_convidado_reuniao_codigo', 'convidado_reuniao', ['codigo'], unique=True)
        op.create_index('ix_convidado_reuniao_reuniao_id', 'convidado_reuniao', ['reuniao_id'], unique=False)
    existentes = _colunas('reuniao_institucional')
    with op.batch_alter_table('reuniao_institucional') as tabela:
        if 'gravacao_arquivo' not in existentes:
            tabela.add_column(sa.Column('gravacao_arquivo', sa.String(length=255), nullable=True))
        if 'gravacao_nome' not in existentes:
            tabela.add_column(sa.Column('gravacao_nome', sa.String(length=255), nullable=True))
        if 'gravacao_tamanho' not in existentes:
            tabela.add_column(sa.Column('gravacao_tamanho', sa.BigInteger(), nullable=True))
        if 'gravacao_enviada_em' not in existentes:
            tabela.add_column(sa.Column('gravacao_enviada_em', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('reuniao_institucional') as tabela:
        tabela.drop_column('gravacao_enviada_em')
        tabela.drop_column('gravacao_tamanho')
        tabela.drop_column('gravacao_nome')
        tabela.drop_column('gravacao_arquivo')
    op.drop_index('ix_convidado_reuniao_reuniao_id', table_name='convidado_reuniao')
    op.drop_index('ix_convidado_reuniao_codigo', table_name='convidado_reuniao')
    op.drop_table('convidado_reuniao')
