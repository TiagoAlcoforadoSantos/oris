"""
Formulários do módulo BD (Etapa 03). Reaproveitam as mesmas regras de
validação do restante do ORIS (ex.: regex do CNES).
"""

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional, Regexp

from app.forms import CNES_REGEX


def coerce_opcional_int(valor):
    if valor in (None, "", "None"):
        return None
    return int(valor)


SITUACOES_UNIDADE = [("ATIVA", "Ativa"), ("INATIVA", "Inativa"), ("MANUTENCAO", "Manutenção")]
SITUACOES_ATIVO = [("ATIVO", "Ativo"), ("INATIVO", "Inativo")]


class UnidadeBDForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(message="Informe o nome."), Length(max=200)])
    cnes = StringField("CNES", validators=[
        DataRequired(message="Informe o CNES."),
        Regexp(CNES_REGEX, message="CNES deve ter só números (7 a 15 dígitos)."),
    ])
    unidade_e_mista = BooleanField("Unidade mista (CNES compartilhado)")
    tipo = StringField("Tipo", validators=[DataRequired(message="Informe o tipo."), Length(max=100)])
    endereco = StringField("Endereço", validators=[Optional(), Length(max=255)])
    bairro = StringField("Bairro", validators=[Optional(), Length(max=100)])
    cidade = StringField("Cidade", validators=[DataRequired(message="Informe a cidade."), Length(max=100)])
    uf = StringField("UF", validators=[
        DataRequired(message="Informe a UF."),
        Length(min=2, max=2, message="UF deve ter 2 letras."),
    ])
    situacao = SelectField("Situação", choices=SITUACOES_UNIDADE)
    submit = SubmitField("Salvar")

    def dados(self):
        def limpo(campo):
            valor = (campo.data or "").strip()
            return valor or None
        return {
            "nome": limpo(self.nome),
            "cnes": limpo(self.cnes),
            "unidade_e_mista": 1 if self.unidade_e_mista.data else 0,
            "tipo": limpo(self.tipo),
            "endereco": limpo(self.endereco),
            "bairro": limpo(self.bairro),
            "cidade": limpo(self.cidade),
            "uf": (self.uf.data or "").strip().upper(),
            "situacao": self.situacao.data,
        }


class ServicoBDForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(message="Informe o nome."), Length(max=150)])
    unidade_id = SelectField("Unidade (opcional)", choices=[], coerce=coerce_opcional_int)
    situacao = SelectField("Situação", choices=SITUACOES_ATIVO)
    submit = SubmitField("Salvar")

    def dados(self):
        return {"nome": self.nome.data.strip(), "unidade_id": self.unidade_id.data,
                "situacao": self.situacao.data}


class EquipamentoBDForm(FlaskForm):
    nome = StringField("Nome", validators=[DataRequired(message="Informe o nome."), Length(max=150)])
    tipo = StringField("Tipo", validators=[DataRequired(message="Informe o tipo."), Length(max=100)])
    unidade_id = SelectField("Unidade (opcional)", choices=[], coerce=coerce_opcional_int)
    servico_id = SelectField("Serviço (opcional)", choices=[], coerce=coerce_opcional_int)
    situacao = SelectField("Situação", choices=SITUACOES_ATIVO)
    submit = SubmitField("Salvar")

    def dados(self):
        return {"nome": self.nome.data.strip(), "tipo": self.tipo.data.strip(),
                "unidade_id": self.unidade_id.data, "servico_id": self.servico_id.data,
                "situacao": self.situacao.data}


class ExcluirForm(FlaskForm):
    """Só carrega o token CSRF — DELETE sempre via POST."""
    submit = SubmitField("Excluir")
