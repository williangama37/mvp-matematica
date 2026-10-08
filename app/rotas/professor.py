from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import current_user
from flask_wtf import FlaskForm
from app import db, estatisticas
from app.models import (Usuario, Turma, Assunto, Questao, Alternativa, Teste, Tentativa, Resposta,
                        OrientacaoPedagogica, PERFIL_PROFESSOR, PERFIL_ADMINISTRADOR, PERFIL_ALUNO,
                        LETRAS_ALTERNATIVAS, NIVEIS_DIFICULDADE, TIPO_ORIENTACAO_NIVELAMENTO)
from app.forms import (FormularioTurma, FormularioAdicionarAluno, FormularioAssunto, FormularioQuestao,
                       FormularioTeste)
from app.decoradores import perfil_requerido
from app.agentes import gerador_questao

bp = Blueprint('professor', __name__)


def _opcoes_turmas(rotulo_vazio):
    turmas = Turma.query.order_by(Turma.ano_letivo.desc(), Turma.nome).all()
    return [(0, rotulo_vazio)] + [(turma.id, turma.descricao) for turma in turmas]


# --------------------------------------------------------------------- Dashboards

@bp.route('/dashboard')
@perfil_requerido(PERFIL_PROFESSOR)
def dashboard():
    turma_id = request.args.get('turma_id', 0, type=int)
    turma = db.session.get(Turma, turma_id) if turma_id else None
    dados = estatisticas.dashboard_geral(turma.id if turma else None)
    turmas = Turma.query.order_by(Turma.ano_letivo.desc(), Turma.nome).all()
    return render_template('professor/dashboard.html', dados=dados, turmas=turmas, turma=turma)


@bp.route('/dashboard/aluno/<int:aluno_id>')
@perfil_requerido(PERFIL_PROFESSOR)
def dashboard_aluno(aluno_id):
    aluno = db.get_or_404(Usuario, aluno_id)
    if not aluno.eh_aluno:
        flash('O dashboard individual é apenas para alunos.', 'warning')
        return redirect(url_for('professor.dashboard'))
    alunos = Usuario.query.filter_by(perfil=PERFIL_ALUNO).order_by(Usuario.nome_completo).all()
    return render_template('professor/dashboard_aluno.html', dados=estatisticas.dashboard_aluno(aluno),
                           alunos=alunos)


@bp.route('/dashboard/alunos')
@perfil_requerido(PERFIL_PROFESSOR)
def escolher_aluno():
    aluno_id = request.args.get('aluno_id', type=int)
    if aluno_id:
        return redirect(url_for('professor.dashboard_aluno', aluno_id=aluno_id))
    return redirect(url_for('professor.dashboard'))


# --------------------------------------------------------------------- Turmas

@bp.route('/turmas', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def turmas():
    form = FormularioTurma()
    professores = Usuario.query.filter(Usuario.perfil.in_([PERFIL_PROFESSOR, PERFIL_ADMINISTRADOR])) \
        .order_by(Usuario.nome_completo).all()
    form.professor_id.choices = [(professor.id, professor.nome_completo) for professor in professores]
    if request.method == 'GET':
        form.professor_id.data = current_user.id

    if form.validate_on_submit():
        turma = Turma(nome=form.nome.data, ano_letivo=form.ano_letivo.data, professor_id=form.professor_id.data)
        db.session.add(turma)
        db.session.commit()
        flash('Turma cadastrada.', 'success')
        return redirect(url_for('professor.turmas'))

    lista_turmas = Turma.query.order_by(Turma.ano_letivo.desc(), Turma.nome).all()
    return render_template('professor/turmas.html', form=form, turmas=lista_turmas)


@bp.route('/turmas/<int:turma_id>', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def detalhe_turma(turma_id):
    turma = db.get_or_404(Turma, turma_id)
    form = FormularioAdicionarAluno()
    alunos_disponiveis = Usuario.query.filter(Usuario.perfil == PERFIL_ALUNO,
                                              (Usuario.turma_id.is_(None)) | (Usuario.turma_id != turma.id)) \
        .order_by(Usuario.nome_completo).all()
    form.aluno_id.choices = [
        (aluno.id, f'{aluno.nome_completo} ({aluno.turma.descricao if aluno.turma else "sem turma"})')
        for aluno in alunos_disponiveis
    ]

    if form.validate_on_submit():
        aluno = db.get_or_404(Usuario, form.aluno_id.data)
        aluno.turma_id = turma.id
        db.session.commit()
        flash(f'{aluno.nome_completo} adicionado(a) à turma.', 'success')
        return redirect(url_for('professor.detalhe_turma', turma_id=turma.id))

    alunos = sorted(turma.alunos, key=lambda aluno: aluno.nome_completo)
    return render_template('professor/turma_detalhe.html', turma=turma, alunos=alunos, form=form)


@bp.route('/turmas/<int:turma_id>/editar', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def editar_turma(turma_id):
    turma = db.get_or_404(Turma, turma_id)
    form = FormularioTurma(obj=turma)
    professores = Usuario.query.filter(Usuario.perfil.in_([PERFIL_PROFESSOR, PERFIL_ADMINISTRADOR])) \
        .order_by(Usuario.nome_completo).all()
    form.professor_id.choices = [(professor.id, professor.nome_completo) for professor in professores]

    if form.validate_on_submit():
        turma.nome = form.nome.data
        turma.ano_letivo = form.ano_letivo.data
        turma.professor_id = form.professor_id.data
        db.session.commit()
        flash('Turma atualizada.', 'success')
        return redirect(url_for('professor.turmas'))

    return render_template('professor/turma_form.html', form=form, turma=turma)


@bp.route('/turmas/<int:turma_id>/alunos/<int:aluno_id>/remover', methods=['POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def remover_aluno_turma(turma_id, aluno_id):
    aluno = db.get_or_404(Usuario, aluno_id)
    if aluno.turma_id == turma_id:
        aluno.turma_id = None
        db.session.commit()
        flash(f'{aluno.nome_completo} removido(a) da turma.', 'success')
    return redirect(url_for('professor.detalhe_turma', turma_id=turma_id))


@bp.route('/turmas/<int:turma_id>/excluir', methods=['POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def excluir_turma(turma_id):
    turma = db.get_or_404(Turma, turma_id)
    Usuario.query.filter_by(turma_id=turma.id).update({'turma_id': None})
    Teste.query.filter_by(turma_id=turma.id).update({'turma_id': None})
    OrientacaoPedagogica.query.filter_by(turma_id=turma.id).update({'turma_id': None})
    db.session.delete(turma)
    db.session.commit()
    flash('Turma excluída. Os alunos ficaram sem turma.', 'success')
    return redirect(url_for('professor.turmas'))


# --------------------------------------------------------------------- Assuntos

@bp.route('/assuntos', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def assuntos():
    form = FormularioAssunto()
    if form.validate_on_submit():
        db.session.add(Assunto(nome=form.nome.data, descricao=form.descricao.data))
        db.session.commit()
        flash('Assunto cadastrado.', 'success')
        return redirect(url_for('professor.assuntos'))

    lista_assuntos = Assunto.query.order_by(Assunto.nome).all()
    return render_template('professor/assuntos.html', form=form, assuntos=lista_assuntos)


@bp.route('/assuntos/<int:assunto_id>/editar', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def editar_assunto(assunto_id):
    assunto = db.get_or_404(Assunto, assunto_id)
    form = FormularioAssunto(obj=assunto, assunto_id=assunto.id)
    if form.validate_on_submit():
        assunto.nome = form.nome.data
        assunto.descricao = form.descricao.data
        db.session.commit()
        flash('Assunto atualizado.', 'success')
        return redirect(url_for('professor.assuntos'))
    return render_template('professor/assunto_form.html', form=form)


@bp.route('/assuntos/<int:assunto_id>/excluir', methods=['POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def excluir_assunto(assunto_id):
    assunto = db.get_or_404(Assunto, assunto_id)
    if assunto.questoes:
        flash('Não é possível excluir um assunto que possui questões. Mova ou exclua as questões antes.', 'danger')
    else:
        db.session.delete(assunto)
        db.session.commit()
        flash('Assunto excluído.', 'success')
    return redirect(url_for('professor.assuntos'))


# --------------------------------------------------------------------- Questões

@bp.route('/questoes')
@perfil_requerido(PERFIL_PROFESSOR)
def questoes():
    assunto_id = request.args.get('assunto_id', 0, type=int)
    consulta = Questao.query
    if assunto_id:
        consulta = consulta.filter_by(assunto_id=assunto_id)
    lista_questoes = consulta.order_by(Questao.criado_em.desc()).all()
    return render_template('professor/questoes.html', questoes=lista_questoes,
                           assuntos=Assunto.query.order_by(Assunto.nome).all(), assunto_id=assunto_id,
                           form=FlaskForm())


def _preparar_formulario_questao(form):
    form.assunto_id.choices = [(assunto.id, assunto.nome) for assunto in Assunto.query.order_by(Assunto.nome).all()]


def _salvar_alternativas(questao, form):
    existentes = {alternativa.letra: alternativa for alternativa in questao.alternativas}
    for letra, dados in zip(LETRAS_ALTERNATIVAS, form.alternativas.entries):
        alternativa = existentes.get(letra) or Alternativa(letra=letra, questao=questao)
        alternativa.texto = dados.texto.data
        alternativa.correta = letra == form.alternativa_correta.data
        # A alternativa correta não é distrator.
        alternativa.descricao_distrator = None if alternativa.correta else dados.descricao_distrator.data
        alternativa.tipo_erro = None if alternativa.correta else dados.tipo_erro.data
        db.session.add(alternativa)


@bp.route('/questoes/nova', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def nova_questao():
    form = FormularioQuestao()
    _preparar_formulario_questao(form)

    if form.validate_on_submit():
        questao = Questao(
            enunciado=form.enunciado.data,
            assunto_id=form.assunto_id.data,
            nivel_dificuldade=form.nivel_dificuldade.data,
            habilidade_bncc=form.habilidade_bncc.data or None,
            ativa=form.ativa.data,
            criado_por=current_user.id,
            atualizado_por=current_user.id,
        )
        db.session.add(questao)
        _salvar_alternativas(questao, form)
        db.session.commit()
        flash('Questão cadastrada.', 'success')
        if 'salvar_e_nova' in request.form:
            return redirect(url_for('professor.nova_questao'))
        return redirect(url_for('professor.questoes'))

    return render_template('professor/questao_form.html', form=form, titulo='Nova questão', letras=LETRAS_ALTERNATIVAS)


@bp.route('/questoes/gerar', methods=['POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def gerar_questao():
    """Pede ao agente uma sugestão de questão. Não salva nada: o professor revisa e salva pelo formulário."""
    dados = request.get_json(silent=True) or {}
    assunto_id = str(dados.get('assunto_id', ''))
    assunto = db.session.get(Assunto, int(assunto_id)) if assunto_id.isdigit() else None
    if assunto is None:
        return jsonify(erro='Selecione um assunto.'), 400
    nivel_dificuldade = dados.get('nivel_dificuldade')
    if nivel_dificuldade not in NIVEIS_DIFICULDADE:
        return jsonify(erro='Selecione a dificuldade.'), 400
    habilidade_bncc = (dados.get('habilidade_bncc') or '').strip()[:20] or None

    try:
        sugestao = gerador_questao.gerar_questao(assunto.nome, assunto.descricao, nivel_dificuldade, habilidade_bncc)
    except gerador_questao.ErroGeracao as erro:
        current_app.logger.error('Falha ao gerar questão com o agente: %s', erro)
        return jsonify(erro=str(erro)), 502
    except Exception:
        current_app.logger.exception('Falha ao gerar questão com o agente.')
        return jsonify(erro='Não foi possível gerar a questão agora. Tente novamente.'), 502
    return jsonify(sugestao)


@bp.route('/questoes/<int:questao_id>/editar', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def editar_questao(questao_id):
    questao = db.get_or_404(Questao, questao_id)
    form = FormularioQuestao(obj=questao)
    _preparar_formulario_questao(form)

    if request.method == 'GET':
        for dados, alternativa in zip(form.alternativas.entries, questao.alternativas):
            dados.texto.data = alternativa.texto
            dados.descricao_distrator.data = alternativa.descricao_distrator
            dados.tipo_erro.data = alternativa.tipo_erro or ''
        if questao.alternativa_correta:
            form.alternativa_correta.data = questao.alternativa_correta.letra

    if form.validate_on_submit():
        questao.enunciado = form.enunciado.data
        questao.assunto_id = form.assunto_id.data
        questao.nivel_dificuldade = form.nivel_dificuldade.data
        questao.habilidade_bncc = form.habilidade_bncc.data or None
        questao.ativa = form.ativa.data
        questao.atualizado_por = current_user.id
        _salvar_alternativas(questao, form)
        db.session.commit()
        flash('Questão atualizada.', 'success')
        return redirect(url_for('professor.questoes'))

    ja_respondida = Resposta.query.filter_by(questao_id=questao.id).first() is not None
    return render_template('professor/questao_form.html', form=form, titulo='Editar questão',
                           letras=LETRAS_ALTERNATIVAS, ja_respondida=ja_respondida)


@bp.route('/questoes/<int:questao_id>/excluir', methods=['POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def excluir_questao(questao_id):
    questao = db.get_or_404(Questao, questao_id)
    if Resposta.query.filter_by(questao_id=questao.id).first():
        # Preserva o histórico de diagnóstico dos alunos.
        questao.ativa = False
        db.session.commit()
        flash('A questão já foi respondida por alunos, então foi apenas desativada para preservar o histórico.',
              'warning')
    else:
        for teste in Teste.query.filter(Teste.questoes.any(Questao.id == questao.id)).all():
            teste.questoes.remove(questao)
        db.session.delete(questao)
        db.session.commit()
        flash('Questão excluída.', 'success')
    return redirect(url_for('professor.questoes'))


# --------------------------------------------------------------------- Testes

def _preparar_formulario_teste(form):
    form.turma_id.choices = _opcoes_turmas('Todas as turmas')
    questoes_ativas = Questao.query.filter_by(ativa=True).join(Assunto) \
        .order_by(Assunto.nome, Questao.id).all()
    form.questoes.choices = [(questao.id, questao.enunciado) for questao in questoes_ativas]
    return questoes_ativas


@bp.route('/testes')
@perfil_requerido(PERFIL_PROFESSOR)
def testes():
    lista_testes = Teste.query.order_by(Teste.criado_em.desc()).all()
    return render_template('professor/testes.html', testes=lista_testes, form=FlaskForm())


@bp.route('/testes/novo', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def novo_teste():
    form = FormularioTeste()
    questoes_ativas = _preparar_formulario_teste(form)

    if form.validate_on_submit():
        teste = Teste(
            titulo=form.titulo.data,
            descricao=form.descricao.data,
            turma_id=form.turma_id.data or None,
            ativo=form.ativo.data,
            criado_por=current_user.id,
            questoes=Questao.query.filter(Questao.id.in_(form.questoes.data)).all(),
        )
        db.session.add(teste)
        db.session.commit()
        flash('Teste criado.', 'success')
        return redirect(url_for('professor.testes'))

    return render_template('professor/teste_form.html', form=form, titulo='Novo teste', questoes=questoes_ativas)


@bp.route('/testes/<int:teste_id>/editar', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def editar_teste(teste_id):
    teste = db.get_or_404(Teste, teste_id)
    form = FormularioTeste(obj=teste)
    questoes_ativas = _preparar_formulario_teste(form)
    if request.method == 'GET':
        form.turma_id.data = teste.turma_id or 0
        form.questoes.data = [questao.id for questao in teste.questoes]

    if teste.tentativas:
        # Alterar as questões depois de aplicado distorceria a comparação entre alunos.
        del form.questoes

    if form.validate_on_submit():
        teste.titulo = form.titulo.data
        teste.descricao = form.descricao.data
        teste.turma_id = form.turma_id.data or None
        teste.ativo = form.ativo.data
        if not teste.tentativas:
            teste.questoes = Questao.query.filter(Questao.id.in_(form.questoes.data)).all()
        db.session.commit()
        flash('Teste atualizado.', 'success')
        return redirect(url_for('professor.testes'))

    return render_template('professor/teste_form.html', form=form, titulo='Editar teste', questoes=questoes_ativas,
                           teste=teste)


@bp.route('/testes/<int:teste_id>/excluir', methods=['POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def excluir_teste(teste_id):
    teste = db.get_or_404(Teste, teste_id)
    db.session.delete(teste)
    db.session.commit()
    flash('Teste e respectivos resultados excluídos.', 'success')
    return redirect(url_for('professor.testes'))


@bp.route('/testes/<int:teste_id>/resultados')
@perfil_requerido(PERFIL_PROFESSOR)
def resultados_teste(teste_id):
    teste = db.get_or_404(Teste, teste_id)
    tentativas = Tentativa.query.filter(Tentativa.teste_id == teste.id, Tentativa.finalizada_em.isnot(None)) \
        .order_by(Tentativa.finalizada_em.desc()).all()

    # Para cada questão: quantos alunos escolheram cada alternativa.
    escolhas = dict(
        db.session.query(Resposta.alternativa_id, db.func.count(Resposta.id))
        .join(Tentativa, Resposta.tentativa_id == Tentativa.id)
        .filter(Tentativa.teste_id == teste.id)
        .group_by(Resposta.alternativa_id).all()
    )
    return render_template('professor/teste_resultados.html', teste=teste, tentativas=tentativas, escolhas=escolhas)


@bp.route('/tentativas/<int:tentativa_id>')
@perfil_requerido(PERFIL_PROFESSOR)
def ver_tentativa(tentativa_id):
    tentativa = db.get_or_404(Tentativa, tentativa_id)
    return render_template('compartilhado/tentativa.html', tentativa=tentativa, mostrar_distratores=True)


# --------------------------------------------------------------------- Orientações (Agentes de IA)

@bp.route('/orientacoes-nivelamento')
@perfil_requerido(PERFIL_PROFESSOR)
def orientacoes_nivelamento():
    orientacoes = OrientacaoPedagogica.query.filter_by(tipo=TIPO_ORIENTACAO_NIVELAMENTO,
                                                       destinatario_id=current_user.id) \
        .order_by(OrientacaoPedagogica.criado_em.desc()).all()
    return render_template('compartilhado/orientacoes.html', orientacoes=orientacoes,
                           titulo='Orientações para aulas de nivelamento',
                           texto_vazio='Quando os agentes de IA forem implementados, eles analisarão os erros '
                                       'mapeados pelos distratores e sugerirão aqui planos para as aulas de '
                                       'nivelamento em matemática de cada turma.')
