"""Adiciona teste.embaralhar_questoes (ordem das questões diferente para cada aluno)

db.create_all() não adiciona colunas a tabelas que já existem, por isso esta migration é
necessária em bancos que já estão em uso. Num banco novo a coluna já é criada pelo
create_all(), então a migration só adiciona o que ainda não existe.

Revision ID: b5e1d3f7a204
Revises: f2c8d5a7b391
Create Date: 2026-10-27 10:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = 'b5e1d3f7a204'
down_revision = 'f2c8d5a7b391'
branch_labels = None
depends_on = None


def upgrade():
    colunas = {coluna['name'] for coluna in sa.inspect(op.get_bind()).get_columns('teste')}
    if 'embaralhar_questoes' in colunas:
        return
    with op.batch_alter_table('teste') as batch_op:
        batch_op.add_column(sa.Column('embaralhar_questoes', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('teste') as batch_op:
        batch_op.drop_column('embaralhar_questoes')
