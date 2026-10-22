from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from flask_login import login_user, logout_user, current_user
from app import db
from app.models import Usuario, Turma, PERFIL_ALUNO
from app.forms import FormularioLogin, FormularioRegistro, FormularioTrocarSenha

bp = Blueprint('autenticacao', __name__)

# Enquanto a senha provisória não é trocada, o usuário fica identificado só na sessão (sem login).
CHAVE_TROCA_SENHA = 'troca_senha_usuario_id'
CHAVE_TROCA_LEMBRAR = 'troca_senha_lembrar_me'


def _exigir_troca_de_senha(usuario, lembrar_me=False):
    session[CHAVE_TROCA_SENHA] = usuario.id
    session[CHAVE_TROCA_LEMBRAR] = lembrar_me
    return redirect(url_for('autenticacao.trocar_senha'))


@bp.before_app_request
def verificar_senha_provisoria():
    """Quem já estava logado quando o administrador redefiniu a senha também precisa trocá-la."""
    if request.endpoint in ('static', 'autenticacao.trocar_senha', 'autenticacao.sair'):
        return None
    if current_user.is_authenticated and current_user.trocar_senha:
        usuario = current_user._get_current_object()
        logout_user()
        return _exigir_troca_de_senha(usuario)
    return None


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

        if usuario.trocar_senha:
            return _exigir_troca_de_senha(usuario, form.lembrar_me.data)

        login_user(usuario, remember=form.lembrar_me.data)
        usuario.ultimo_acesso = datetime.now()
        db.session.commit()
        return redirect(url_for('principal.inicio'))

    return render_template('login.html', form=form)


@bp.route('/trocar-senha', methods=['GET', 'POST'])
def trocar_senha():
    usuario_id = session.get(CHAVE_TROCA_SENHA)
    usuario = db.session.get(Usuario, usuario_id) if usuario_id else None
    if usuario is None or not usuario.trocar_senha:
        session.pop(CHAVE_TROCA_SENHA, None)
        session.pop(CHAVE_TROCA_LEMBRAR, None)
        return redirect(url_for('autenticacao.entrar'))

    form = FormularioTrocarSenha()
    if form.validate_on_submit():
        if usuario.verificar_senha(form.senha.data):
            form.senha.errors.append('A nova senha precisa ser diferente da senha provisória.')
        else:
            usuario.definir_senha(form.senha.data)
            usuario.trocar_senha = False
            usuario.ultimo_acesso = datetime.now()
            db.session.commit()
            lembrar_me = session.pop(CHAVE_TROCA_LEMBRAR, False)
            session.pop(CHAVE_TROCA_SENHA, None)
            login_user(usuario, remember=lembrar_me)
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('principal.inicio'))

    return render_template('trocar_senha.html', form=form, usuario=usuario)


@bp.route('/logout', methods=['GET', 'POST'])
def sair():
    logout_user()
    session.pop(CHAVE_TROCA_SENHA, None)
    session.pop(CHAVE_TROCA_LEMBRAR, None)
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
