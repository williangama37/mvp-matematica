import json
from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


PERFIL_ALUNO = 'aluno'
PERFIL_PROFESSOR = 'professor'
PERFIL_ADMINISTRADOR = 'administrador'

PERFIS = {
    PERFIL_ALUNO: 'Aluno',
    PERFIL_PROFESSOR: 'Professor',
    PERFIL_ADMINISTRADOR: 'Administrador',
}

NIVEIS_DIFICULDADE = {
    'facil': 'Fácil',
    'medio': 'Médio',
    'dificil': 'Difícil',
}

# Classificação do erro associado a cada distrator. É o que permite mapear
# "onde" o aluno errou e alimentar os agentes de IA no futuro.
TIPOS_ERRO = {
    'conceitual': 'Erro conceitual',
    'procedimental': 'Erro procedimental',
    'calculo': 'Erro de cálculo',
    'interpretacao': 'Erro de interpretação',
    'outro': 'Outro',
}

LETRAS_ALTERNATIVAS = ['A', 'B', 'C', 'D']


def agora():
    return datetime.now()


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True)
    nome_usuario = db.Column(db.String(150), unique=True, nullable=False)
    nome_completo = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True)
    senha_hash = db.Column(db.String(256), nullable=False)
    perfil = db.Column(db.String(20), nullable=False, default=PERFIL_ALUNO)
    turma_id = db.Column(db.Integer, db.ForeignKey('turma.id', name='fk_usuario_turma_id'))
    ultimo_acesso = db.Column(db.DateTime)
    # Ligado quando o administrador redefine a senha: o próximo login exige uma senha nova.
    trocar_senha = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    criado_em = db.Column(db.DateTime, default=agora)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)

    turma = db.relationship('Turma', foreign_keys=[turma_id], back_populates='alunos')
    tentativas = db.relationship('Tentativa', back_populates='aluno', lazy=True, cascade='all, delete-orphan')
    orientacoes = db.relationship('OrientacaoPedagogica', back_populates='destinatario', lazy=True,
                                  cascade='all, delete-orphan')

    def definir_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    @property
    def eh_aluno(self):
        return self.perfil == PERFIL_ALUNO

    @property
    def eh_professor(self):
        return self.perfil == PERFIL_PROFESSOR

    @property
    def eh_administrador(self):
        return self.perfil == PERFIL_ADMINISTRADOR

    @property
    def pode_ensinar(self):
        """Professores e administradores têm acesso às funções de professor."""
        return self.perfil in (PERFIL_PROFESSOR, PERFIL_ADMINISTRADOR)

    @property
    def nome_perfil(self):
        return PERFIS.get(self.perfil, self.perfil)


class Turma(db.Model):
    __tablename__ = 'turma'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    ano_letivo = db.Column(db.Integer, nullable=False)
    professor_id = db.Column(db.Integer, db.ForeignKey('usuario.id', name='fk_turma_professor_id'))
    criado_em = db.Column(db.DateTime, default=agora)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)

    professor = db.relationship('Usuario', foreign_keys=[professor_id])
    alunos = db.relationship('Usuario', foreign_keys=[Usuario.turma_id], back_populates='turma')
    testes = db.relationship('Teste', back_populates='turma', lazy=True)

    @property
    def descricao(self):
        return f'{self.nome} ({self.ano_letivo})'


class Assunto(db.Model):
    __tablename__ = 'assunto'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=agora)

    questoes = db.relationship('Questao', back_populates='assunto', lazy=True)


class Questao(db.Model):
    __tablename__ = 'questao'
    id = db.Column(db.Integer, primary_key=True)
    enunciado = db.Column(db.Text, nullable=False)
    assunto_id = db.Column(db.Integer, db.ForeignKey('assunto.id', name='fk_questao_assunto_id'), nullable=False)
    nivel_dificuldade = db.Column(db.String(20), nullable=False, default='medio')
    habilidade_bncc = db.Column(db.String(20))
    ativa = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=agora)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuario.id', name='fk_questao_criado_por'))
    atualizado_por = db.Column(db.Integer, db.ForeignKey('usuario.id', name='fk_questao_atualizado_por'))

    assunto = db.relationship('Assunto', back_populates='questoes')
    criador = db.relationship('Usuario', foreign_keys=[criado_por])
    atualizador = db.relationship('Usuario', foreign_keys=[atualizado_por])
    alternativas = db.relationship('Alternativa', back_populates='questao', lazy=True,
                                   order_by='Alternativa.letra', cascade='all, delete-orphan')

    @property
    def alternativa_correta(self):
        return next((alternativa for alternativa in self.alternativas if alternativa.correta), None)

    @property
    def nome_dificuldade(self):
        return NIVEIS_DIFICULDADE.get(self.nivel_dificuldade, self.nivel_dificuldade)


class Alternativa(db.Model):
    """Uma das 4 alternativas da questão. As incorretas são os distratores:
    cada uma registra qual raciocínio equivocado leva o aluno a escolhê-la."""
    __tablename__ = 'alternativa'
    id = db.Column(db.Integer, primary_key=True)
    questao_id = db.Column(db.Integer, db.ForeignKey('questao.id', name='fk_alternativa_questao_id'), nullable=False)
    letra = db.Column(db.String(1), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    correta = db.Column(db.Boolean, default=False, nullable=False)
    descricao_distrator = db.Column(db.Text)
    tipo_erro = db.Column(db.String(30))

    questao = db.relationship('Questao', back_populates='alternativas')

    @property
    def nome_tipo_erro(self):
        return TIPOS_ERRO.get(self.tipo_erro, '—')


teste_questao = db.Table(
    'teste_questao',
    db.Column('teste_id', db.Integer, db.ForeignKey('teste.id', name='fk_teste_questao_teste_id'), primary_key=True),
    db.Column('questao_id', db.Integer, db.ForeignKey('questao.id', name='fk_teste_questao_questao_id'),
              primary_key=True),
)


class Teste(db.Model):
    __tablename__ = 'teste'
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text)
    turma_id = db.Column(db.Integer, db.ForeignKey('turma.id', name='fk_teste_turma_id'))
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=agora)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)
    criado_por = db.Column(db.Integer, db.ForeignKey('usuario.id', name='fk_teste_criado_por'))

    turma = db.relationship('Turma', back_populates='testes')
    criador = db.relationship('Usuario', foreign_keys=[criado_por])
    questoes = db.relationship('Questao', secondary=teste_questao, lazy='subquery', order_by='Questao.id')
    tentativas = db.relationship('Tentativa', back_populates='teste', lazy=True, cascade='all, delete-orphan')
    analises = db.relationship('FeedbackTurma', back_populates='teste', lazy=True, cascade='all, delete-orphan')


class Tentativa(db.Model):
    """Uma realização de um teste por um aluno."""
    __tablename__ = 'tentativa'
    id = db.Column(db.Integer, primary_key=True)
    teste_id = db.Column(db.Integer, db.ForeignKey('teste.id', name='fk_tentativa_teste_id'), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey('usuario.id', name='fk_tentativa_aluno_id'), nullable=False)
    iniciada_em = db.Column(db.DateTime, default=agora)
    finalizada_em = db.Column(db.DateTime)
    total_acertos = db.Column(db.Integer, default=0)
    total_questoes = db.Column(db.Integer, default=0)

    teste = db.relationship('Teste', back_populates='tentativas')
    aluno = db.relationship('Usuario', back_populates='tentativas')
    respostas = db.relationship('Resposta', back_populates='tentativa', lazy=True, cascade='all, delete-orphan')
    feedback = db.relationship('FeedbackAluno', back_populates='tentativa', uselist=False,
                               cascade='all, delete-orphan')

    @property
    def percentual_acerto(self):
        if not self.total_questoes:
            return 0
        return round(100 * self.total_acertos / self.total_questoes, 1)


class Resposta(db.Model):
    __tablename__ = 'resposta'
    id = db.Column(db.Integer, primary_key=True)
    tentativa_id = db.Column(db.Integer, db.ForeignKey('tentativa.id', name='fk_resposta_tentativa_id'),
                             nullable=False)
    questao_id = db.Column(db.Integer, db.ForeignKey('questao.id', name='fk_resposta_questao_id'), nullable=False)
    alternativa_id = db.Column(db.Integer, db.ForeignKey('alternativa.id', name='fk_resposta_alternativa_id'))
    correta = db.Column(db.Boolean, default=False, nullable=False)

    tentativa = db.relationship('Tentativa', back_populates='respostas')
    questao = db.relationship('Questao')
    alternativa = db.relationship('Alternativa')


TIPO_ORIENTACAO_ALUNO = 'aluno'
TIPO_ORIENTACAO_NIVELAMENTO = 'nivelamento'


class OrientacaoPedagogica(db.Model):
    """Orientações que serão geradas pelos agentes de IA (Agno).
    - tipo 'aluno': orientação de estudo para o próprio aluno;
    - tipo 'nivelamento': plano de aula de nivelamento para o professor."""
    __tablename__ = 'orientacao_pedagogica'
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuario.id', name='fk_orientacao_destinatario_id'),
                                nullable=False)
    turma_id = db.Column(db.Integer, db.ForeignKey('turma.id', name='fk_orientacao_turma_id'))
    tentativa_id = db.Column(db.Integer, db.ForeignKey('tentativa.id', name='fk_orientacao_tentativa_id'))
    titulo = db.Column(db.String(200), nullable=False)
    conteudo = db.Column(db.Text, nullable=False)
    gerado_por = db.Column(db.String(50), default='agente_ia')
    criado_em = db.Column(db.DateTime, default=agora)

    destinatario = db.relationship('Usuario', back_populates='orientacoes')
    turma = db.relationship('Turma')
    tentativa = db.relationship('Tentativa')


STATUS_PENDENTE = 'pendente'
STATUS_PRONTO = 'pronto'
STATUS_ERRO = 'erro'
STATUS_AGENTE = (STATUS_PENDENTE, STATUS_PRONTO, STATUS_ERRO)


class RegistroAgenteMixin:
    """Campos comuns aos resultados dos agentes de diagnóstico (feedback do aluno e análise da turma).
    Os dados de entrada são calculados por código e salvos antes de o agente rodar, na coluna JSON
    indicada por COLUNA_ENTRADA; o resultado do agente só existe quando o status é 'pronto'."""
    COLUNA_ENTRADA = None

    resultado_json = db.Column(db.Text)
    status = db.Column(db.String(10), nullable=False, default=STATUS_PENDENTE)
    modelo = db.Column(db.String(60))
    criado_em = db.Column(db.DateTime, default=agora)

    @property
    def entrada(self):
        valor = getattr(self, self.COLUNA_ENTRADA)
        return json.loads(valor) if valor else None

    @entrada.setter
    def entrada(self, valor):
        setattr(self, self.COLUNA_ENTRADA, json.dumps(valor, ensure_ascii=False))

    @property
    def resultado(self):
        return json.loads(self.resultado_json) if self.resultado_json else None

    @resultado.setter
    def resultado(self, valor):
        self.resultado_json = json.dumps(valor, ensure_ascii=False) if valor is not None else None

    @property
    def inicio_geracao(self):
        """Quando a geração atual começou (usado para detectar um 'pendente' que perdeu a thread)."""
        return self.criado_em

    @property
    def pendente(self):
        return self.status == STATUS_PENDENTE

    @property
    def pronto(self):
        return self.status == STATUS_PRONTO

    @property
    def com_erro(self):
        return self.status == STATUS_ERRO


class FeedbackAluno(RegistroAgenteMixin, db.Model):
    """Feedback do agente de IA para o aluno, um por tentativa (gerar de novo reaproveita o registro)."""
    __tablename__ = 'feedback_aluno'
    __table_args__ = (
        db.CheckConstraint(f"status IN {STATUS_AGENTE}", name='ck_feedback_aluno_status'),
        db.UniqueConstraint('tentativa_id', name='uq_feedback_aluno_tentativa_id'),
    )
    COLUNA_ENTRADA = 'classificacao_json'

    id = db.Column(db.Integer, primary_key=True)
    tentativa_id = db.Column(db.Integer, db.ForeignKey('tentativa.id', name='fk_feedback_aluno_tentativa_id',
                                                       ondelete='CASCADE'),
                             nullable=False)
    classificacao_json = db.Column(db.Text, nullable=False)
    atualizado_em = db.Column(db.DateTime, default=agora, onupdate=agora)

    tentativa = db.relationship('Tentativa', back_populates='feedback')

    @property
    def classificacao(self):
        return self.entrada

    @classificacao.setter
    def classificacao(self, valor):
        self.entrada = valor

    @property
    def inicio_geracao(self):
        return self.atualizado_em


GATILHO_MANUAL = 'manual'
GATILHO_FORCADO = 'forcado'
GATILHOS = {GATILHO_MANUAL: 'Manual', GATILHO_FORCADO: 'Forçado (sem respostas novas)'}


class FeedbackTurma(RegistroAgenteMixin, db.Model):
    """Análise do agente de IA para o professor sobre o desempenho da turma em um teste.
    Cada atualização cria um novo registro, mantendo o histórico. qtd_respostas e
    data_ultima_resposta guardam o estado dos dados no momento da análise."""
    __tablename__ = 'feedback_turma'
    __table_args__ = (
        db.CheckConstraint(f"status IN {STATUS_AGENTE}", name='ck_feedback_turma_status'),
        db.CheckConstraint(f"gatilho IN {tuple(GATILHOS)}", name='ck_feedback_turma_gatilho'),
        db.Index('ix_feedback_turma_teste_criado', 'teste_id', 'criado_em'),
        # Não é UNIQUE por teste: só impede duas análises 'pendente' ao mesmo tempo para o mesmo teste.
        db.Index('uq_feedback_turma_pendente', 'teste_id', unique=True,
                 sqlite_where=db.text(f"status = '{STATUS_PENDENTE}'"),
                 postgresql_where=db.text(f"status = '{STATUS_PENDENTE}'")),
    )
    COLUNA_ENTRADA = 'dados_entrada_json'

    id = db.Column(db.Integer, primary_key=True)
    teste_id = db.Column(db.Integer, db.ForeignKey('teste.id', name='fk_feedback_turma_teste_id', ondelete='CASCADE'),
                         nullable=False)
    qtd_respostas = db.Column(db.Integer, nullable=False)
    data_ultima_resposta = db.Column(db.DateTime)
    dados_entrada_json = db.Column(db.Text, nullable=False)
    gatilho = db.Column(db.String(10), nullable=False, default=GATILHO_MANUAL)

    teste = db.relationship('Teste', back_populates='analises')

    @property
    def nome_gatilho(self):
        return GATILHOS.get(self.gatilho, self.gatilho)
