from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from app import db
from app.models import Usuario, Turma, Questao, Teste, PERFIS, PERFIL_ADMINISTRADOR, PERFIL_PROFESSOR, PERFIL_ALUNO
from app.forms import FormularioUsuarioAdmin, FormularioRedefinirSenha
from app.decoradores import perfil_requerido

bp = Blueprint('admin', __name__)


@bp.route('/usuarios')
@perfil_requerido(PERFIL_ADMINISTRADOR)
def usuarios():
    perfil = request.args.get('perfil', '')
    consulta = Usuario.query
    if perfil in PERFIS:
        consulta = consulta.filter_by(perfil=perfil)
    lista_usuarios = consulta.order_by(Usuario.perfil, Usuario.nome_completo).all()
    return render_template('admin/usuarios.html', usuarios=lista_usuarios, perfis=PERFIS, perfil_filtro=perfil,
                           form=FormularioUsuarioAdmin())


def _formulario_usuario(usuario):
    form = FormularioUsuarioAdmin(obj=usuario)
    form.turma_id.choices = [(0, 'Sem turma')] +         [(turma.id, turma.descricao) for turma in Turma.query.order_by(Turma.ano_letivo.desc(), Turma.nome).all()]
    return form


@bp.route('/usuarios/<int:usuario_id>', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_ADMINISTRADOR)
def editar_usuario(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    form = _formulario_usuario(usuario)
    if request.method == 'GET':
        form.turma_id.data = usuario.turma_id or 0

    if form.validate_on_submit():
        if usuario.id == current_user.id and form.perfil.data != PERFIL_ADMINISTRADOR:
            flash('Você não pode remover o seu próprio acesso de administrador.', 'danger')
            return redirect(url_for('admin.editar_usuario', usuario_id=usuario.id))

        usuario.perfil = form.perfil.data
        # Só alunos pertencem a uma turma; professores são vinculados como responsáveis.
        usuario.turma_id = (form.turma_id.data or None) if usuario.perfil == PERFIL_ALUNO else None
        db.session.commit()
        flash(f'Usuário {usuario.nome_usuario} atualizado: agora é {usuario.nome_perfil}.', 'success')
        return redirect(url_for('admin.usuarios'))

    return render_template('admin/usuario_form.html', form=form, form_senha=FormularioRedefinirSenha(),
                           usuario=usuario)


@bp.route('/usuarios/<int:usuario_id>/senha', methods=['POST'])
@perfil_requerido(PERFIL_ADMINISTRADOR)
def redefinir_senha(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    form_senha = FormularioRedefinirSenha()

    if form_senha.validate_on_submit():
        usuario.definir_senha(form_senha.nova_senha.data)
        # A senha definida pelo administrador é provisória: o usuário cria a dele no próximo login.
        # Quem altera a própria senha não precisa trocá-la de novo.
        usuario.trocar_senha = usuario.id != current_user.id
        db.session.commit()
        if usuario.trocar_senha:
            flash(f'Senha de {usuario.nome_usuario} alterada. No próximo login será pedida uma nova senha.', 'success')
        else:
            flash('Sua senha foi alterada.', 'success')
        return redirect(url_for('admin.usuarios'))

    form = _formulario_usuario(usuario)
    form.turma_id.data = usuario.turma_id or 0
    return render_template('admin/usuario_form.html', form=form, form_senha=form_senha, usuario=usuario)


@bp.route('/usuarios/<int:usuario_id>/promover', methods=['POST'])
@perfil_requerido(PERFIL_ADMINISTRADOR)
def promover_professor(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    if usuario.perfil == PERFIL_ALUNO:
        usuario.perfil = PERFIL_PROFESSOR
        usuario.turma_id = None
        db.session.commit()
        flash(f'{usuario.nome_completo} agora é Professor.', 'success')
    return redirect(url_for('admin.usuarios'))


@bp.route('/usuarios/<int:usuario_id>/excluir', methods=['POST'])
@perfil_requerido(PERFIL_ADMINISTRADOR)
def excluir_usuario(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    if usuario.id == current_user.id:
        flash('Você não pode excluir a sua própria conta.', 'danger')
        return redirect(url_for('admin.usuarios'))

    # Questões, testes e turmas continuam existindo, apenas sem o autor vinculado.
    Turma.query.filter_by(professor_id=usuario.id).update({'professor_id': None})
    Questao.query.filter_by(criado_por=usuario.id).update({'criado_por': None})
    Questao.query.filter_by(atualizado_por=usuario.id).update({'atualizado_por': None})
    Teste.query.filter_by(criado_por=usuario.id).update({'criado_por': None})
    db.session.delete(usuario)
    db.session.commit()
    flash('Usuário excluído.', 'success')
    return redirect(url_for('admin.usuarios'))
