"""
Formulários da aplicação ORIS.

Usar Flask-WTF garante proteção CSRF automática nos formulários,
sem precisar implementar nada manualmente.
"""

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length


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
