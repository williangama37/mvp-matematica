"""Classificação por competência (assunto), feita por código e não pelo modelo.

Os percentuais vêm do módulo de estatísticas; aqui só se aplica a regra de domínio, se
compara com a tentativa anterior (aluno) e se agregam os alunos de um teste (turma).
O resultado é o único dado de desempenho enviado aos agentes e não contém dados pessoais."""
from collections import Counter

from app import estatisticas

# Percentual de acerto a partir do qual a competência é considerada dominada.
LIMIAR_DOMINIO = 70
# Diferenças menores que isso (em pontos percentuais) contam como "manteve".
TOLERANCIA_VARIACAO = 5
# Quantas tentativas anteriores, resumidas, acompanham a classificação.
MAX_TENTATIVAS_ANTERIORES = 2

DOMINA = 'domina'
PRECISA_ESTUDAR = 'precisa_estudar'
CLASSIFICACOES = {DOMINA: 'Domina', PRECISA_ESTUDAR: 'Precisa estudar'}

# Faixas de acerto, as mesmas da legenda dos dashboards (crítico / em desenvolvimento / adequado).
FAIXAS = [
    ('critico', 'Crítico (0–49%)', 0),
    ('em_desenvolvimento', 'Em desenvolvimento (50–69%)', 50),
    ('adequado', f'Adequado ({LIMIAR_DOMINIO}–100%)', LIMIAR_DOMINIO),
]
# Perfis de necessidade enviados à análise da turma; combinações além disso viram "outras combinações".
MAX_PERFIS = 6

MELHOROU = 'melhorou'
MANTEVE = 'manteve'
PIOROU = 'piorou'
VARIACOES = {MELHOROU: 'Melhorou', MANTEVE: 'Manteve', PIOROU: 'Piorou'}


def classificar(percentual):
    return DOMINA if percentual >= LIMIAR_DOMINIO else PRECISA_ESTUDAR


def variacao(percentual_atual, percentual_anterior):
    diferenca = percentual_atual - percentual_anterior
    if diferenca >= TOLERANCIA_VARIACAO:
        return MELHOROU
    if diferenca <= -TOLERANCIA_VARIACAO:
        return PIOROU
    return MANTEVE


def classificar_competencias(por_assunto):
    """Recebe a saída de estatisticas.acerto_por_assunto (de um aluno, tentativa ou turma)."""
    return [
        {'competencia': item['assunto'], 'acertos': item['acertos'], 'total': item['total'],
         'percentual': item['percentual'], 'classificacao': classificar(item['percentual'])}
        for item in por_assunto
    ]


def _resumo_tentativa(tentativa):
    competencias = classificar_competencias(estatisticas.acerto_por_assunto(tentativa_id=tentativa.id))
    for item in competencias:
        # Numa tentativa, o total de respostas do assunto é o número de questões dele no teste.
        item['amostra_pequena'] = estatisticas.amostra_pequena(item['total'])
    return {
        'teste': tentativa.teste.titulo,
        'data': tentativa.finalizada_em.strftime('%d/%m/%Y'),
        'percentual': tentativa.percentual_acerto,
        'competencias': competencias,
    }


def _historico_por_assunto(tentativa):
    """{assunto: avaliações anteriores do mesmo assunto, da mais antiga para a mais recente}, a partir
    da evolução por teste do aluno. Considera só testes concluídos antes deste e guarda no máximo
    MAX_TENTATIVAS_ANTERIORES avaliações por assunto."""
    evolucao = estatisticas.evolucao_por_teste(aluno_id=tentativa.aluno_id, ate=tentativa.finalizada_em)
    anteriores = [i for i, teste_id in enumerate(evolucao['teste_ids']) if teste_id != tentativa.teste_id]
    historico = {}
    for assunto, pontos in evolucao['assuntos'].items():
        avaliacoes = [{'teste': evolucao['rotulos'][i], **pontos[i],
                       'amostra_pequena': estatisticas.amostra_pequena(pontos[i]['total'])}
                      for i in anteriores if pontos[i] is not None]
        if avaliacoes:
            historico[assunto] = avaliacoes[-MAX_TENTATIVAS_ANTERIORES:]
    return historico


def _erros_por_assunto(tentativa):
    """{assunto: questões que o aluno errou ou deixou em branco nesta tentativa}, com a alternativa
    marcada e o raciocínio equivocado que ela representa. É o que permite ao agente apontar por onde
    começar a estudar dentro do assunto, e não só qual assunto revisar."""
    erros = {}
    for resposta in tentativa.respostas:
        if resposta.correta:
            continue
        questao, marcada = resposta.questao, resposta.alternativa
        erros.setdefault(questao.assunto.nome, []).append({
            'enunciado': questao.enunciado,
            'dificuldade': questao.nome_dificuldade,
            'alternativa_marcada': _texto_alternativa(marcada) if marcada else 'Em branco',
            'alternativa_correta': _texto_alternativa(questao.alternativa_correta),
            'raciocinio_equivocado': (marcada.descricao_distrator or '') if marcada else '',
            'tipo_erro': marcada.nome_tipo_erro if marcada else 'Em branco',
        })
    return erros


def classificar_tentativa(tentativa):
    """Resumo de uma tentativa: competências classificadas, prioridade de estudo e, em cada uma, o
    histórico do mesmo assunto e a variação em relação à última vez em que ele foi avaliado (mesmo
    que não tenha caído no teste imediatamente anterior), mais as tentativas anteriores resumidas.
    As competências a estudar trazem também as questões erradas nesta tentativa."""
    atual = _resumo_tentativa(tentativa)
    anteriores = [_resumo_tentativa(item) for item in
                  estatisticas.tentativas_anteriores(tentativa, limite=MAX_TENTATIVAS_ANTERIORES)]
    historico = _historico_por_assunto(tentativa)
    erros = _erros_por_assunto(tentativa)

    for item in atual['competencias']:
        avaliacoes = historico.get(item['competencia'], [])
        ultima = avaliacoes[-1] if avaliacoes else None
        item['historico'] = avaliacoes
        item['teste_anterior'] = ultima['teste'] if ultima else None
        item['percentual_anterior'] = ultima['percentual'] if ultima else None
        item['variacao'] = variacao(item['percentual'], ultima['percentual']) if ultima else None
        if item['classificacao'] == PRECISA_ESTUDAR:
            item['erros'] = erros.get(item['competencia'], [])

    # Prioridade de estudo: menor acerto primeiro; no empate, o que piorou vem antes.
    a_estudar = sorted((item for item in atual['competencias'] if item['classificacao'] == PRECISA_ESTUDAR),
                       key=lambda item: (item['percentual'], item['variacao'] != PIOROU))
    for posicao, item in enumerate(a_estudar, start=1):
        item['prioridade'] = posicao

    atual['limiar_dominio'] = LIMIAR_DOMINIO
    atual['min_questoes'] = estatisticas.MIN_QUESTOES_PONTO
    atual['anteriores'] = anteriores
    return atual


# --------------------------------------------------------------------- Turma (um teste)

def faixa(percentual):
    return next(chave for chave, _, minimo in reversed(FAIXAS) if percentual >= minimo)


def _distribuicao(percentuais):
    """Quantos alunos (e que percentual deles) caem em cada faixa."""
    contagem = {chave: 0 for chave, _, _ in FAIXAS}
    for valor in percentuais:
        contagem[faixa(valor)] += 1
    return {chave: {'alunos': qtd, 'percentual': estatisticas.percentual(qtd, len(percentuais))}
            for chave, qtd in contagem.items()}


def _contagem(parte, total):
    return {'alunos': parte, 'percentual': estatisticas.percentual(parte, total)}


def agrupar_por_necessidade(por_tentativa):
    """Agrupa as tentativas pelo conjunto exato de competências em que o aluno precisa estudar.
    Recebe {tentativa_id: acerto_por_assunto} e devolve os perfis em ordem determinística (maiores
    grupos primeiro), com os ids das tentativas, para a tela do professor identificar os alunos."""
    grupos = {}
    for tentativa_id, competencias in por_tentativa.items():
        chave = tuple(sorted(item['assunto'] for item in competencias
                             if classificar(item['percentual']) == PRECISA_ESTUDAR))
        grupos.setdefault(chave, []).append(tentativa_id)
    ordenados = sorted(grupos.items(), key=lambda grupo: (-len(grupo[1]), len(grupo[0]), grupo[0]))

    perfis = [{'codigo': f'P{posicao}', 'precisa_estudar': list(chave), 'outras_combinacoes': False,
               'tentativas': sorted(ids)}
              for posicao, (chave, ids) in enumerate(ordenados[:MAX_PERFIS], start=1)]
    if len(ordenados) > MAX_PERFIS:
        restantes = ordenados[MAX_PERFIS:]
        perfis.append({'codigo': 'OUTROS', 'outras_combinacoes': True,
                       'precisa_estudar': sorted({nome for chave, _ in restantes for nome in chave}),
                       'tentativas': sorted(i for _, ids in restantes for i in ids)})
    return perfis


def classificar_teste(teste, estado=None):
    """Dados agregados e anônimos do desempenho da turma em um teste, para a análise do professor.
    Não contém nomes, e-mails nem identificadores de alunos ou tentativas. `estado` é o de
    estatisticas.estado_respostas_teste: só entram as tentativas concluídas até a última resposta dele."""
    estado = estado or estatisticas.estado_respostas_teste(teste.id)
    tentativas = estatisticas.tentativas_do_teste(teste.id, ate=estado['ultima_resposta'])
    por_tentativa = estatisticas.acerto_por_assunto_por_tentativa(teste.id, ate=estado['ultima_resposta'])
    total_alunos = len(tentativas)
    questoes_por_assunto = Counter(questao.assunto.nome for questao in teste.questoes)

    competencias = []
    for item in classificar_competencias(estatisticas.acerto_por_assunto(teste_id=teste.id)):
        percentuais = [c['percentual'] for lista in por_tentativa.values() for c in lista
                       if c['assunto'] == item['competencia']]
        dominam = sum(1 for valor in percentuais if classificar(valor) == DOMINA)
        questoes = questoes_por_assunto[item['competencia']]
        competencias.append({
            'competencia': item['competencia'],
            'percentual_acerto': item['percentual'],
            # Poucas questões no assunto deixam a classificação de cada aluno instável.
            'questoes': questoes,
            'amostra_pequena': estatisticas.amostra_pequena(questoes),
            'respostas': item['total'],
            'alunos_avaliados': len(percentuais),
            'alunos_domina': _contagem(dominam, len(percentuais)),
            'alunos_precisa_estudar': _contagem(len(percentuais) - dominam, len(percentuais)),
            'distribuicao_faixas': _distribuicao(percentuais),
        })
    # Prioridade pelos dados: mais alunos precisando estudar primeiro; no empate, menor acerto.
    ordem = sorted(competencias, key=lambda c: (-c['alunos_precisa_estudar']['percentual'], c['percentual_acerto']))
    for posicao, item in enumerate(ordem, start=1):
        item['prioridade_pelos_dados'] = posicao

    perfis = [{'codigo': perfil['codigo'], 'precisa_estudar': perfil['precisa_estudar'],
               'outras_combinacoes': perfil['outras_combinacoes'],
               **_contagem(len(perfil['tentativas']), total_alunos)}
              for perfil in agrupar_por_necessidade(por_tentativa)]

    return {
        'teste': teste.titulo,
        'total_questoes': len(teste.questoes),
        'total_alunos': total_alunos,
        'limiar_dominio': LIMIAR_DOMINIO,
        'min_questoes': estatisticas.MIN_QUESTOES_PONTO,
        'faixas': {chave: rotulo for chave, rotulo, _ in FAIXAS},
        'desempenho_geral': {
            'percentual_medio': estatisticas.percentual(sum(t.total_acertos for t in tentativas),
                                                        sum(t.total_questoes for t in tentativas)),
            'distribuicao_faixas': _distribuicao([t.percentual_acerto for t in tentativas]),
        },
        'competencias': competencias,
        'perfis': perfis,
        'questoes_mais_erradas': [
            {'competencia': item['questao'].assunto.nome, 'enunciado': item['questao'].enunciado,
             'alternativa_correta': _texto_alternativa(item['questao'].alternativa_correta),
             'erros': item['erros'], 'respostas': item['total'], 'percentual_erro': item['percentual_erro']}
            for item in estatisticas.questoes_mais_erradas(teste.id)
        ],
        'alternativas_erradas_frequentes': [
            {'competencia': item['questao'].assunto.nome, 'enunciado': item['questao'].enunciado,
             'alternativa': _texto_alternativa(item['alternativa']),
             'raciocinio_equivocado': item['alternativa'].descricao_distrator or '',
             'tipo_erro': item['alternativa'].nome_tipo_erro, 'escolhas': item['vezes'],
             'percentual_alunos': estatisticas.percentual(item['vezes'], total_alunos)}
            for item in estatisticas.distratores_frequentes(teste_id=teste.id, limite=8)
        ],
        'erros_por_tipo': estatisticas.erros_por_tipo(teste_id=teste.id),
    }


def _texto_alternativa(alternativa):
    return f'{alternativa.letra}) {alternativa.texto}' if alternativa else None
