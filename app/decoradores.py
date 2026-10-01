from functools import wraps
from flask import abort
from flask_login import current_user, login_required


def perfil_requerido(*perfis):
    """Restringe a rota aos perfis informados. O administrador sempre tem acesso."""
    def decorador(funcao):
        @wraps(funcao)
        @login_required
        def funcao_protegida(*args, **kwargs):
            if current_user.eh_administrador or current_user.perfil in perfis:
                return funcao(*args, **kwargs)
            abort(403)
        return funcao_protegida
    return decorador
