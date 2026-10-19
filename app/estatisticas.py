"""Cálculos usados nos dashboards.

Fica separado das rotas para que os agentes de IA (Agno) possam reaproveitar
os mesmos dados de diagnóstico quando forem implementados."""
import unicodedata

from sqlalchemy import func, case
from app import db
from app.models import (Usuario, Questao, Alternativa, Assunto, Teste, Tentativa, Resposta,
                        PERFIL_ALUNO, TIPOS_ERRO)


def _percentual(parte, total):
    return round(100 * parte / total, 1) if total else 0


# Versão pública, para os agentes calcularem percentuais com o mesmo arredondamento dos dashboards.
percentual = _percentual


def _filtrar_respostas(consulta, turma_id=None, aluno_id=None, tentativa_id=None, teste_id=None):
    consulta = consulta.join(Tentativa, Resposta.tentativa_id == Tentativa.id)
    if teste_id:
        consulta = consulta.filter(Tentativa.teste_id == teste_id, Tentativa.finalizada_em.isnot(None))
    if tentativa_id:
        consulta = consulta.filter(Tentativa.id == tentativa_id)
    elif aluno_id:
        consulta = consulta.filter(Tentativa.aluno_id == aluno_id)
    elif turma_id:
        consulta = consulta.join(Usuario, Tentativa.aluno_id == Usuario.id).filter(Usuario.turma_id == turma_id)
    return consulta


def _filtrar_tentativas(consulta, turma_id=None, aluno_id=None):
    consulta = consulta.filter(Tentativa.finalizada_em.isnot(None))
    if aluno_id:
        consulta = consulta.filter(Tentativa.aluno_id == aluno_id)
    elif turma_id:
        consulta = consulta.join(Usuario, Tentativa.aluno_id == Usuario.id).filter(Usuario.turma_id == turma_id)
    return consulta


def acerto_por_assunto(turma_id=None, aluno_id=None, tentativa_id=None, teste_id=None):
    """Desempenho por competência (assunto). Com tentativa_id ou teste_id, considera só aquela
    tentativa ou as respostas daquele teste."""
    acertos = func.sum(case((Resposta.correta.is_(True), 1), else_=0))
    consulta = db.session.query(Assunto.nome, acertos, func.count(Resposta.id)) \
        .select_from(Resposta) \
        .join(Questao, Resposta.questao_id == Questao.id) \
        .join(Assunto, Questao.assunto_id == Assunto.id)
    consulta = _filtrar_respostas(consulta, turma_id, aluno_id, tentativa_id, teste_id)
    linhas = consulta.group_by(Assunto.id).order_by(Assunto.nome).all()
    return [
        {'assunto': nome, 'acertos': int(qtd_acertos or 0), 'total': total,
         'percentual': _percentual(qtd_acertos or 0, total)}
        for nome, qtd_acertos, total in linhas
    ]


def erros_por_tipo(turma_id=None, aluno_id=None, teste_id=None):
    consulta = db.session.query(Alternativa.tipo_erro, func.count(Resposta.id)) \
        .select_from(Resposta) \
        .join(Alternativa, Resposta.alternativa_id == Alternativa.id) \
        .filter(Resposta.correta.is_(False))
    consulta = _filtrar_respostas(consulta, turma_id, aluno_id, teste_id=teste_id)
    linhas = consulta.group_by(Alternativa.tipo_erro).order_by(func.count(Resposta.id).desc()).all()
    return [{'tipo': TIPOS_ERRO.get(tipo, 'Não classificado'), 'quantidade': quantidade}
            for tipo, quantidade in linhas]


def distratores_frequentes(turma_id=None, aluno_id=None, limite=10, teste_id=None):
    """Distratores mais escolhidos: mostram exatamente qual raciocínio equivocado aparece mais."""
    consulta = db.session.query(Alternativa, func.count(Resposta.id).label('vezes')) \
        .select_from(Resposta) \
        .join(Alternativa, Resposta.alternativa_id == Alternativa.id) \
        .filter(Resposta.correta.is_(False))
    consulta = _filtrar_respostas(consulta, turma_id, aluno_id, teste_id=teste_id)
    linhas = consulta.group_by(Alternativa.id).order_by(func.count(Resposta.id).desc()).limit(limite).all()
    return [{'alternativa': alternativa, 'questao': alternativa.questao, 'vezes': vezes}
            for alternativa, vezes in linhas]


# Nos gráficos de evolução, pontos calculados com menos questões que isso aparecem destacados
# (amostra pequena: com 1 ou 2 questões o percentual salta entre 0, 50 e 100%).
MIN_QUESTOES_PONTO = 3


def _ordem_alfabetica(texto):
    """Ordena ignorando acentos e maiúsculas ("Álgebra" antes de "Funções")."""
    return unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode().casefold()


def _ponto(acertos, total):
    return {'percentual': _percentual(acertos, total), 'acertos': acertos, 'total': total}


def amostra_pequena(questoes):
    return questoes < MIN_QUESTOES_PONTO


def evolucao_por_teste(turma_id=None, aluno_id=None, ate=None):
    """Acerto teste a teste, em ordem de aplicação: no geral e em cada assunto.
    Para o aluno, cada teste é a sua tentativa; para a turma (ou todos), soma as respostas dos alunos.
    Cada ponto traz acertos e total, para o gráfico mostrar o tamanho da amostra; None indica que
    o assunto não foi avaliado naquele teste. Com `ate`, considera só as tentativas concluídas até
    essa data (ex.: ao gerar de novo o feedback de um teste antigo)."""
    acertos = func.sum(case((Resposta.correta.is_(True), 1), else_=0))
    consulta = db.session.query(Teste.id, Teste.titulo, Assunto.nome, acertos, func.count(Resposta.id),
                                func.min(Tentativa.finalizada_em)) \
        .select_from(Resposta) \
        .join(Questao, Resposta.questao_id == Questao.id) \
        .join(Assunto, Questao.assunto_id == Assunto.id)
    consulta = _filtrar_respostas(consulta, turma_id, aluno_id) \
        .join(Teste, Tentativa.teste_id == Teste.id) \
        .filter(Tentativa.finalizada_em.isnot(None))
    if ate:
        consulta = consulta.filter(Tentativa.finalizada_em <= ate)

    testes = {}
    for teste_id, titulo, assunto, qtd_acertos, total, inicio in consulta.group_by(Teste.id, Assunto.id).all():
        teste = testes.setdefault(teste_id, {'titulo': titulo, 'inicio': inicio, 'assuntos': {}})
        teste['inicio'] = min(teste['inicio'], inicio)
        teste['assuntos'][assunto] = (int(qtd_acertos or 0), total)
    ordem = sorted(testes.items(), key=lambda item: (item[1]['inicio'], item[0]))
    nomes = sorted({nome for _, teste in ordem for nome in teste['assuntos']}, key=_ordem_alfabetica)

    return {
        'teste_ids': [teste_id for teste_id, _ in ordem],
        'rotulos': [f'{teste["titulo"]} ({teste["inicio"]:%d/%m})' for _, teste in ordem],
        'geral': [_ponto(sum(a for a, _ in teste['assuntos'].values()), sum(t for _, t in teste['assuntos'].values()))
                  for _, teste in ordem],
        'assuntos': {nome: [_ponto(*teste['assuntos'][nome]) if nome in teste['assuntos'] else None
                            for _, teste in ordem]
                     for nome in nomes},
        'min_questoes': MIN_QUESTOES_PONTO,
    }


def tentativas_anteriores(tentativa, limite=None):
    """Tentativas finalizadas do mesmo aluno antes da informada, da mais recente para a mais antiga."""
    consulta = Tentativa.query.filter(Tentativa.aluno_id == tentativa.aluno_id, Tentativa.id != tentativa.id,
                                      Tentativa.finalizada_em.isnot(None),
                                      Tentativa.finalizada_em <= tentativa.finalizada_em) \
        .order_by(Tentativa.finalizada_em.desc(), Tentativa.id.desc())
    return consulta.limit(limite).all() if limite else consulta.all()


def estado_respostas_teste(teste_id):
    """Quantidade de tentativas finalizadas do teste e a data/hora da mais recente.
    Serve para saber se chegaram respostas novas desde a última análise da turma."""
    quantidade, ultima = db.session.query(func.count(Tentativa.id), func.max(Tentativa.finalizada_em))         .filter(Tentativa.teste_id == teste_id, Tentativa.finalizada_em.isnot(None)).one()
    return {'quantidade': quantidade or 0, 'ultima_resposta': ultima}


def tentativas_do_teste(teste_id, ate=None):
    """Tentativas finalizadas do teste (até a data informada), da mais antiga para a mais recente."""
    consulta = Tentativa.query.filter(Tentativa.teste_id == teste_id, Tentativa.finalizada_em.isnot(None))
    if ate:
        consulta = consulta.filter(Tentativa.finalizada_em <= ate)
    return consulta.order_by(Tentativa.finalizada_em, Tentativa.id).all()


def acerto_por_assunto_por_tentativa(teste_id, ate=None):
    """Desempenho de cada tentativa do teste em cada competência: {tentativa_id: acerto_por_assunto}.
    Base para distribuições e agrupamentos de alunos feitos por código."""
    acertos = func.sum(case((Resposta.correta.is_(True), 1), else_=0))
    consulta = db.session.query(Tentativa.id, Assunto.nome, acertos, func.count(Resposta.id))         .select_from(Resposta)         .join(Questao, Resposta.questao_id == Questao.id)         .join(Assunto, Questao.assunto_id == Assunto.id)
    consulta = _filtrar_respostas(consulta, teste_id=teste_id)
    if ate:
        consulta = consulta.filter(Tentativa.finalizada_em <= ate)
    por_tentativa = {}
    for tentativa_id, nome, qtd_acertos, total in consulta.group_by(Tentativa.id, Assunto.id)             .order_by(Tentativa.id, Assunto.nome).all():
        por_tentativa.setdefault(tentativa_id, []).append(
            {'assunto': nome, 'acertos': int(qtd_acertos or 0), 'total': total,
             'percentual': _percentual(qtd_acertos or 0, total)})
    return por_tentativa


def questoes_mais_erradas(teste_id, limite=5):
    """Questões do teste com maior percentual de erro (inclui respostas em branco)."""
    erros = func.sum(case((Resposta.correta.is_(False), 1), else_=0))
    consulta = db.session.query(Questao, erros, func.count(Resposta.id))         .select_from(Resposta)         .join(Questao, Resposta.questao_id == Questao.id)
    consulta = _filtrar_respostas(consulta, teste_id=teste_id)
    linhas = consulta.group_by(Questao.id).all()
    linhas = sorted(((questao, int(qtd_erros or 0), total) for questao, qtd_erros, total in linhas if qtd_erros),
                    key=lambda linha: (-linha[1] / linha[2], -linha[1], linha[0].id))
    return [{'questao': questao, 'erros': qtd_erros, 'total': total, 'percentual_erro': _percentual(qtd_erros, total)}
            for questao, qtd_erros, total in linhas[:limite]]


def resumo_tentativas(turma_id=None, aluno_id=None):
    consulta = db.session.query(func.count(Tentativa.id), func.sum(Tentativa.total_acertos),
                                func.sum(Tentativa.total_questoes))
    quantidade, acertos, total = _filtrar_tentativas(consulta, turma_id, aluno_id).one()
    return {'quantidade': quantidade or 0, 'media_acerto': _percentual(acertos or 0, total or 0)}


def desempenho_alunos(turma_id=None):
    acertos = func.coalesce(func.sum(Tentativa.total_acertos), 0)
    total = func.coalesce(func.sum(Tentativa.total_questoes), 0)
    consulta = db.session.query(Usuario, func.count(Tentativa.id), acertos, total,
                                func.max(Tentativa.finalizada_em)) \
        .outerjoin(Tentativa, (Tentativa.aluno_id == Usuario.id) & Tentativa.finalizada_em.isnot(None)) \
        .filter(Usuario.perfil == PERFIL_ALUNO)
    if turma_id:
        consulta = consulta.filter(Usuario.turma_id == turma_id)
    linhas = consulta.group_by(Usuario.id).order_by(Usuario.nome_completo).all()
    return [
        {'aluno': aluno, 'testes_realizados': qtd, 'media_acerto': _percentual(qtd_acertos, qtd_total) if qtd else None,
         'ultimo_teste': ultimo}
        for aluno, qtd, qtd_acertos, qtd_total, ultimo in linhas
    ]


def dashboard_geral(turma_id=None):
    alunos = Usuario.query.filter_by(perfil=PERFIL_ALUNO)
    if turma_id:
        alunos = alunos.filter_by(turma_id=turma_id)
    testes = Teste.query
    if turma_id:
        testes = testes.filter((Teste.turma_id == turma_id) | (Teste.turma_id.is_(None)))

    resumo = resumo_tentativas(turma_id)
    return {
        'total_alunos': alunos.count(),
        'total_questoes': Questao.query.filter_by(ativa=True).count(),
        'total_testes': testes.count(),
        'total_tentativas': resumo['quantidade'],
        'media_acerto': resumo['media_acerto'],
        'acerto_por_assunto': acerto_por_assunto(turma_id),
        'erros_por_tipo': erros_por_tipo(turma_id),
        'distratores': distratores_frequentes(turma_id),
        'evolucao': evolucao_por_teste(turma_id=turma_id),
        'alunos': desempenho_alunos(turma_id),
    }


def dashboard_aluno(aluno):
    resumo = resumo_tentativas(aluno_id=aluno.id)
    por_assunto = acerto_por_assunto(aluno_id=aluno.id)
    ordenados = sorted(por_assunto, key=lambda item: item['percentual'])
    return {
        'aluno': aluno,
        'total_tentativas': resumo['quantidade'],
        'media_acerto': resumo['media_acerto'],
        'assunto_mais_fraco': ordenados[0] if ordenados else None,
        'assunto_mais_forte': ordenados[-1] if ordenados else None,
        'acerto_por_assunto': por_assunto,
        'erros_por_tipo': erros_por_tipo(aluno_id=aluno.id),
        'distratores': distratores_frequentes(aluno_id=aluno.id),
        'evolucao': evolucao_por_teste(aluno_id=aluno.id),
        'tentativas': Tentativa.query.filter(Tentativa.aluno_id == aluno.id, Tentativa.finalizada_em.isnot(None))
            .order_by(Tentativa.finalizada_em.desc()).all(),
    }
