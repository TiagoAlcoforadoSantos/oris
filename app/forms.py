"""
Formulários da aplicação ORIS.

Usar Flask-WTF garante proteção CSRF automática nos formulários,
sem precisar implementar nada manualmente.
"""

from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Regexp, ValidationError

# Regex do CNES, compartilhada com o importador de planilhas (Fase 10)
# em app/services/importacao_service.py — mantida em um único lugar
# para nunca divergir da validação usada no cadastro manual.
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


def _coerce_opcional_int(valor):
    """Converte o valor de um SelectField para int, tratando string
    vazia (opção "Nenhum") como None. Usado no campo `servico_id` de
    Equipamento, que é opcional."""
    if valor in (None, "", "None"):
        return None
    return int(valor)


class ServicoForm(FlaskForm):
    """Formulário de cadastro/edição de Serviço de Saúde Bucal.

    A lista de unidades disponíveis (`unidade_id.choices`) é
    preenchida na rota (app/routes/servicos.py), com as unidades
    existentes no momento da requisição — isso faz o próprio
    WTForms rejeitar automaticamente uma unidade inexistente (ela
    simplesmente não está entre as opções válidas).
    """

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
    """Formulário de cadastro/edição de Equipamento.

    `unidade_id.choices` e `servico_id.choices` são preenchidos na
    rota (app/routes/equipamentos.py) com os dados existentes no
    momento da requisição. `servico_id` é opcional — a opção
    "Nenhum" equivale a None.

    A regra de que o serviço selecionado precisa pertencer à unidade
    selecionada depende dos dois campos ao mesmo tempo, então é
    validada na rota, e não aqui no formulário.
    """

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
    """Formulário simples para alterar a situação (ATIVO/INATIVO) de
    um Serviço ou Equipamento já existente."""

    situacao = SelectField(
        "Nova situação",
        choices=[("ATIVO", "Ativo"), ("INATIVO", "Inativo")],
        validators=[DataRequired(message="Selecione uma situação.")],
    )
    submit = SubmitField("Alterar situação")


class AcaoAlteracaoForm(FlaskForm):
    """Formulário mínimo, usado só para dar proteção CSRF aos botões
    de aprovar/rejeitar uma Alteração (Fase 7) — não tem campos de
    dados, só o token CSRF embutido pelo FlaskForm."""

    submit = SubmitField("Confirmar")


class CriarUsuarioForm(FlaskForm):
    """Formulário de criação de usuário (Fase 11 — Administração de
    Usuários). A unicidade do email é verificada à parte, na rota,
    para dar uma mensagem amigável específica.

    Regra mínima de senha: o projeto não tinha, até esta fase, uma
    regra de tamanho mínimo para senha (o LoginForm só exige que o
    campo não esteja vazio). Para o cadastro administrativo de um
    novo usuário, adotamos um mínimo de 8 caracteres — a mesma ideia
    de "regra mínima de segurança" pedida pela Fase 11, aplicada pela
    primeira vez aqui e documentada no README.
    """

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
    """Formulário de edição de usuário — só nome, email e perfil. A
    situação (ativo/inativo) tem sua própria rota/botão dedicado
    (`/usuarios/<id>/situacao`), seguindo o mesmo padrão já usado em
    Unidade/Serviço/Equipamento. A senha também não é editada aqui —
    ver `RedefinirSenhaForm`."""

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
    """Formulário mínimo para o ADMINISTRADOR definir uma nova senha
    para outro usuário (Fase 11, item 8). A senha nunca é exibida de
    volta — este formulário só recebe a nova senha e a confirmação."""

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
