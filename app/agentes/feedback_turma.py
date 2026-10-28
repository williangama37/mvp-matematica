"""Agente que orienta o professor a montar uma estratégia de nivelamento a partir do
desempenho da turma em um teste.

Os dados enviados são agregados e anônimos, calculados por código (classificacao.py, a
partir do módulo de estatísticas): acerto e distribuição por faixas em cada competência,
percentual de alunos que domina / precisa estudar, perfis de necessidade e erros mais
frequentes. O agente roda em segundo plano (execucao.py) e cada atualização cria um novo
FeedbackTurma, mantendo o histórico; as rotas apenas leem esses registros."""
import json
from typing import List

from agno.agent import Agent
from pydantic import BaseModel, Field

from app import estatisticas
from app.agentes import classificacao, comum, execucao
from app.models import FeedbackTurma, STATUS_PENDENTE, GATILHO_MANUAL, GATILHO_FORCADO

# Número mínimo de alunos que concluíram o teste para a análise fazer sentido.
MIN_RESPOSTAS = 5

# Resposta de solicitar_analise(), interpretada pela página do professor.
INICIADA = 'iniciada'
EM_ANDAMENTO = 'em_andamento'
SEM_MUDANCA = 'sem_mudanca'
RESPOSTAS_INSUFICIENTES = 'respostas_insuficientes'


class CompetenciaCritica(BaseModel):
    competencia: str = Field(description='Nome da competência exatamente como recebido.')
    evidencias: str = Field(description='Os dados que tornam a competência crítica (percentuais, faixas, erros).')
    foco: str = Field(description='O que trabalhar nela, a partir das questões e alternativas mais erradas.')


class PerfilGrupo(BaseModel):
    codigo: str = Field(description='Código do perfil exatamente como recebido (ex.: P1, P2, OUTROS).')
    titulo: str = Field(description='Nome curto do perfil, pela necessidade (ex.: "Base algébrica a consolidar").')
    descricao: str = Field(description='A necessidade do grupo descrita pelas competências, sem nomes de alunos.')
    encaminhamento: str = Field(description='Como atender esse grupo no nivelamento.')


class Estrategia(BaseModel):
    titulo: str
    descricao: str = Field(description='A atividade ou abordagem de nivelamento, de forma concreta.')
    competencias: List[str] = Field(description='Competências trabalhadas, com os nomes recebidos.')
    perfis: List[str] = Field(description='Códigos dos perfis atendidos.')
    justificativa: str = Field(description='Os dados que justificam esta estratégia.')


class EtapaSequencia(BaseModel):
    competencia: str = Field(description='Competência da etapa, com o nome recebido.')
    conteudos: str = Field(description='Conteúdos de pré-cálculo a trabalhar nesta etapa.')
    motivo: str = Field(description='Por que esta etapa vem nesta posição (pré-requisitos e dados).')


class AnaliseTurma(BaseModel):
    competencias_criticas: List[CompetenciaCritica] = Field(description='Em ordem de prioridade (mais urgente primeiro).')
    perfis_de_grupo: List[PerfilGrupo] = Field(description='Um item por perfil recebido.')
    estrategias: List[Estrategia]
    sequencia_sugerida: List[EtapaSequencia] = Field(description='Ordem sugerida dos conteúdos do nivelamento.')
    pontos_de_atencao: List[str]
    justificativa: str = Field(description='Um parágrafo que sintetiza os dados que sustentam a estratégia.')


INSTRUCOES = [
    'Você é um especialista em ensino de Matemática no ensino superior e apoia professores de pré-cálculo a '
    'planejar o nivelamento de calouros, em português do Brasil.',
    'Use um tom técnico e pedagógico, objetivo e dirigido ao professor, sem floreios.',
    'Baseie-se somente nos dados agregados recebidos (JSON). Não invente números, alunos nem competências. '
    'Justifique cada sugestão com os dados, citando-os (ex.: "62% dos alunos precisam estudar Funções; a '
    'alternativa B, escolhida por 40% da turma, revela confusão entre f(x+1) e f(x)+1").',
    'A classificação de cada aluno (domina a partir do limiar_dominio; abaixo, precisa estudar) e os perfis já '
    'foram calculados por código: não reclassifique nem refaça agrupamentos.',
    'competencias_criticas: as competências com maior necessidade, em ordem de prioridade. Parta de '
    'prioridade_pelos_dados e só mude a ordem por uma relação de pré-requisito, explicando-a nas evidências. '
    'Não inclua competências que a maioria domina, a menos que os dados mostrem um erro recorrente relevante.',
    'perfis_de_grupo: um item para cada perfil recebido, com o mesmo código. Descreva a necessidade pelas '
    'competências de precisa_estudar e indique o encaminhamento. O perfil sem competências a estudar pode '
    'ser aproveitado como monitoria ou aprofundamento.',
    'estrategias: de 3 a 6 atividades ou abordagens concretas de nivelamento (ex.: lista graduada de exercícios, '
    'discussão dos distratores mais escolhidos, trabalho em pares entre perfis complementares), indicando as '
    'competências e os perfis atendidos.',
    'sequencia_sugerida: a ordem dos conteúdos respeitando os pré-requisitos do pré-cálculo (ex.: frações e '
    'potências antes de expressões algébricas; álgebra antes de funções).',
    'pontos_de_atencao: limitações dos dados (ex.: poucas respostas, competência avaliada por poucas questões) '
    'e riscos pedagógicos a observar.',
    'Quando amostra_pequena for verdadeiro, a competência foi avaliada por poucas questões neste teste (menos que '
    'min_questoes): a classificação de cada aluno nela é instável. Trate os números dela como indício, não baseie '
    'sozinha uma prioridade alta nela e registre essa limitação em pontos_de_atencao.',
    'Use notação matemática em texto simples (ex.: x², √2, 3/4). Ao citar uma expressão de enunciado ou '
    'alternativa que esteja em LaTeX, mantenha-a exatamente como recebida, com os delimitadores $$...$$.',
]


def _criar_agente():
    return Agent(
        name='Análise da turma',
        model=comum.criar_modelo(),
        instructions=INSTRUCOES,
        # Sem variáveis de estado nas instruções: desligar o template do Agno evita que ele troque $$ por $.
        resolve_in_context=False,
        # Erros temporários (ex.: 503 "alta demanda") costumam passar em segundos: tenta de novo após 2s e 4s.
        retries=2,
        delay_between_retries=2,
        exponential_backoff=True,
        output_schema=AnaliseTurma,
    )


def _respeitar_dados(analise, dados):
    """Mantém só competências e perfis que existem nos dados (com os nomes e números calculados
    por código) e numera a prioridade das competências críticas."""
    competencias = {item['competencia'].casefold(): item['competencia'] for item in dados['competencias']}
    perfis = {perfil['codigo'].casefold(): perfil for perfil in dados['perfis']}

    def nome_competencia(nome):
        return competencias.get(nome.strip().casefold())

    criticas, vistas = [], set()
    for item in analise.competencias_criticas:
        nome = nome_competencia(item.competencia)
        if nome and nome not in vistas:
            vistas.add(nome)
            criticas.append({**item.model_dump(), 'competencia': nome, 'prioridade': len(criticas) + 1})

    perfis_de_grupo, vistos = [], set()
    for item in analise.perfis_de_grupo:
        perfil = perfis.get(item.codigo.strip().casefold())
        if perfil and perfil['codigo'] not in vistos:
            vistos.add(perfil['codigo'])
            perfis_de_grupo.append({**item.model_dump(), **perfil})
    perfis_de_grupo.sort(key=lambda item: [p['codigo'] for p in dados['perfis']].index(item['codigo']))

    estrategias = [
        {**item.model_dump(),
         'competencias': [nome for nome in map(nome_competencia, item.competencias) if nome],
         'perfis': [perfis[codigo.strip().casefold()]['codigo'] for codigo in item.perfis
                    if codigo.strip().casefold() in perfis]}
        for item in analise.estrategias
    ]
    sequencia = [{**item.model_dump(), 'competencia': nome_competencia(item.competencia) or item.competencia}
                 for item in analise.sequencia_sugerida]

    return {
        'competencias_criticas': criticas,
        'perfis_de_grupo': perfis_de_grupo,
        'estrategias': estrategias,
        'sequencia_sugerida': sequencia,
        'pontos_de_atencao': analise.pontos_de_atencao,
        'justificativa': analise.justificativa,
    }


def gerar_analise(dados):
    """Chama o agente com os dados agregados da turma. Retorna (resultado, id do modelo)."""
    pedido = ('Analise o desempenho da turma neste teste diagnóstico (JSON, dados agregados e anônimos) e '
              'proponha a estratégia de nivelamento.\n' + json.dumps(dados, ensure_ascii=False, indent=2))
    analise, modelo = comum.executar(_criar_agente(), pedido, AnaliseTurma)
    return _respeitar_dados(analise, dados), modelo


# --------------------------------------------------------------------- Consultas (somente leitura)

def _analises(teste_id):
    return FeedbackTurma.query.filter_by(teste_id=teste_id) \
        .order_by(FeedbackTurma.criado_em.desc(), FeedbackTurma.id.desc())


def analise_mais_recente(teste_id):
    return _analises(teste_id).first()


def historico(teste_id):
    return _analises(teste_id).all()


def descrever(analise, inicio='Gerada'):
    """'Gerada em DD/MM às HH:MM com N respostas'."""
    return f'{inicio} em {analise.criado_em:%d/%m} às {analise.criado_em:%H:%M} com {analise.qtd_respostas} respostas'


# --------------------------------------------------------------------- Gatilho manual

def _sem_mudanca(analise, estado):
    return (analise is not None and analise.pronto
            and analise.qtd_respostas == estado['quantidade']
            and analise.data_ultima_resposta == estado['ultima_resposta'])


def solicitar_analise(teste, forcar=False):
    """Verifica se a análise do teste deve ser gerada e, se sim, dispara o agente em segundo plano.
    Retorna {'situacao': ..., 'mensagem': ...} para a página do professor."""
    pendente = FeedbackTurma.query.filter_by(teste_id=teste.id, status=STATUS_PENDENTE).first()
    if pendente and not execucao.pendente_expirado(pendente):
        return {'situacao': EM_ANDAMENTO, 'mensagem': 'A análise deste teste já está em andamento.'}
    if pendente:
        execucao.marcar_erro(pendente)

    estado = estatisticas.estado_respostas_teste(teste.id)
    if estado['quantidade'] < MIN_RESPOSTAS:
        return {'situacao': RESPOSTAS_INSUFICIENTES,
                'mensagem': f'A análise precisa de pelo menos {MIN_RESPOSTAS} respostas; '
                            f'este teste tem {estado["quantidade"]} até agora.'}

    # Só pede confirmação quando a última análise está pronta e nada mudou; depois de um erro,
    # atualizar é uma nova tentativa.
    ultima = analise_mais_recente(teste.id)
    sem_mudanca = _sem_mudanca(ultima, estado)
    if sem_mudanca and not forcar:
        return {'situacao': SEM_MUDANCA,
                'mensagem': f'Nenhuma nova resposta desde a última análise ({descrever(ultima, "gerada")}). '
                            'Deseja atualizar mesmo assim?'}

    registro = execucao.criar_registro(
        FeedbackTurma, classificacao.classificar_teste(teste, estado),
        teste_id=teste.id, qtd_respostas=estado['quantidade'], data_ultima_resposta=estado['ultima_resposta'],
        gatilho=GATILHO_FORCADO if sem_mudanca else GATILHO_MANUAL)
    if registro is None:
        return {'situacao': EM_ANDAMENTO, 'mensagem': 'A análise deste teste já está em andamento.'}
    execucao.iniciar_em_segundo_plano(FeedbackTurma, registro.id, gerar_analise)
    return {'situacao': INICIADA, 'mensagem': 'Análise iniciada. Ela aparece aqui assim que ficar pronta.'}
