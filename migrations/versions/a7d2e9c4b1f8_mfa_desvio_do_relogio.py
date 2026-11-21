"""MFA: diferença entre o relógio do celular e o do servidor (mfa_desvio)

Revision ID: a7d2e9c4b1f8
Revises: f3c8a1d6e2b4
Create Date: 2026-11-21 20:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'a7d2e9c4b1f8'
down_revision = 'f3c8a1d6e2b4'
branch_labels = None
depends_on = None


def upgrade():
    colunas = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('usuario')}
    if 'mfa_desvio' not in colunas:
        with op.batch_alter_table('usuario') as tabela:
            tabela.add_column(sa.Column('mfa_desvio', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('usuario') as tabela:
        tabela.drop_column('mfa_desvio')
