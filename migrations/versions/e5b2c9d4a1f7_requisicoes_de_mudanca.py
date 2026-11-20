"""requisicoes de mudanca (RDM/CR/SC) e membros do grupo de aprovacao

Revision ID: e5b2c9d4a1f7
Revises: d7e3f1a8c2b5
Create Date: 2026-11-19 23:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = 'e5b2c9d4a1f7'
down_revision = 'd7e3f1a8c2b5'
branch_labels = None
depends_on = None

TEXTO_LONGO = sa.Text().with_variant(mysql.LONGTEXT(), 'mysql', 'mariadb')


def upgrade():
    tabelas = sa.inspect(op.get_bind()).get_table_names()
    if 'requisicao_mudanca' not in tabelas:
        op.create_table('requisicao_mudanca',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('codigo', sa.String(length=20), nullable=False),
            sa.Column('tipo', sa.String(length=20), nullable=False),
            sa.Column('titulo', sa.String(length=200), nullable=False),
            sa.Column('descricao', TEXTO_LONGO, nullable=True),
            sa.Column('justificativa', TEXTO_LONGO, nullable=True),
            sa.Column('risco', sa.String(length=10), nullable=False),
            sa.Column('plano_rollback', TEXTO_LONGO, nullable=True),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('conteudo', TEXTO_LONGO, nullable=True),
            sa.Column('grupo_aprovacao', sa.String(length=100), nullable=True),
            sa.Column('solicitante_id', sa.Integer(), nullable=False),
            sa.Column('data_solicitacao', sa.DateTime(), nullable=False),
            sa.Column('data_agendada', sa.DateTime(), nullable=True),
            sa.Column('aprovador_id', sa.Integer(), nullable=True),
            sa.Column('data_decisao', sa.DateTime(), nullable=True),
            sa.Column('motivo_decisao', sa.String(length=500), nullable=True),
            sa.Column('aplicado_por_id', sa.Integer(), nullable=True),
            sa.Column('data_aplicacao', sa.DateTime(), nullable=True),
            sa.Column('resultado', TEXTO_LONGO, nullable=True),
            sa.ForeignKeyConstraint(['solicitante_id'], ['usuario.id']),
            sa.ForeignKeyConstraint(['aprovador_id'], ['usuario.id']),
            sa.ForeignKeyConstraint(['aplicado_por_id'], ['usuario.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('codigo'))
        op.create_index('ix_requisicao_mudanca_status', 'requisicao_mudanca', ['status'])
    if 'membro_comite_mudanca' not in tabelas:
        op.create_table('membro_comite_mudanca',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('usuario_id', sa.Integer(), nullable=False),
            sa.Column('incluido_por_id', sa.Integer(), nullable=True),
            sa.Column('incluido_em', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['usuario_id'], ['usuario.id']),
            sa.ForeignKeyConstraint(['incluido_por_id'], ['usuario.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('usuario_id'))


def downgrade():
    tabelas = sa.inspect(op.get_bind()).get_table_names()
    if 'membro_comite_mudanca' in tabelas:
        op.drop_table('membro_comite_mudanca')
    if 'requisicao_mudanca' in tabelas:
        op.drop_index('ix_requisicao_mudanca_status', table_name='requisicao_mudanca')
        op.drop_table('requisicao_mudanca')
