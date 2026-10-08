"""Agente que sugere uma questão de múltipla escolha ao professor.

O agente apenas devolve a sugestão; quem decide salvar no banco é o professor,
ao revisar e enviar o formulário de questão."""
import os
from typing import List, Literal

from agno.agent import Agent
from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.run.base import RunStatus
from pydantic import BaseModel, Field

from app.models import NIVEIS_DIFICULDADE, TIPOS_ERRO, LETRAS_ALTERNATIVAS


class ErroGeracao(Exception):
    """Falha ao gerar a questão; a mensagem pode ser mostrada ao professor."""


class AlternativaSugerida(BaseModel):
    letra: Literal['A', 'B', 'C', 'D']
    texto: str = Field(description='Texto da alternativa, curto e sem a letra no início.')
    descricao_distrator: str = Field(
        description='Para alternativas incorretas: o raciocínio equivocado que leva o aluno a escolhê-la. '
                    'Para a correta: string vazia.')
    tipo_erro: str = Field(
        description='Para alternativas incorretas: um destes valores: ' + ', '.join(TIPOS_ERRO)
                    + '. Para a correta: string vazia.')


class QuestaoSugerida(BaseModel):
    enunciado: str = Field(description='Enunciado completo da questão.')
    alternativas: List[AlternativaSugerida] = Field(description='Exatamente 4 alternativas, A, B, C e D, nesta ordem.')
    alternativa_correta: Literal['A', 'B', 'C', 'D']


INSTRUCOES = [
    'Você ajuda professores de Matemática de pré-calculo a criar questões diagnósticas '
    'de múltipla escolha, em português do Brasil.',
    'Cada questão tem exatamente 4 alternativas (A, B, C, D) e apenas uma correta. Varie a posição da correta.',
    'As alternativas incorretas são distratores: cada uma deve ser o resultado exato de um erro típico e plausível '
    'de um aluno (não um número aleatório), para que a escolha revele onde o aluno errou.',
    'Em cada distrator, descreva em uma ou duas frases o raciocínio equivocado, mostrando a conta errada quando '
    'houver (ex.: "Somou numeradores e denominadores: (3+1)/(4+2) = 4/6"), e classifique o tipo de erro: '
    + '; '.join(f'{chave} = {nome}' for chave, nome in TIPOS_ERRO.items()) + '.',
    'Na alternativa correta, deixe descricao_distrator e tipo_erro vazios.',
    'Confira os cálculos: a alternativa correta precisa estar certa e nenhum distrator pode ser equivalente a ela.',
    'Ajuste a complexidade ao nível de dificuldade pedido. Se uma habilidade da BNCC for informada, a questão deve '
    'avaliá-la. Use notação matemática em texto simples (ex.: 3/4, x², √2), sem LaTeX.',
]


def _criar_modelo():
    """Usa o Gemini se GOOGLE_API_KEY estiver no .env; senão, o Claude (ANTHROPIC_API_KEY)."""
    if os.getenv('GOOGLE_API_KEY'):
        return Gemini(id='gemini-3.7-flash')
    return Claude(
        id='claude-opus-5-5',
        max_tokens=16000,
        output_config={'effort': 'medium'},
        # Se o modelo recusar o pedido, a API repete a chamada em um modelo alternativo.
        betas=['server-side-fallback-2026-07-01'],
        request_params={'fallbacks': 'default'},
    )


def _criar_agente():
    return Agent(
        name='Gerador de questões',
        model=_criar_modelo(),
        instructions=INSTRUCOES,
        # Erros temporários (ex.: 503 "alta demanda") costumam passar em segundos: tenta de novo após 2s e 4s.
        retries=2,
        delay_between_retries=2,
        exponential_backoff=True,
        output_schema=QuestaoSugerida,
    )


def _normalizar_tipo_erro(tipo_erro):
    tipo_erro = (tipo_erro or '').strip().lower()
    return tipo_erro if tipo_erro in TIPOS_ERRO else 'outro'


def gerar_questao(assunto, descricao_assunto, nivel_dificuldade, habilidade_bncc=None):
    """Retorna um dicionário com a questão sugerida, no formato do FormularioQuestao."""
    pedido = [
        f'Assunto: {assunto}',
        f'Descrição do assunto: {descricao_assunto or "—"}',
        f'Dificuldade: {NIVEIS_DIFICULDADE.get(nivel_dificuldade, nivel_dificuldade)}',
    ]
    if habilidade_bncc:
        pedido.append(f'Habilidade BNCC: {habilidade_bncc}')

    resposta = _criar_agente().run('Crie uma questão com estes dados:\n' + '\n'.join(pedido))
    # Em caso de falha (chave inválida, cota, modelo inexistente...) o Agno não lança exceção:
    # marca o status como erro e coloca a mensagem em content.
    if resposta.status == RunStatus.error:
        raise ErroGeracao(f'O modelo retornou um erro: {resposta.content}')
    questao = resposta.content
    if not isinstance(questao, QuestaoSugerida):
        raise ErroGeracao('O agente não devolveu uma questão no formato esperado.')

    alternativas = {alternativa.letra: alternativa for alternativa in questao.alternativas}
    if sorted(alternativas) != LETRAS_ALTERNATIVAS:
        raise ErroGeracao('O agente não devolveu as 4 alternativas esperadas.')

    return {
        'enunciado': questao.enunciado,
        'alternativa_correta': questao.alternativa_correta,
        'alternativas': [
            {
                'texto': alternativas[letra].texto,
                'descricao_distrator': '' if letra == questao.alternativa_correta
                else alternativas[letra].descricao_distrator,
                'tipo_erro': '' if letra == questao.alternativa_correta
                else _normalizar_tipo_erro(alternativas[letra].tipo_erro),
            }
            for letra in LETRAS_ALTERNATIVAS
        ],
    }
