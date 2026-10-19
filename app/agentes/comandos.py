"""Comandos de linha de comando dos agentes (flask agentes ...)."""
import click
from flask.cli import AppGroup

from app.agentes import execucao, feedback_aluno
from app.models import Tentativa

grupo_agentes = AppGroup('agentes', help='Comandos dos agentes de IA.')


@grupo_agentes.command('feedbacks')
def gerar_feedbacks():
    """Gera os feedbacks de tentativas que ainda não têm, que deram erro ou que ficaram presas em 'pendente'."""
    tentativas = Tentativa.query.filter(Tentativa.finalizada_em.isnot(None)).order_by(Tentativa.finalizada_em).all()
    for tentativa in tentativas:
        if tentativa.feedback and not execucao.pode_gerar_novamente(tentativa.feedback):
            continue
        click.echo(f'Tentativa {tentativa.id}: gerando feedback...')
        feedback_aluno.agendar(tentativa, em_segundo_plano=False)
        click.echo(f'  status: {tentativa.feedback.status if tentativa.feedback else "não gerado"}')
