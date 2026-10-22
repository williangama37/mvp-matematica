"""Adiciona usuario.trocar_senha (troca obrigatória após o administrador redefinir a senha)

db.create_all() não adiciona colunas a tabelas que já existem, por isso esta migration é
necessária em bancos que já estão em uso. Num banco novo a coluna já é criada pelo
create_all(), então a migration só adiciona o que ainda não existe.

Revision ID: e4b9a1d6c205
Revises: c7d2e8f4a913
Create Date: 2026-10-22 10:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'e4b9a1d6c205'
down_revision = 'c7d2e8f4a913'
branch_labels = None
depends_on = None


def upgrade():
    colunas = {coluna['name'] for coluna in sa.inspect(op.get_bind()).get_columns('usuario')}
    if 'trocar_senha' in colunas:
        return
    with op.batch_alter_table('usuario') as batch_op:
        batch_op.add_column(sa.Column('trocar_senha', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('usuario') as batch_op:
        batch_op.drop_column('trocar_senha')
