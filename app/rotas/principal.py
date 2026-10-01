from flask import Blueprint, redirect, url_for, render_template
from flask_login import current_user, login_required

bp = Blueprint('principal', __name__)


@bp.route('/')
@login_required
def inicio():
    if current_user.pode_ensinar:
        return redirect(url_for('professor.dashboard'))
    return redirect(url_for('aluno.dashboard'))


@bp.app_errorhandler(403)
def acesso_negado(erro):
    return render_template('compartilhado/erro.html', codigo=403,
                           mensagem='Você não tem permissão para acessar esta página.'), 403


@bp.app_errorhandler(404)
def nao_encontrado(erro):
    return render_template('compartilhado/erro.html', codigo=404, mensagem='Página não encontrada.'), 404
