"""Controle de status e execução em segundo plano dos agentes de diagnóstico.

Funciona com qualquer modelo que use o RegistroAgenteMixin (FeedbackAluno e FeedbackTurma):
1. preparar_registro (um registro por chave, reaproveitado ao gerar de novo) ou
   criar_registro (um registro novo a cada geração, mantendo o histórico): grava os dados
   de entrada (calculados por código) com status 'pendente';
2. iniciar_em_segundo_plano: roda o agente numa thread, sem segurar a requisição;
3. processar: termina o registro como 'pronto' (com o resultado) ou 'erro'."""
import threading
from datetime import timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import STATUS_PENDENTE, STATUS_PRONTO, STATUS_ERRO, agora

# Um registro 'pendente' há mais tempo que isso provavelmente perdeu a thread
# (ex.: servidor reiniciado) e pode ser gerado de novo.
LIMITE_PENDENTE = timedelta(minutes=5)


def pendente_expirado(registro):
    return registro.pendente and registro.inicio_geracao and agora() - registro.inicio_geracao > LIMITE_PENDENTE


def pode_gerar_novamente(registro):
    return registro.com_erro or pendente_expirado(registro)


def preparar_registro(classe, entrada, **chave):
    """Cria ou reaproveita o registro identificado por `chave` (coluna UNIQUE) e o deixa pendente.
    Retorna None se outra requisição criou o mesmo registro ao mesmo tempo (ela cuida da geração)."""
    registro = classe.query.filter_by(**chave).first()
    if registro is None:
        registro = classe(**chave)
        db.session.add(registro)
    registro.entrada = entrada
    registro.resultado = None
    registro.modelo = None
    registro.status = STATUS_PENDENTE
    if hasattr(registro, 'atualizado_em'):
        registro.atualizado_em = agora()
    return _salvar(registro)


def criar_registro(classe, entrada, **campos):
    """Cria um registro novo e pendente. Retorna None se uma restrição do banco impedir
    (ex.: já existe uma geração pendente para o mesmo teste)."""
    registro = classe(status=STATUS_PENDENTE, **campos)
    registro.entrada = entrada
    db.session.add(registro)
    return _salvar(registro)


def marcar_erro(registro):
    """Encerra um registro (ex.: pendente que perdeu a thread) para liberar uma nova geração."""
    registro.status = STATUS_ERRO
    db.session.commit()


def _salvar(registro):
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None
    return registro


def processar(classe, registro_id, gerar):
    """Chama gerar(entrada) -> (resultado, modelo) e grava o status final do registro."""
    registro = db.session.get(classe, registro_id)
    if registro is None or not registro.pendente:
        return
    try:
        resultado, modelo = gerar(registro.entrada)
    except Exception:
        current_app.logger.exception('Falha ao gerar %s %s com o agente.', classe.__tablename__, registro_id)
        db.session.rollback()
        registro.status = STATUS_ERRO
    else:
        registro.resultado = resultado
        registro.modelo = modelo
        registro.status = STATUS_PRONTO
    db.session.commit()


def iniciar_em_segundo_plano(classe, registro_id, gerar):
    """Roda processar() numa thread com o próprio contexto da aplicação (e a própria sessão do banco)."""
    app = current_app._get_current_object()

    def tarefa():
        with app.app_context():
            processar(classe, registro_id, gerar)

    thread = threading.Thread(target=tarefa, name=f'{classe.__tablename__}-{registro_id}', daemon=True)
    thread.start()
    return thread
