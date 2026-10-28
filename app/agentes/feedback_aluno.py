"""Agente que escreve o feedback do aluno ao concluir um teste.

A classificação por competência (domina / precisa estudar) e a variação em relação à
tentativa anterior são calculadas por código (classificacao.py). O agente só transforma
esse resumo em orientações; ele roda em segundo plano (execucao.py) e o resultado fica
salvo em FeedbackAluno, que as rotas apenas leem."""
import json
from typing import List

from agno.agent import Agent
from pydantic import BaseModel, Field

from app.agentes import classificacao, comum, execucao
from app.models import FeedbackAluno


class PontoForte(BaseModel):
    competencia: str = Field(description='Nome da competência exatamente como recebido.')
    comentario: str = Field(description='Uma frase reconhecendo o domínio, sem exageros.')


class ItemEstudo(BaseModel):
    competencia: str = Field(description='Nome da competência exatamente como recebido.')
    motivo: str = Field(description='Uma frase simples explicando por que vale revisar agora.')
    como_estudar: str = Field(
        description='Por onde começar, a partir dos erros recebidos: o ponto exato a revisar e que tipo de '
                    'exercício fazer.')


class FeedbackGerado(BaseModel):
    pontos_fortes: List[PontoForte] = Field(description='Somente as competências classificadas como "domina".')
    a_estudar: List[ItemEstudo] = Field(
        description='Somente as competências "precisa_estudar", na ordem do campo prioridade (1 primeiro).')
    evolucao: str = Field(description='Duas ou três frases sobre a evolução em relação às tentativas anteriores.')
    recomendacoes: List[str] = Field(description='De 2 a 4 dicas práticas e curtas de estudo.')
    mensagem: str = Field(description='Duas ou três frases de encorajamento para fechar o feedback.')


INSTRUCOES = [
    'Você é um tutor de Matemática que escreve, em português do Brasil, o feedback de um aluno calouro do ensino '
    'superior logo depois de um teste diagnóstico de pré-cálculo.',
    'Use um tom acolhedor e motivador, com linguagem simples e direta, falando com o aluno por "você". '
    'A nota não é um julgamento sobre o aluno: é um retrato do momento que mostra por onde continuar. '
    'Evite palavras como "fraco", "ruim" ou "fracasso".',
    'Use somente a classificação recebida, sem recalcular percentuais nem reavaliar: competências com '
    'classificacao "domina" vão em pontos_fortes; as "precisa_estudar" vão em a_estudar, na ordem do campo '
    'prioridade (1 é a mais urgente). Escreva o nome da competência exatamente como recebido.',
    'Em evolucao, use o campo variacao de cada competência (melhorou, manteve ou piorou). Ela compara com a última '
    'vez em que o mesmo assunto foi avaliado (teste_anterior), mesmo que não tenha sido no teste imediatamente '
    'anterior; historico traz até 2 avaliações anteriores do assunto, da mais antiga para a mais recente. '
    'Reconheça com clareza todo progresso. Se algo piorou, trate como parte normal do aprendizado e aponte o '
    'caminho. Competência sem histórico está sendo avaliada pela primeira vez: este teste é o ponto de partida dela.',
    'Quando amostra_pequena for verdadeiro, o percentual veio de poucas questões (menos que min_questoes): trate '
    'como um indício, não como conclusão, e não dê peso a grandes variações nessa competência (uma única questão '
    'muda muito o percentual). Ainda assim, mantenha a classificação recebida.',
    'Cada competência "precisa_estudar" traz em erros as questões que o aluno errou ou deixou em branco: '
    'enunciado, dificuldade, alternativa marcada, alternativa correta, raciocinio_equivocado (o raciocínio que '
    'leva àquela alternativa) e tipo_erro (conceitual, procedimental, de cálculo, de interpretação). '
    'Use esses dados para dizer por onde começar: em motivo, aponte o padrão de erro (ex.: "nas duas questões '
    'você distribuiu o expoente na soma"); em como_estudar, indique o ponto exato a revisar e um tipo de '
    'exercício que trabalhe esse erro. Erro conceitual pede rever a ideia antes de praticar; procedimental, '
    'praticar o passo a passo; de cálculo, refazer conferindo cada conta; de interpretação, reler o enunciado '
    'e traduzi-lo para a linguagem matemática antes de resolver. Se os erros forem nas questões fáceis, sugira '
    'começar pela base do assunto. Sem raciocinio_equivocado (ou em branco), compare a alternativa marcada com '
    'a correta sem afirmar o que o aluno pensou. Não copie o enunciado inteiro; cite só o essencial.',
    'Em como_estudar, seja concreto para o nível de pré-cálculo (ex.: "refaça exercícios de fatoração por '
    'evidência e produtos notáveis, conferindo cada passo"). Se não houver nada a estudar, deixe a_estudar vazio '
    'e sugira como aprofundar nas recomendações.',
    'Não invente dados que não estão no resumo e não compare o aluno com colegas. '
    'Use notação matemática em texto simples (ex.: x², √2, 3/4), sem LaTeX.',
]


def _criar_agente():
    return Agent(
        name='Feedback do aluno',
        model=comum.criar_modelo(),
        instructions=INSTRUCOES,
        # Sem variáveis de estado nas instruções: desligar o template do Agno evita que ele troque $$ por $.
        resolve_in_context=False,
        # Erros temporários (ex.: 503 "alta demanda") costumam passar em segundos: tenta de novo após 2s e 4s.
        retries=2,
        delay_between_retries=2,
        exponential_backoff=True,
        output_schema=FeedbackGerado,
    )


def _respeitar_classificacao(feedback, resumo):
    """Garante que o texto do agente segue a classificação feita por código: cada competência na
    lista certa, sem repetição, e a_estudar na ordem de prioridade calculada."""
    por_nome = {item['competencia'].casefold(): item for item in resumo['competencias']}

    def filtrar(itens, rotulo):
        vistos, filtrados = set(), []
        for item in itens:
            original = por_nome.get(item.competencia.strip().casefold())
            if original and original['classificacao'] == rotulo and original['competencia'] not in vistos:
                vistos.add(original['competencia'])
                filtrados.append({**item.model_dump(), 'competencia': original['competencia'],
                                  'prioridade': original.get('prioridade')})
        return filtrados

    a_estudar = sorted(filtrar(feedback.a_estudar, classificacao.PRECISA_ESTUDAR), key=lambda item: item['prioridade'])
    return {
        'pontos_fortes': [{'competencia': item['competencia'], 'comentario': item['comentario']}
                          for item in filtrar(feedback.pontos_fortes, classificacao.DOMINA)],
        'a_estudar': a_estudar,
        'evolucao': feedback.evolucao,
        'recomendacoes': feedback.recomendacoes,
        'mensagem': feedback.mensagem,
    }


def gerar_feedback(resumo):
    """Chama o agente com o resumo da classificação. Retorna (resultado, id do modelo)."""
    pedido = ('Escreva o feedback do aluno a partir deste resumo do teste (JSON). '
              '"anteriores" traz até 2 tentativas anteriores, da mais recente para a mais antiga.\n'
              + json.dumps(resumo, ensure_ascii=False, indent=2))
    feedback, modelo = comum.executar(_criar_agente(), pedido, FeedbackGerado)
    return _respeitar_classificacao(feedback, resumo), modelo


def agendar(tentativa, em_segundo_plano=True):
    """Classifica a tentativa, salva o feedback como 'pendente' e dispara o agente em segundo plano.
    Também serve para gerar de novo um feedback com erro: o registro da tentativa é reaproveitado.
    Com em_segundo_plano=False (comando `flask agentes feedbacks`), espera o agente terminar."""
    registro = execucao.preparar_registro(FeedbackAluno, classificacao.classificar_tentativa(tentativa),
                                          tentativa_id=tentativa.id)
    if registro is None:
        return None
    if not em_segundo_plano:
        return execucao.processar(FeedbackAluno, registro.id, gerar_feedback)
    return execucao.iniciar_em_segundo_plano(FeedbackAluno, registro.id, gerar_feedback)
