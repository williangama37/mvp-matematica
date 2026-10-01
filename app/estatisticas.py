"""Cálculos usados nos dashboards.

Fica separado das rotas para que os agentes de IA (Agno) possam reaproveitar
os mesmos dados de diagnóstico quando forem implementados."""
from sqlalchemy import func, case
from app import db
from app.models import (Usuario, Questao, Alternativa, Assunto, Teste, Tentativa, Resposta,
                        PERFIL_ALUNO, TIPOS_ERRO)


def _percentual(parte, total):
    return round(100 * parte / total, 1) if total else 0


def _filtrar_respostas(consulta, turma_id=None, aluno_id=None):
    consulta = consulta.join(Tentativa, Resposta.tentativa_id == Tentativa.id)
    if aluno_id:
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


def acerto_por_assunto(turma_id=None, aluno_id=None):
    acertos = func.sum(case((Resposta.correta.is_(True), 1), else_=0))
    consulta = db.session.query(Assunto.nome, acertos, func.count(Resposta.id)) \
        .select_from(Resposta) \
        .join(Questao, Resposta.questao_id == Questao.id) \
        .join(Assunto, Questao.assunto_id == Assunto.id)
    consulta = _filtrar_respostas(consulta, turma_id, aluno_id)
    linhas = consulta.group_by(Assunto.id).order_by(Assunto.nome).all()
    return [
        {'assunto': nome, 'acertos': int(qtd_acertos or 0), 'total': total,
         'percentual': _percentual(qtd_acertos or 0, total)}
        for nome, qtd_acertos, total in linhas
    ]


def erros_por_tipo(turma_id=None, aluno_id=None):
    consulta = db.session.query(Alternativa.tipo_erro, func.count(Resposta.id)) \
        .select_from(Resposta) \
        .join(Alternativa, Resposta.alternativa_id == Alternativa.id) \
        .filter(Resposta.correta.is_(False))
    consulta = _filtrar_respostas(consulta, turma_id, aluno_id)
    linhas = consulta.group_by(Alternativa.tipo_erro).order_by(func.count(Resposta.id).desc()).all()
    return [{'tipo': TIPOS_ERRO.get(tipo, 'Não classificado'), 'quantidade': quantidade}
            for tipo, quantidade in linhas]


def distratores_frequentes(turma_id=None, aluno_id=None, limite=10):
    """Distratores mais escolhidos: mostram exatamente qual raciocínio equivocado aparece mais."""
    consulta = db.session.query(Alternativa, func.count(Resposta.id).label('vezes')) \
        .select_from(Resposta) \
        .join(Alternativa, Resposta.alternativa_id == Alternativa.id) \
        .filter(Resposta.correta.is_(False))
    consulta = _filtrar_respostas(consulta, turma_id, aluno_id)
    linhas = consulta.group_by(Alternativa.id).order_by(func.count(Resposta.id).desc()).limit(limite).all()
    return [{'alternativa': alternativa, 'questao': alternativa.questao, 'vezes': vezes}
            for alternativa, vezes in linhas]


def evolucao_por_data(turma_id=None):
    """Média de acerto da turma (ou geral) por dia de realização dos testes."""
    dia = func.date(Tentativa.finalizada_em)
    consulta = db.session.query(dia, func.sum(Tentativa.total_acertos), func.sum(Tentativa.total_questoes))
    consulta = _filtrar_tentativas(consulta, turma_id)
    linhas = consulta.group_by(dia).order_by(dia).all()
    return {
        'rotulos': [str(data) for data, _, _ in linhas],
        'valores': [_percentual(acertos or 0, total or 0) for _, acertos, total in linhas],
    }


def evolucao_aluno(aluno_id):
    tentativas = Tentativa.query.filter(Tentativa.aluno_id == aluno_id, Tentativa.finalizada_em.isnot(None)) \
        .order_by(Tentativa.finalizada_em).all()
    return {
        'rotulos': [f'{t.teste.titulo} ({t.finalizada_em:%d/%m})' for t in tentativas],
        'valores': [t.percentual_acerto for t in tentativas],
    }


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
        'evolucao': evolucao_por_data(turma_id),
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
        'evolucao': evolucao_aluno(aluno.id),
        'tentativas': Tentativa.query.filter(Tentativa.aluno_id == aluno.id, Tentativa.finalizada_em.isnot(None))
            .order_by(Tentativa.finalizada_em.desc()).all(),
    }
