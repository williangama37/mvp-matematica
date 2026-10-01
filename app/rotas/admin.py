from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user
from app import db
from app.models import Usuario, Turma, Questao, Teste, PERFIS, PERFIL_ADMINISTRADOR, PERFIL_PROFESSOR, PERFIL_ALUNO
from app.forms import FormularioUsuarioAdmin
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


@bp.route('/usuarios/<int:usuario_id>', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_ADMINISTRADOR)
def editar_usuario(usuario_id):
    usuario = db.get_or_404(Usuario, usuario_id)
    form = FormularioUsuarioAdmin(obj=usuario)
    form.turma_id.choices = [(0, 'Sem turma')] + \
        [(turma.id, turma.descricao) for turma in Turma.query.order_by(Turma.ano_letivo.desc(), Turma.nome).all()]
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

    return render_template('admin/usuario_form.html', form=form, usuario=usuario)


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
