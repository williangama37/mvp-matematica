from dotenv import load_dotenv

# Carrega o arquivo .env (ex.: ANTHROPIC_API_KEY, usada pelos agentes do Agno).
load_dotenv()


class Config:
    SECRET_KEY = 'minha_chave_secreta'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///diagnostico_matematica.db'
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
