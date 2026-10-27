from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, abort
from flask_login import current_user
from flask_wtf import FlaskForm
from app import db, estatisticas, sorteio
from app.models import (Usuario, Turma, Assunto, Questao, Alternativa, Teste, Tentativa, Resposta,
                        OrientacaoPedagogica, GeracaoQuestao, PERFIL_PROFESSOR, PERFIL_ADMINISTRADOR,
                        PERFIL_ALUNO, LETRAS_ALTERNATIVAS, NIVEIS_DIFICULDADE)
from app.forms import (FormularioTurma, FormularioAdicionarAluno, FormularioAssunto, FormularioQuestao,
                       FormularioTeste, FormularioGerarTeste)
from app.decoradores import perfil_requerido
from app.agentes import gerador_questao, feedback_turma, classificacao, execucao

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
    """Inicia a geração de uma sugestão de questão em segundo plano e responde na hora.
    A página consulta status_geracao_questao até a sugestão ficar pronta. Nada é salvo como questão:
    o professor revisa e salva pelo formulário."""
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
        registro = gerador_questao.agendar(current_user.id, assunto, nivel_dificuldade, habilidade_bncc)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Falha ao iniciar a geração de questão.')
        registro = None
    if registro is None:
        return jsonify(erro='Não foi possível iniciar a geração agora. Tente novamente.'), 500
    return jsonify(url_status=url_for('professor.status_geracao_questao', geracao_id=registro.id)), 202


@bp.route('/questoes/gerar/<int:geracao_id>')
@perfil_requerido(PERFIL_PROFESSOR)
def status_geracao_questao(geracao_id):
    """Situação da geração, lida do banco (nunca chama o agente)."""
    registro = db.get_or_404(GeracaoQuestao, geracao_id)
    if registro.professor_id != current_user.id:
        abort(404)
    if execucao.pendente_expirado(registro):
        execucao.marcar_erro(registro)
    if registro.com_erro:
        return jsonify(status=registro.status, erro='Não foi possível gerar a questão agora. Tente novamente.')
    return jsonify(status=registro.status, sugestao=registro.resultado)


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
    return render_template('professor/testes.html', testes=lista_testes, form=FlaskForm(),
                           turmas=Turma.query.order_by(Turma.ano_letivo.desc(), Turma.nome).all())


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
            embaralhar_questoes=form.embaralhar_questoes.data,
            criado_por=current_user.id,
            questoes=Questao.query.filter(Questao.id.in_(form.questoes.data)).all(),
        )
        db.session.add(teste)
        db.session.commit()
        flash('Teste criado.', 'success')
        return redirect(url_for('professor.testes'))

    return render_template('professor/teste_form.html', form=form, titulo='Novo teste', questoes=questoes_ativas,
                           turmas=Turma.query.order_by(Turma.ano_letivo.desc(), Turma.nome).all())


@bp.route('/testes/gerar')
@perfil_requerido(PERFIL_PROFESSOR)
def escolher_turma_gerar_teste():
    turma_id = request.args.get('turma_id', type=int)
    if turma_id is not None:
        return redirect(url_for('professor.gerar_teste', turma_id=turma_id))
    flash('Selecione a turma (ou todas as turmas) para gerar o teste.', 'warning')
    return redirect(url_for('professor.novo_teste'))


@bp.route('/testes/gerar-automatico', methods=['GET', 'POST'], defaults={'turma_id': 0})
@bp.route('/turmas/<int:turma_id>/gerar-teste', methods=['GET', 'POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def gerar_teste(turma_id):
    """Teste montado por sorteio. A prévia fica na própria página (campos 'questao', na ordem exibida):
    sortear tudo, trocar uma questão e salvar reenviam o formulário, e nada é gravado antes de o
    professor confirmar. turma_id 0 = todas as turmas, como no cadastro manual."""
    turma = db.get_or_404(Turma, turma_id) if turma_id else None
    destino = f'a turma {turma.descricao}' if turma else 'todas as turmas'
    form = FormularioGerarTeste()
    form.assuntos.choices = [(assunto.id, assunto.nome) for assunto in Assunto.query.order_by(Assunto.nome).all()]
    if 'titulo' not in request.form:
        # A seção de confirmação só aparece com a prévia: até lá, valem os valores padrão.
        form.titulo.data = f'Diagnóstico — {turma.descricao}' if turma else 'Diagnóstico'
        form.ativo.data = True
        form.embaralhar_questoes.data = True

    questoes_ativas = Questao.query.filter_by(ativa=True).join(Assunto).order_by(Assunto.nome, Questao.id).all()
    por_id = {questao.id: questao for questao in questoes_ativas}
    previa = []
    for questao_id in request.form.getlist('questao', type=int):
        if questao_id in por_id and por_id[questao_id] not in previa:
            previa.append(por_id[questao_id])

    acao, _, posicao = request.form.get('acao', '').partition(':')
    if form.validate_on_submit():
        if acao == 'sortear':
            try:
                previa = sorteio.sortear(form.assuntos.data, form.quantidade.data, form.distribuicao)
            except sorteio.SorteioImpossivel as erro:
                flash(str(erro), 'warning')
        elif acao in ('trocar', 'escolher') and posicao.isdigit() and int(posicao) < len(previa):
            indice = int(posicao)
            atual = previa[indice]
            em_uso = [questao.id for questao in previa]
            if acao == 'trocar':
                nova = sorteio.substituta(atual, em_uso)
                if nova is None:
                    flash(f'Não há outra questão ativa de {atual.assunto.nome} ({atual.nome_dificuldade.lower()}) '
                          f'para trocar a questão {indice + 1}.', 'warning')
            else:
                nova = por_id.get(request.form.get(f'escolha_{indice}', type=int))
                if nova is None or nova.id in em_uso:
                    nova = None
                    flash('Escolha uma questão que ainda não esteja no teste.', 'warning')
            if nova:
                previa[indice] = nova
        elif acao == 'salvar':
            if not form.titulo.data:
                form.titulo.errors.append('Informe o título do teste.')
            elif not previa:
                flash('Sorteie as questões antes de salvar.', 'warning')
            else:
                teste = Teste(
                    titulo=form.titulo.data,
                    descricao=form.descricao.data,
                    turma_id=turma.id if turma else None,
                    ativo=form.ativo.data,
                    embaralhar_questoes=form.embaralhar_questoes.data,
                    criado_por=current_user.id,
                    questoes=previa,
                )
                db.session.add(teste)
                db.session.commit()
                flash(f'Teste criado com {len(previa)} questões para {destino}.', 'success')
                return redirect(url_for('professor.testes'))

    return render_template('professor/teste_gerar.html', form=form, turma=turma, destino=destino, previa=previa,
                           questoes_ativas=questoes_ativas, disponibilidade=sorteio.disponibilidade(),
                           niveis=NIVEIS_DIFICULDADE)


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
        teste.embaralhar_questoes = form.embaralhar_questoes.data
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

def _testes_do_professor():
    """Testes de que o professor é responsável (quem criou). O administrador vê todos."""
    consulta = Teste.query
    if not current_user.eh_administrador:
        consulta = consulta.filter(Teste.criado_por == current_user.id)
    return consulta.order_by(Teste.criado_em.desc(), Teste.id.desc()).all()


def _teste_do_professor(teste_id):
    teste = db.get_or_404(Teste, teste_id)
    if not (current_user.eh_administrador or teste.criado_por == current_user.id):
        abort(403)
    return teste


def _alunos_por_perfil(analise):
    """Refaz por código o agrupamento usado na análise (mesmas tentativas, até a última resposta
    considerada) para mostrar ao professor quem está em cada perfil. Os nomes não vão ao agente."""
    por_tentativa = estatisticas.acerto_por_assunto_por_tentativa(analise.teste_id,
                                                                  ate=analise.data_ultima_resposta)
    perfis = classificacao.agrupar_por_necessidade(por_tentativa)
    tentativas = {t.id: t for t in Tentativa.query.filter(
        Tentativa.id.in_([i for perfil in perfis for i in perfil['tentativas']])).all()}
    return {perfil['codigo']: sorted(tentativas[i].aluno.nome_completo for i in perfil['tentativas'] if i in tentativas)
            for perfil in perfis}


@bp.route('/orientacoes-nivelamento')
@perfil_requerido(PERFIL_PROFESSOR)
def orientacoes_nivelamento():
    """Análise do agente para o teste selecionado (o mais recente, por padrão). Só lê do banco."""
    testes = _testes_do_professor()
    teste_id = request.args.get('teste_id', type=int)
    teste = _teste_do_professor(teste_id) if teste_id else (testes[0] if testes else None)
    contexto = {'testes': testes, 'teste': teste, 'form': FlaskForm(), 'minimo': feedback_turma.MIN_RESPOSTAS,
                'faixas': classificacao.FAIXAS, 'descrever': feedback_turma.descrever}
    if teste:
        analises = feedback_turma.historico(teste.id)
        valida = next((analise for analise in analises if analise.pronto), None)
        estado = estatisticas.estado_respostas_teste(teste.id)
        contexto.update(
            estado=estado,
            mais_recente=analises[0] if analises else None,
            valida=valida,
            novas_respostas=max(estado['quantidade'] - valida.qtd_respostas, 0) if valida else 0,
            alunos_por_perfil=_alunos_por_perfil(valida) if valida else {},
            anteriores=[analise for analise in analises if analise is not valida],
        )
    return render_template('professor/orientacoes.html', **contexto)


@bp.route('/testes/<int:teste_id>/analise')
@perfil_requerido(PERFIL_PROFESSOR)
def analise_teste(teste_id):
    """Análise mais recente do teste, lida do banco (nunca chama o agente)."""
    analise = feedback_turma.analise_mais_recente(_teste_do_professor(teste_id).id)
    if analise is None:
        return jsonify(status=None)
    return jsonify(status=analise.status, gatilho=analise.gatilho, modelo=analise.modelo,
                   qtd_respostas=analise.qtd_respostas, criado_em=analise.criado_em.isoformat(),
                   descricao=feedback_turma.descrever(analise), resultado=analise.resultado)


@bp.route('/testes/<int:teste_id>/analise/atualizar', methods=['POST'])
@perfil_requerido(PERFIL_PROFESSOR)
def atualizar_analise_teste(teste_id):
    """Botão "Atualizar análise": verifica se há respostas novas antes de gerar.
    Com forcar=true (após a confirmação do professor), gera mesmo sem mudanças."""
    teste = _teste_do_professor(teste_id)
    dados = request.get_json(silent=True) or {}
    forcar = dados.get('forcar') is True or request.form.get('forcar') == 'true'
    try:
        resposta = feedback_turma.solicitar_analise(teste, forcar=forcar)
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Falha ao solicitar a análise do teste %s.', teste.id)
        return jsonify(situacao='erro', mensagem='Não foi possível iniciar a análise agora. Tente novamente.'), 500
    return jsonify(resposta)
