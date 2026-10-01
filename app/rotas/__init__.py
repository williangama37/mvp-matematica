def registrar_rotas(app):
    from app.rotas.autenticacao import bp as bp_autenticacao
    from app.rotas.principal import bp as bp_principal
    from app.rotas.admin import bp as bp_admin
    from app.rotas.professor import bp as bp_professor
    from app.rotas.aluno import bp as bp_aluno

    app.register_blueprint(bp_autenticacao)
    app.register_blueprint(bp_principal)
    app.register_blueprint(bp_admin, url_prefix='/admin')
    app.register_blueprint(bp_professor, url_prefix='/professor')
    app.register_blueprint(bp_aluno, url_prefix='/aluno')
