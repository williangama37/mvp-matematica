from flask_wtf import FlaskForm
from wtforms import (Form, StringField, PasswordField, BooleanField, SubmitField, SelectField,
                     TextAreaField, IntegerField, FieldList, FormField, RadioField, SelectMultipleField)
from wtforms.validators import DataRequired, ValidationError, EqualTo, Email, Optional, Length, NumberRange
from wtforms.widgets import ListWidget, CheckboxInput
from app.models import Usuario, Assunto, PERFIS, NIVEIS_DIFICULDADE, TIPOS_ERRO, LETRAS_ALTERNATIVAS


class FormularioLogin(FlaskForm):
    nome_usuario = StringField('Usuário', validators=[DataRequired()])
    senha = PasswordField('Senha', validators=[DataRequired()])
    lembrar_me = BooleanField('Lembrar-me')
    enviar = SubmitField('Entrar')


class FormularioRegistro(FlaskForm):
    nome_completo = StringField('Nome completo', validators=[DataRequired(), Length(max=150)])
    nome_usuario = StringField('Usuário', validators=[DataRequired(), Length(max=150)])
    email = StringField('E-mail', validators=[Optional(), Email()])
    turma_id = SelectField('Turma', coerce=int, validators=[Optional()])
    senha = PasswordField('Senha', validators=[DataRequired(), Length(min=6, message='Use ao menos 6 caracteres.')])
    senha2 = PasswordField('Repita a senha', validators=[DataRequired(), EqualTo('senha', 'As senhas não conferem.')])
    enviar = SubmitField('Registrar')

    def validate_nome_usuario(self, nome_usuario):
        if Usuario.query.filter_by(nome_usuario=nome_usuario.data).first() is not None:
            raise ValidationError('Por favor, use um nome de usuário diferente.')

    def validate_email(self, email):
        if email.data and Usuario.query.filter_by(email=email.data).first() is not None:
            raise ValidationError('Este e-mail já está cadastrado.')


class FormularioUsuarioAdmin(FlaskForm):
    perfil = SelectField('Perfil', choices=list(PERFIS.items()))
    turma_id = SelectField('Turma', coerce=int)
    enviar = SubmitField('Salvar')


class FormularioRedefinirSenha(FlaskForm):
    """Usado pelo administrador para definir uma senha provisória para outro usuário."""
    nova_senha = PasswordField('Nova senha', validators=[DataRequired(), Length(min=6, message='Use ao menos 6 caracteres.')])
    nova_senha2 = PasswordField('Repita a nova senha',
                                validators=[DataRequired(), EqualTo('nova_senha', 'As senhas não conferem.')])
    enviar = SubmitField('Alterar senha')


class FormularioTrocarSenha(FlaskForm):
    """Exibido no primeiro login após o administrador redefinir a senha."""
    senha = PasswordField('Nova senha', validators=[DataRequired(), Length(min=6, message='Use ao menos 6 caracteres.')])
    senha2 = PasswordField('Confirme a nova senha',
                           validators=[DataRequired(), EqualTo('senha', 'As senhas não conferem.')])
    enviar = SubmitField('Salvar nova senha')


class FormularioTurma(FlaskForm):
    nome = StringField('Nome da turma', validators=[DataRequired(), Length(max=100)])
    ano_letivo = IntegerField('Ano letivo', validators=[DataRequired(), NumberRange(min=2000, max=2100)])
    professor_id = SelectField('Professor responsável', coerce=int)
    enviar = SubmitField('Salvar')


class FormularioAdicionarAluno(FlaskForm):
    aluno_id = SelectField('Aluno', coerce=int, validators=[DataRequired()])
    enviar = SubmitField('Adicionar à turma')


class FormularioAssunto(FlaskForm):
    nome = StringField('Assunto', validators=[DataRequired(), Length(max=100)])
    descricao = TextAreaField('Descrição', validators=[Optional()])
    enviar = SubmitField('Salvar')

    def __init__(self, *args, assunto_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.assunto_id = assunto_id

    def validate_nome(self, nome):
        existente = Assunto.query.filter_by(nome=nome.data).first()
        if existente and existente.id != self.assunto_id:
            raise ValidationError('Já existe um assunto com este nome.')


class FormularioAlternativa(Form):
    """Subformulário (sem CSRF próprio) de uma alternativa da questão."""
    texto = StringField('Texto da alternativa', validators=[DataRequired()])
    descricao_distrator = TextAreaField('Raciocínio que leva a este erro', validators=[Optional()])
    tipo_erro = SelectField('Tipo de erro', choices=[('', '— selecione —')] + list(TIPOS_ERRO.items()),
                            validators=[Optional()])


class FormularioQuestao(FlaskForm):
    enunciado = TextAreaField('Enunciado', validators=[DataRequired()])
    assunto_id = SelectField('Assunto', coerce=int, validators=[DataRequired()])
    nivel_dificuldade = SelectField('Dificuldade', choices=list(NIVEIS_DIFICULDADE.items()))
    habilidade_bncc = StringField('Habilidade BNCC (opcional)', validators=[Optional(), Length(max=20)])
    alternativas = FieldList(FormField(FormularioAlternativa), min_entries=4, max_entries=4)
    alternativa_correta = RadioField('Alternativa correta', choices=[(letra, letra) for letra in LETRAS_ALTERNATIVAS],
                                     validators=[DataRequired(message='Indique a alternativa correta.')])
    ativa = BooleanField('Questão ativa', default=True)
    enviar = SubmitField('Salvar questão')

    def validate_alternativas(self, alternativas):
        correta = self.alternativa_correta.data
        for letra, alternativa in zip(LETRAS_ALTERNATIVAS, alternativas.entries):
            if letra == correta:
                continue
            if not alternativa.descricao_distrator.data or not alternativa.tipo_erro.data:
                raise ValidationError(
                    f'Descreva o distrator e o tipo de erro da alternativa {letra} (todas as incorretas precisam).')


class CampoMultiplaEscolha(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class FormularioTeste(FlaskForm):
    titulo = StringField('Título', validators=[DataRequired(), Length(max=150)])
    descricao = TextAreaField('Descrição / instruções', validators=[Optional()])
    turma_id = SelectField('Turma', coerce=int)
    questoes = CampoMultiplaEscolha('Questões', coerce=int,
                                    validators=[DataRequired(message='Selecione ao menos uma questão.')])
    ativo = BooleanField('Disponível para os alunos', default=True)
    embaralhar_questoes = BooleanField('Embaralhar a ordem das questões para cada aluno')
    enviar = SubmitField('Salvar teste')


class FormularioGerarTeste(FlaskForm):
    """Parâmetros do sorteio e dados do teste gerado automaticamente. As questões sorteadas
    vão na própria página (campos 'questao'), para a prévia poder ser alterada antes de salvar."""
    quantidade = IntegerField('Quantidade de questões', default=10,
                              validators=[DataRequired(message='Informe a quantidade.'), NumberRange(min=1, max=50)])
    assuntos = CampoMultiplaEscolha('Assuntos', coerce=int,
                                    validators=[DataRequired(message='Selecione ao menos um assunto.')])
    qtd_facil = IntegerField('Fáceis', validators=[Optional(), NumberRange(min=0)])
    qtd_medio = IntegerField('Médias', validators=[Optional(), NumberRange(min=0)])
    qtd_dificil = IntegerField('Difíceis', validators=[Optional(), NumberRange(min=0)])
    titulo = StringField('Título', validators=[Optional(), Length(max=150)])
    descricao = TextAreaField('Descrição / instruções', validators=[Optional()])
    ativo = BooleanField('Disponível para os alunos', default=True)
    embaralhar_questoes = BooleanField('Embaralhar a ordem das questões para cada aluno', default=True)

    @property
    def distribuicao(self):
        """{nível: quantidade} quando o professor preencheu alguma dificuldade; senão None (qualquer nível)."""
        valores = {'facil': self.qtd_facil.data, 'medio': self.qtd_medio.data, 'dificil': self.qtd_dificil.data}
        if all(valor is None for valor in valores.values()):
            return None
        return {nivel: valor or 0 for nivel, valor in valores.items()}

    def validate_quantidade(self, quantidade):
        distribuicao = self.distribuicao
        if distribuicao is not None and quantidade.data and sum(distribuicao.values()) != quantidade.data:
            raise ValidationError(f'A distribuição por dificuldade soma {sum(distribuicao.values())}, '
                                  f'mas a quantidade é {quantidade.data}.')
