from flask import Flask
from flask_wtf import CSRFProtect
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
csrf = CSRFProtect()
migrate = Migrate()
login = LoginManager()
login.login_view = 'autenticacao.entrar'
login.login_message = 'Faça login para acessar esta página.'
login.login_message_category = 'warning'

ASSUNTOS_INICIAIS = [
    ('Números', 'Sistema de numeração, operações, múltiplos, divisores e números racionais.'),
    ('Frações e Decimais', 'Representação, equivalência e operações com frações e números decimais.'),
    ('Álgebra', 'Expressões algébricas, equações, inequações e sistemas.'),
    ('Funções', 'Função afim, quadrática e interpretação de gráficos.'),
    ('Geometria', 'Figuras planas e espaciais, ângulos, semelhança e teorema de Pitágoras.'),
    ('Grandezas e Medidas', 'Perímetro, área, volume e conversão de unidades.'),
    ('Probabilidade e Estatística', 'Leitura de tabelas e gráficos, média, moda, mediana e probabilidade.'),
    ('Proporcionalidade', 'Razão, proporção, regra de três e porcentagem.'),
]


def criar_administrador_padrao(app):
    """Cria o administrador padrão definido em config.py, se ainda não existir.
    Depois de criado o banco, basta apagar os campos ADMIN_PADRAO_* do config."""
    from app.models import Usuario, PERFIL_ADMINISTRADOR

    nome_usuario = app.config.get('ADMIN_PADRAO_USUARIO')
    senha = app.config.get('ADMIN_PADRAO_SENHA')
    if not nome_usuario or not senha:
        return

    if Usuario.query.filter_by(nome_usuario=nome_usuario).first():
        return

    administrador = Usuario(
        nome_usuario=nome_usuario,
        nome_completo='Jorge Amado',
        perfil=PERFIL_ADMINISTRADOR,
    )
    administrador.definir_senha(senha)
    db.session.add(administrador)
    db.session.commit()


def criar_assuntos_iniciais():
    from app.models import Assunto

    if Assunto.query.first():
        return

    for nome, descricao in ASSUNTOS_INICIAIS:
        db.session.add(Assunto(nome=nome, descricao=descricao))
    db.session.commit()


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    db.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    with app.app_context():
        from app import models
        from app.rotas import registrar_rotas

        registrar_rotas(app)
        db.create_all()
        criar_administrador_padrao(app)
        criar_assuntos_iniciais()

        @login.user_loader
        def carregar_usuario(usuario_id):
            return db.session.get(models.Usuario, int(usuario_id))

        return app
