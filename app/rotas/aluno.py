from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify, current_app
from flask_login import current_user
from flask_wtf import FlaskForm
from app import db, estatisticas
from app.models import Teste, Tentativa, Resposta, Alternativa, FeedbackAluno, PERFIL_ALUNO
from app.decoradores import perfil_requerido
from app.agentes import feedback_aluno, classificacao, execucao

bp = Blueprint('aluno', __name__)


def _testes_disponiveis():
    consulta = Teste.query.filter_by(ativo=True)
    if current_user.turma_id:
        consulta = consulta.filter((Teste.turma_id.is_(None)) | (Teste.turma_id == current_user.turma_id))
    else:
        consulta = consulta.filter(Teste.turma_id.is_(None))
    return consulta.order_by(Teste.criado_em.desc()).all()


def _tentativa_finalizada(teste_id):
    return Tentativa.query.filter(Tentativa.teste_id == teste_id, Tentativa.aluno_id == current_user.id,
                                  Tentativa.finalizada_em.isnot(None)).first()


@bp.route('/dashboard')
@perfil_requerido(PERFIL_ALUNO)
def dashboard():
    return render_template('aluno/dashboard.html', dados=estatisticas.dashboard_aluno(current_user),
                           pendentes=sum(1 for teste in _testes_disponiveis() if not _tentativa_finalizada(teste.id)))


@bp.route('/testes')
@perfil_requerido(PERFIL_ALUNO)
def testes():
    lista = [(teste, _tentativa_finalizada(teste.id)) for teste in _testes_disponiveis()]
    return render_template('aluno/testes.html', testes=lista)


@bp.route('/testes/<int:teste_id>', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_ALUNO)
def realizar_teste(teste_id):
    teste = db.get_or_404(Teste, teste_id)
    if teste not in _testes_disponiveis():
        abort(404)

    tentativa_anterior = _tentativa_finalizada(teste.id)
    if tentativa_anterior:
        flash('Você já realizou este teste. Veja o seu resultado.', 'info')
        return redirect(url_for('aluno.resultado', tentativa_id=tentativa_anterior.id))

    form = FlaskForm()
    if form.validate_on_submit():
        tentativa = Tentativa(teste_id=teste.id, aluno_id=current_user.id, total_questoes=len(teste.questoes))
        acertos = 0
        for questao in teste.questoes:
            alternativa_id = request.form.get(f'questao_{questao.id}', type=int)
            alternativa = db.session.get(Alternativa, alternativa_id) if alternativa_id else None
            if alternativa and alternativa.questao_id != questao.id:
                alternativa = None
            correta = bool(alternativa and alternativa.correta)
            acertos += correta
            tentativa.respostas.append(Resposta(questao_id=questao.id,
                                                alternativa_id=alternativa.id if alternativa else None,
                                                correta=correta))
        tentativa.total_acertos = acertos
        tentativa.finalizada_em = datetime.now()
        db.session.add(tentativa)
        db.session.commit()
        _agendar_feedback(tentativa)
        flash('Teste enviado! Confira o seu resultado.', 'success')
        return redirect(url_for('aluno.resultado', tentativa_id=tentativa.id))

    return render_template('aluno/realizar_teste.html', teste=teste, form=form)


@bp.route('/resultados/<int:tentativa_id>')
@perfil_requerido(PERFIL_ALUNO)
def resultado(tentativa_id):
    tentativa = db.get_or_404(Tentativa, tentativa_id)
    if tentativa.aluno_id != current_user.id:
        abort(403)
    return render_template('compartilhado/tentativa.html', tentativa=tentativa, mostrar_distratores=False)


@bp.route('/orientacoes')
@perfil_requerido(PERFIL_ALUNO)
def orientacoes():
    """Feedbacks do agente, do teste mais recente para o mais antigo. Só lê do banco."""
    feedbacks = FeedbackAluno.query.join(Tentativa).filter(Tentativa.aluno_id == current_user.id) \
        .order_by(Tentativa.finalizada_em.desc(), Tentativa.id.desc()).all()
    return render_template('aluno/orientacoes.html', feedbacks=feedbacks, form=FlaskForm(),
                           classificacoes=classificacao.CLASSIFICACOES, variacoes=classificacao.VARIACOES,
                           pode_gerar_novamente=execucao.pode_gerar_novamente)


@bp.route('/orientacoes/<int:tentativa_id>/status')
@perfil_requerido(PERFIL_ALUNO)
def status_feedback(tentativa_id):
    """Consultado pela página enquanto o feedback está em preparação."""
    return jsonify(status=_feedback_do_aluno(tentativa_id).status)


@bp.route('/orientacoes/<int:tentativa_id>/gerar-novamente', methods=['POST'])
@perfil_requerido(PERFIL_ALUNO)
def gerar_feedback_novamente(tentativa_id):
    feedback = _feedback_do_aluno(tentativa_id)
    if FlaskForm().validate_on_submit() and execucao.pode_gerar_novamente(feedback):
        _agendar_feedback(feedback.tentativa)
        flash('Estamos preparando o seu feedback novamente.', 'info')
    return redirect(url_for('aluno.orientacoes'))


def _feedback_do_aluno(tentativa_id):
    """O aluno só acessa feedbacks das próprias tentativas."""
    feedback = FeedbackAluno.query.join(Tentativa) \
        .filter(FeedbackAluno.tentativa_id == tentativa_id, Tentativa.aluno_id == current_user.id).first()
    if feedback is None:
        abort(404)
    return feedback


def _agendar_feedback(tentativa):
    """O teste já foi salvo: uma falha aqui não pode impedir o aluno de ver o resultado."""
    try:
        feedback_aluno.agendar(tentativa)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Não foi possível agendar o feedback da tentativa %s.', tentativa.id)
