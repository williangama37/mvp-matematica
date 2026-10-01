from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import current_user
from flask_wtf import FlaskForm
from app import db, estatisticas
from app.models import Teste, Tentativa, Resposta, Alternativa, OrientacaoPedagogica, PERFIL_ALUNO, \
    TIPO_ORIENTACAO_ALUNO
from app.decoradores import perfil_requerido

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
    lista = OrientacaoPedagogica.query.filter_by(tipo=TIPO_ORIENTACAO_ALUNO, destinatario_id=current_user.id) \
        .order_by(OrientacaoPedagogica.criado_em.desc()).all()
    return render_template('compartilhado/orientacoes.html', orientacoes=lista,
                           titulo='Minhas orientações pedagógicas',
                           texto_vazio='Em breve, um agente de IA vai analisar os seus testes e indicar aqui o que '
                                       'revisar e como estudar cada assunto em que você teve dificuldade.')
