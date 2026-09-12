"""
Formulários da aplicação ORIS.

Usar Flask-WTF garante proteção CSRF automática nos formulários,
sem precisar implementar nada manualmente.
"""

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Regexp


class LoginForm(FlaskForm):
    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Informe o email."),
            Email(message="Email inválido.", check_deliverability=False),
        ],
    )
    senha = PasswordField(
        "Senha",
        validators=[DataRequired(message="Informe a senha."), Length(min=1, max=255)],
    )
    submit = SubmitField("Entrar")


class UnidadeForm(FlaskForm):
    """Formulário de cadastro/edição de Unidade de Saúde Bucal.

    As validações aqui são as de formato/obrigatoriedade. A
    unicidade do CNES é verificada à parte, na rota
    (app/routes/unidades.py), para permitir uma mensagem amigável
    específica em vez de deixar o erro do banco estourar.
    """

    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome da unidade."), Length(max=200)],
    )

    cnes = StringField(
        "CNES",
        validators=[
            DataRequired(message="Informe o código CNES."),
            Regexp(
                r"^\d{7,15}$",
                message="CNES deve conter apenas números (entre 7 e 15 dígitos).",
            ),
        ],
    )

    tipo = StringField(
        "Tipo",
        validators=[DataRequired(message="Informe o tipo da unidade."), Length(max=100)],
    )

    endereco = StringField("Endereço", validators=[Length(max=255)])
    bairro = StringField("Bairro", validators=[Length(max=100)])

    cidade = StringField(
        "Cidade",
        validators=[DataRequired(message="Informe a cidade."), Length(max=100)],
    )

    uf = StringField(
        "UF",
        validators=[
            DataRequired(message="Informe a UF."),
            Length(min=2, max=2, message="UF deve ter 2 letras (ex.: PE)."),
        ],
    )

    situacao = SelectField(
        "Situação",
        choices=[
            ("ATIVA", "Ativa"),
            ("INATIVA", "Inativa"),
            ("MANUTENCAO", "Manutenção"),
        ],
        validators=[DataRequired(message="Selecione uma situação.")],
    )

    submit = SubmitField("Salvar")


class AlterarSituacaoForm(FlaskForm):
    """Formulário simples, usado só para alterar a situação de uma
    unidade já existente (sem editar os demais campos)."""

    situacao = SelectField(
        "Nova situação",
        choices=[
            ("ATIVA", "Ativa"),
            ("INATIVA", "Inativa"),
            ("MANUTENCAO", "Manutenção"),
        ],
        validators=[DataRequired(message="Selecione uma situação.")],
    )
    submit = SubmitField("Alterar situação")
