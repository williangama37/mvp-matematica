import os
from dotenv import load_dotenv

# Carrega o arquivo .env (ex.: ANTHROPIC_API_KEY, usada pelos agentes do Agno, e DATABASE_URL).
load_dotenv()


def url_banco():
    """Usa o PostgreSQL de DATABASE_URL (definida pelo Heroku ou no .env); sem ela, o SQLite local.
    O Heroku entrega a URL como postgres://, mas o SQLAlchemy só aceita postgresql://."""
    url = os.environ.get('DATABASE_URL', 'sqlite:///diagnostico_matematica.db')
    if url.startswith('postgres://'):
        url = url.replace('postgres://', 'postgresql://', 1)
    return url


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'minha_chave_secreta')
    SQLALCHEMY_DATABASE_URI = url_banco()
    # Descarta conexões que o servidor do banco encerrou por inatividade.
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ------------------------------------------------------------------
    # ADMINISTRADOR PADRÃO
    # Usado apenas para criar o primeiro administrador quando o banco é
    # criado. Depois que o banco existir, APAGUE estas duas linhas: o
    # usuário continua salvo no banco (com a senha criptografada) e a
    # criação automática é ignorada quando os campos não existem.
    # ------------------------------------------------------------------
    ADMIN_PADRAO_USUARIO = 'jorge.amado'
    ADMIN_PADRAO_SENHA = '3ngenharia'
