"""Cria a tabela geracao_questao (sugestões do gerador de questões, geradas em segundo plano)

Como db.create_all() também cria a tabela ao iniciar a aplicação, a migration só cria o
que ainda não existe.

Revision ID: f2c8d5a7b391
Revises: e4b9a1d6c205
Create Date: 2026-10-22 16:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'f2c8d5a7b391'
down_revision = 'e4b9a1d6c205'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('geracao_questao'):
        return
    op.create_table(
        'geracao_questao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('professor_id', sa.Integer(), nullable=False),
        sa.Column('pedido_json', sa.Text(), nullable=False),
        sa.Column('resultado_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('modelo', sa.String(length=60), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pendente', 'pronto', 'erro')", name='ck_geracao_questao_status'),
        sa.ForeignKeyConstraint(['professor_id'], ['usuario.id'], name='fk_geracao_questao_professor_id',
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('geracao_questao')
