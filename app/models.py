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
