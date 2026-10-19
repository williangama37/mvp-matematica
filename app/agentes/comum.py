"""Peças compartilhadas pelos agentes de diagnóstico (feedback do aluno e análise da turma):
escolha do modelo e execução com saída estruturada.

Segue a mesma configuração do gerador de questões."""
import os

from agno.models.anthropic import Claude
from agno.models.google import Gemini
from agno.run.base import RunStatus


class ErroAgente(Exception):
    """O agente não conseguiu devolver um resultado válido."""


def criar_modelo():
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


def executar(agente, pedido, esquema):
    """Roda o agente e devolve (saída validada pelo esquema Pydantic, id do modelo que respondeu)."""
    resposta = agente.run(pedido)
    # Em caso de falha (chave inválida, cota, modelo inexistente...) o Agno não lança exceção:
    # marca o status como erro e coloca a mensagem em content.
    if resposta.status == RunStatus.error:
        raise ErroAgente(f'O modelo retornou um erro: {resposta.content}')
    if not isinstance(resposta.content, esquema):
        raise ErroAgente('O agente não devolveu a resposta no formato esperado.')
    return resposta.content, resposta.model or agente.model.id
