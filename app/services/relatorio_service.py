"""
Geração de relatórios em CSV (Requisito 4 — relatórios a exportar).

Três relatórios, um por entidade: unidades, serviços e equipamentos.
O CSV sai em UTF-8 com BOM (abre direto no Excel com acentos).

SEGURANÇA (SEC-008 de docs/SEGURANCA.md): como agora o ORIS GERA um
arquivo com dados que vieram de planilhas importadas, toda célula de
texto que começa com `=`, `+`, `-`, `@`, TAB ou CR recebe um apóstrofo
na frente, neutralizando *formula injection* quando alguém abrir o
arquivo no Excel/Sheets.
"""

import csv
import io

from app.models import Equipamento, Servico, Unidade
from app.utils.datetime_utils import utcnow

ENTIDADES_RELATORIO = ("unidades", "servicos", "equipamentos")

_PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")


def sanitizar_celula(valor):
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "SIM" if valor else "NAO"
    if hasattr(valor, "value"):  # Enum
        valor = valor.value
    texto = str(valor)
    if texto.startswith(_PERIGOSOS):
        return "'" + texto
    return texto


def _linhas_unidades():
    cabecalho = ["id", "nome", "cnes", "unidade_mista", "tipo", "endereco", "bairro", "cidade", "uf", "situacao"]
    linhas = [
        [u.id, u.nome, u.cnes, u.unidade_e_mista, u.tipo, u.endereco, u.bairro, u.cidade, u.uf, u.situacao]
        for u in Unidade.query.order_by(Unidade.nome).all()
    ]
    return cabecalho, linhas


def _linhas_servicos():
    cabecalho = ["id", "nome", "unidade_id", "unidade", "situacao"]
    linhas = [
        [s.id, s.nome, s.unidade_id, s.unidade.nome if s.unidade else "", s.situacao]
        for s in Servico.query.order_by(Servico.nome).all()
    ]
    return cabecalho, linhas


def _linhas_equipamentos():
    cabecalho = ["id", "nome", "tipo", "unidade_id", "unidade", "servico_id", "servico", "situacao"]
    linhas = [
        [
            e.id, e.nome, e.tipo, e.unidade_id, e.unidade.nome if e.unidade else "",
            e.servico_id, e.servico.nome if e.servico else "", e.situacao,
        ]
        for e in Equipamento.query.order_by(Equipamento.nome).all()
    ]
    return cabecalho, linhas


_GERADORES = {
    "unidades": _linhas_unidades,
    "servicos": _linhas_servicos,
    "equipamentos": _linhas_equipamentos,
}


def gerar_csv(entidade):
    """Devolve (nome_do_arquivo, bytes). `entidade` precisa estar em
    ENTIDADES_RELATORIO (quem chama valida; aqui um valor inválido
    levanta ValueError)."""
    if entidade not in _GERADORES:
        raise ValueError("Entidade de relatório desconhecida.")

    cabecalho, linhas = _GERADORES[entidade]()
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow([sanitizar_celula(c) for c in linha])

    carimbo = utcnow().strftime("%Y%m%d-%H%M%S")
    nome_arquivo = f"oris-{entidade}-{carimbo}.csv"
    return nome_arquivo, ("﻿" + buffer.getvalue()).encode("utf-8")
