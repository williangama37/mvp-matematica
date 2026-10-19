"""Cria a tabela feedback_turma (análise do agente de IA por teste, com histórico)

Não há UNIQUE por teste: cada atualização gera um novo registro. O índice parcial
uq_feedback_turma_pendente só impede duas análises 'pendente' ao mesmo tempo para o
mesmo teste. Como db.create_all() também cria a tabela ao iniciar a aplicação, a
migration só cria o que ainda não existe.

Revision ID: c7d2e8f4a913
Revises: a1f3c9e2b7d4
Create Date: 2026-10-18 15:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'c7d2e8f4a913'
down_revision = 'a1f3c9e2b7d4'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('feedback_turma'):
        return
    op.create_table(
        'feedback_turma',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teste_id', sa.Integer(), nullable=False),
        sa.Column('qtd_respostas', sa.Integer(), nullable=False),
        sa.Column('data_ultima_resposta', sa.DateTime(), nullable=True),
        sa.Column('dados_entrada_json', sa.Text(), nullable=False),
        sa.Column('resultado_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('gatilho', sa.String(length=10), nullable=False),
        sa.Column('modelo', sa.String(length=60), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pendente', 'pronto', 'erro')", name='ck_feedback_turma_status'),
        sa.CheckConstraint("gatilho IN ('manual', 'forcado')", name='ck_feedback_turma_gatilho'),
        sa.ForeignKeyConstraint(['teste_id'], ['teste.id'], name='fk_feedback_turma_teste_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feedback_turma_teste_criado', 'feedback_turma', ['teste_id', 'criado_em'])
    op.create_index('uq_feedback_turma_pendente', 'feedback_turma', ['teste_id'], unique=True,
                    sqlite_where=sa.text("status = 'pendente'"), postgresql_where=sa.text("status = 'pendente'"))


def downgrade():
    op.drop_index('uq_feedback_turma_pendente', table_name='feedback_turma')
    op.drop_index('ix_feedback_turma_teste_criado', table_name='feedback_turma')
    op.drop_table('feedback_turma')
