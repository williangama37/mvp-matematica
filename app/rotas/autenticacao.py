from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from app import db
from app.models import Usuario, Turma, PERFIL_ALUNO
from app.forms import FormularioLogin, FormularioRegistro

bp = Blueprint('autenticacao', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def entrar():
    if current_user.is_authenticated:
        return redirect(url_for('principal.inicio'))

    form = FormularioLogin()
    if form.validate_on_submit():
        usuario = Usuario.query.filter_by(nome_usuario=form.nome_usuario.data).first()

        if usuario is None or not usuario.verificar_senha(form.senha.data):
            flash('Nome de usuário ou senha incorretos', 'danger')
            return redirect(url_for('autenticacao.entrar'))

        login_user(usuario, remember=form.lembrar_me.data)
        usuario.ultimo_acesso = datetime.now()
        db.session.commit()
        return redirect(url_for('principal.inicio'))

    return render_template('login.html', form=form)


@bp.route('/logout', methods=['GET', 'POST'])
def sair():
    logout_user()
    return redirect(url_for('autenticacao.entrar'))


@bp.route('/registro', methods=['GET', 'POST'])
def registrar():
    if current_user.is_authenticated:
        return redirect(url_for('principal.inicio'))

    form = FormularioRegistro()
    form.turma_id.choices = [(0, 'Ainda não sei / sem turma')] + \
        [(turma.id, turma.descricao) for turma in Turma.query.order_by(Turma.ano_letivo.desc(), Turma.nome).all()]

    if form.validate_on_submit():
        # Todo cadastro público é de aluno; só o administrador promove a professor.
        usuario = Usuario(
            nome_usuario=form.nome_usuario.data,
            nome_completo=form.nome_completo.data,
            email=form.email.data or None,
            perfil=PERFIL_ALUNO,
            turma_id=form.turma_id.data or None,
        )
        usuario.definir_senha(form.senha.data)
        db.session.add(usuario)
        db.session.commit()
        flash('Parabéns, você se registrou com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('autenticacao.entrar'))

    return render_template('registro.html', form=form)
