"""Formulários da aplicação ORIS."""

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Regexp, ValidationError

CNES_REGEX = r"^\d{7,15}$"


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
    """Formulário de cadastro/edição de Unidade de Saúde Bucal."""

    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome da unidade."), Length(max=200)],
    )

    cnes = StringField(
        "CNES",
        validators=[
            DataRequired(message="Informe o código CNES."),
            Regexp(
                CNES_REGEX,
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
    """Formulário simples, usado só para alterar a situação de uma unidade já existente..."""

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


def _coerce_opcional_int(valor):
    """Converte o valor de um SelectField para int, tratando string vazia (opção..."""
    if valor in (None, "", "None"):
        return None
    return int(valor)


class ServicoForm(FlaskForm):
    """Formulário de cadastro/edição de Serviço de Saúde Bucal."""

    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome do serviço."), Length(max=150)],
    )

    unidade_id = SelectField(
        "Unidade",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Selecione a unidade.")],
    )

    situacao = SelectField(
        "Situação",
        choices=[("ATIVO", "Ativo"), ("INATIVO", "Inativo")],
        validators=[DataRequired(message="Selecione uma situação.")],
    )

    submit = SubmitField("Salvar")


class EquipamentoForm(FlaskForm):
    """Formulário de cadastro/edição de Equipamento."""

    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome do equipamento."), Length(max=150)],
    )

    tipo = StringField(
        "Tipo",
        validators=[DataRequired(message="Informe o tipo do equipamento."), Length(max=100)],
    )

    unidade_id = SelectField(
        "Unidade",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Selecione a unidade.")],
    )

    servico_id = SelectField(
        "Serviço (opcional)",
        choices=[],
        coerce=_coerce_opcional_int,
        validate_choice=True,
    )

    situacao = SelectField(
        "Situação",
        choices=[("ATIVO", "Ativo"), ("INATIVO", "Inativo")],
        validators=[DataRequired(message="Selecione uma situação.")],
    )

    submit = SubmitField("Salvar")


class AlterarSituacaoAtivoInativoForm(FlaskForm):
    """Formulário simples para alterar a situação (ATIVO/INATIVO) de um Serviço ou..."""

    situacao = SelectField(
        "Nova situação",
        choices=[("ATIVO", "Ativo"), ("INATIVO", "Inativo")],
        validators=[DataRequired(message="Selecione uma situação.")],
    )
    submit = SubmitField("Alterar situação")


class AcaoAlteracaoForm(FlaskForm):
    """Formulário mínimo, usado só para dar proteção CSRF aos botões de aprovar/rejeitar..."""

    submit = SubmitField("Confirmar")


class CriarUsuarioForm(FlaskForm):
    """Formulário de criação de usuário (Fase 11 - Administração de Usuários)."""

    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=150)],
    )

    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Informe o email."),
            Email(message="Email inválido.", check_deliverability=False),
            Length(max=150),
        ],
    )

    senha = PasswordField(
        "Senha",
        validators=[
            DataRequired(message="Informe a senha."),
            Length(min=8, max=255, message="A senha deve ter no mínimo 8 caracteres."),
        ],
    )

    perfil = SelectField(
        "Perfil",
        choices=[
            ("ADMINISTRADOR", "Administrador"),
            ("GESTAO_INFORMACAO", "Gestão da Informação"),
            ("RESPONSAVEL_SAUDE_BUCAL", "Responsável pela Saúde Bucal"),
            ("GESTOR", "Gestor"),
        ],
        validators=[DataRequired(message="Selecione um perfil.")],
    )

    ativo = SelectField(
        "Situação",
        choices=[("1", "Ativo"), ("0", "Inativo")],
        default="1",
        validators=[DataRequired()],
    )

    submit = SubmitField("Salvar")


class EditarUsuarioForm(FlaskForm):
    """Formulário de edição de usuário - só nome, email e perfil."""

    nome = StringField(
        "Nome",
        validators=[DataRequired(message="Informe o nome."), Length(max=150)],
    )

    email = StringField(
        "Email",
        validators=[
            DataRequired(message="Informe o email."),
            Email(message="Email inválido.", check_deliverability=False),
            Length(max=150),
        ],
    )

    perfil = SelectField(
        "Perfil",
        choices=[
            ("ADMINISTRADOR", "Administrador"),
            ("GESTAO_INFORMACAO", "Gestão da Informação"),
            ("RESPONSAVEL_SAUDE_BUCAL", "Responsável pela Saúde Bucal"),
            ("GESTOR", "Gestor"),
        ],
        validators=[DataRequired(message="Selecione um perfil.")],
    )

    submit = SubmitField("Salvar")


class RedefinirSenhaForm(FlaskForm):
    """Formulário mínimo para o ADMINISTRADOR definir uma nova senha para outro usuário..."""

    nova_senha = PasswordField(
        "Nova senha",
        validators=[
            DataRequired(message="Informe a nova senha."),
            Length(min=8, max=255, message="A senha deve ter no mínimo 8 caracteres."),
        ],
    )
    confirmar_senha = PasswordField(
        "Confirmar nova senha",
        validators=[DataRequired(message="Confirme a nova senha.")],
    )
    submit = SubmitField("Redefinir senha")

    def validate_confirmar_senha(self, field):
        if field.data != self.nova_senha.data:
            raise ValidationError("As senhas informadas não conferem.")
