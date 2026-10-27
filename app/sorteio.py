"""Sorteio de questões para o teste gerado automaticamente.

O sorteio só monta uma proposta: nada é salvo até o professor revisar a prévia e confirmar.
Dentro de cada nível de dificuldade as questões são repartidas entre os assuntos escolhidos,
para um assunto com muitas questões cadastradas não tomar conta do teste."""
import random
from collections import defaultdict
from app.models import Questao, NIVEIS_DIFICULDADE

ORDEM_NIVEIS = list(NIVEIS_DIFICULDADE)


class SorteioImpossivel(Exception):
    """Não há questões ativas suficientes para os parâmetros pedidos."""


def questoes_disponiveis(assunto_ids):
    return Questao.query.filter(Questao.ativa.is_(True), Questao.assunto_id.in_(assunto_ids)).all()


def disponibilidade():
    """{assunto_id: {nível: quantidade de questões ativas}}, para o professor ver o que dá para sortear."""
    contagem = defaultdict(lambda: dict.fromkeys(ORDEM_NIVEIS, 0))
    for questao in Questao.query.filter_by(ativa=True).all():
        contagem[questao.assunto_id][questao.nivel_dificuldade] += 1
    return contagem


def _equilibrado(questoes, quantidade):
    """Escolhe `quantidade` questões alternando entre os assuntos (em ordem aleatória)."""
    por_assunto = defaultdict(list)
    for questao in questoes:
        por_assunto[questao.assunto_id].append(questao)
    filas = list(por_assunto.values())
    for fila in filas:
        random.shuffle(fila)
    random.shuffle(filas)

    escolhidas = []
    while len(escolhidas) < quantidade and filas:
        for fila in list(filas):
            if len(escolhidas) == quantidade:
                break
            escolhidas.append(fila.pop())
            if not fila:
                filas.remove(fila)
    return escolhidas


def sortear(assunto_ids, quantidade, distribuicao=None):
    """Lista de questões sorteadas, agrupadas por assunto e dificuldade para facilitar a revisão.
    distribuicao: {nível: quantidade} ou None para qualquer dificuldade."""
    questoes = questoes_disponiveis(assunto_ids)
    if distribuicao is None:
        if len(questoes) < quantidade:
            raise SorteioImpossivel(f'Há só {len(questoes)} questão(ões) ativa(s) nos assuntos escolhidos '
                                    f'(pedidas: {quantidade}).')
        escolhidas = _equilibrado(questoes, quantidade)
    else:
        faltas = []
        escolhidas = []
        for nivel, pedidas in distribuicao.items():
            do_nivel = [questao for questao in questoes if questao.nivel_dificuldade == nivel]
            if len(do_nivel) < pedidas:
                faltas.append(f'{NIVEIS_DIFICULDADE[nivel].lower()}: {len(do_nivel)} de {pedidas}')
            escolhidas += _equilibrado(do_nivel, pedidas)
        if faltas:
            raise SorteioImpossivel('Não há questões ativas suficientes nos assuntos escolhidos ('
                                    + '; '.join(faltas) + ').')
    return sorted(escolhidas, key=lambda questao: (questao.assunto.nome,
                                                   ORDEM_NIVEIS.index(questao.nivel_dificuldade), questao.id))


def substituta(questao, ids_em_uso):
    """Outra questão ativa do mesmo assunto e dificuldade que ainda não está no teste, ou None."""
    candidatas = Questao.query.filter(Questao.ativa.is_(True), Questao.assunto_id == questao.assunto_id,
                                      Questao.nivel_dificuldade == questao.nivel_dificuldade,
                                      Questao.id.notin_(ids_em_uso)).all()
    return random.choice(candidatas) if candidatas else None
