"""Cria a tabela feedback_aluno (feedback do agente de IA por tentativa)

As demais tabelas são criadas por db.create_all() em create_app(), que também cria
esta tabela ao iniciar a aplicação. Por isso a migration só cria o que ainda não existe:
pode ser aplicada tanto num banco novo quanto num banco que já está em uso.

Revision ID: a1f3c9e2b7d4
Revises:
Create Date: 2026-10-18 10:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1f3c9e2b7d4'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('feedback_aluno'):
        return
    op.create_table(
        'feedback_aluno',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tentativa_id', sa.Integer(), nullable=False),
        sa.Column('resultado_json', sa.Text(), nullable=True),
        sa.Column('classificacao_json', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('modelo', sa.String(length=60), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pendente', 'pronto', 'erro')", name='ck_feedback_aluno_status'),
        sa.ForeignKeyConstraint(['tentativa_id'], ['tentativa.id'], name='fk_feedback_aluno_tentativa_id',
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tentativa_id', name='uq_feedback_aluno_tentativa_id'),
    )


def downgrade():
    op.drop_table('feedback_aluno')
