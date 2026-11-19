"""cursos: aulas dentro da plataforma (texto, video, material), testes de conhecimento e progresso automatico

Revision ID: d7e3f1a8c2b5
Revises: c4a1e7d2b9f0
Create Date: 2026-11-18 15:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = 'd7e3f1a8c2b5'
down_revision = 'c4a1e7d2b9f0'
branch_labels = None
depends_on = None

TEXTO_LONGO = sa.Text().with_variant(mysql.LONGTEXT(), 'mysql', 'mariadb')


def upgrade():
    tabelas = sa.inspect(op.get_bind()).get_table_names()
    if 'aula_curso' not in tabelas:
        op.create_table('aula_curso',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('curso_id', sa.Integer(), nullable=False),
            sa.Column('ordem', sa.Integer(), nullable=False),
            sa.Column('titulo', sa.String(length=200), nullable=False),
            sa.Column('texto', TEXTO_LONGO, nullable=True),
            sa.Column('video_tipo', sa.String(length=10), nullable=True),
            sa.Column('video_arquivo', sa.String(length=255), nullable=True),
            sa.Column('video_nome', sa.String(length=255), nullable=True),
            sa.Column('video_tamanho', sa.BigInteger(), nullable=True),
            sa.Column('youtube_id', sa.String(length=20), nullable=True),
            sa.Column('video_duracao', sa.Integer(), nullable=True),
            sa.Column('material_arquivo', sa.String(length=255), nullable=True),
            sa.Column('material_nome', sa.String(length=255), nullable=True),
            sa.Column('origem', sa.String(length=20), nullable=True),
            sa.Column('criado_em', sa.DateTime(), nullable=True),
            sa.Column('atualizado_em', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['curso_id'], ['curso.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_aula_curso_curso_id', 'aula_curso', ['curso_id'], unique=False)
    if 'questao_aula' not in tabelas:
        op.create_table('questao_aula',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('aula_id', sa.Integer(), nullable=False),
            sa.Column('ordem', sa.Integer(), nullable=False),
            sa.Column('enunciado', TEXTO_LONGO, nullable=False),
            sa.Column('alternativas', TEXTO_LONGO, nullable=False),
            sa.Column('correta', sa.Integer(), nullable=False),
            sa.Column('explicacao', TEXTO_LONGO, nullable=True),
            sa.Column('origem', sa.String(length=12), nullable=True),
            sa.Column('criado_em', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['aula_id'], ['aula_curso.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_questao_aula_aula_id', 'questao_aula', ['aula_id'], unique=False)
    if 'progresso_aula' not in tabelas:
        op.create_table('progresso_aula',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('acompanhamento_id', sa.Integer(), nullable=False),
            sa.Column('aula_id', sa.Integer(), nullable=False),
            sa.Column('segundos_assistidos', sa.Integer(), nullable=False),
            sa.Column('posicao_video', sa.Integer(), nullable=False),
            sa.Column('trechos_video', TEXTO_LONGO, nullable=True),
            sa.Column('video_concluido', sa.Boolean(), nullable=False),
            sa.Column('leitura_concluida', sa.Boolean(), nullable=False),
            sa.Column('material_aberto', sa.Boolean(), nullable=False),
            sa.Column('teste_nota', sa.Integer(), nullable=True),
            sa.Column('teste_tentativas', sa.Integer(), nullable=False),
            sa.Column('teste_aprovado', sa.Boolean(), nullable=False),
            sa.Column('teste_respostas', TEXTO_LONGO, nullable=True),
            sa.Column('concluida_em', sa.DateTime(), nullable=True),
            sa.Column('atualizado_em', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['acompanhamento_id'], ['acompanhamento.id']),
            sa.ForeignKeyConstraint(['aula_id'], ['aula_curso.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('acompanhamento_id', 'aula_id', name='uq_progresso_aula')
        )
        op.create_index('ix_progresso_aula_acompanhamento_id', 'progresso_aula', ['acompanhamento_id'], unique=False)
        op.create_index('ix_progresso_aula_aula_id', 'progresso_aula', ['aula_id'], unique=False)


def downgrade():
    tabelas = sa.inspect(op.get_bind()).get_table_names()
    for nome in ('progresso_aula', 'questao_aula', 'aula_curso'):
        if nome in tabelas:
            op.drop_table(nome)
