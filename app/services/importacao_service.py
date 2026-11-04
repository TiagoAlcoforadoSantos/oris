"""Serviço central do importador de planilhas (Fase 10; adaptado na Stage "importador x..."""

import re
import unicodedata

import pandas as pd

from app.forms import CNES_REGEX
from app.models import Equipamento, Servico, SituacaoAtivoInativo, SituacaoUnidade, Unidade

LIMITE_TAMANHO_BYTES = 5 * 1024 * 1024  # 5 MB
LIMITE_LINHAS = 2000
LINHAS_PREVIA = 50

EXTENSOES_ACEITAS = (".csv", ".xlsx")

_CNES_REGEX_COMPILADO = re.compile(CNES_REGEX)


class ArquivoInvalidoError(Exception):
    """Erro amigável de leitura do arquivo (formato, vazio, corrompido, sem cabeçalho,..."""


CAMPOS_POR_ENTIDADE = {
    "unidades": {
        "obrigatorios": ["nome", "cnes", "cidade", "uf", "situacao"],
        "opcionais": ["tipo", "endereco", "bairro"],
    },
    "servicos": {
        "obrigatorios": ["nome", "situacao"],
        "opcionais": ["unidade_cnes"],
    },
    "equipamentos": {
        "obrigatorios": ["nome", "tipo", "situacao"],
        "opcionais": ["servico_nome", "unidade_cnes"],
    },
    "rede": {
        "obrigatorios": ["nome", "cnes", "unidade_flag", "equipamento_flag"],
        "opcionais": [
            "tipo_equipamento",
            "tipo_servico",
            "unidade_mista",
            "nome_curto",
            "ds",
            "endereco",
            "bairro",
            "ativo",
        ],
    },
}

RÓTULOS_CAMPOS = {
    "nome": "Nome",
    "cnes": "CNES",
    "tipo": "Tipo",
    "endereco": "Endereço",
    "bairro": "Bairro",
    "cidade": "Cidade",
    "uf": "UF",
    "situacao": "Situação",
    "unidade_cnes": "CNES da Unidade",
    "servico_nome": "Nome do Serviço (opcional)",
    "unidade_flag": "Unidade (S/N)",
    "equipamento_flag": "Equipamento de Saúde (S/N)",
    "tipo_equipamento": "Tipo de Equipamento",
    "tipo_servico": "Tipo de Serviço",
    "unidade_mista": "Unidade é Mista? (S/N)",
    "nome_curto": "Nome Curto",
    "ds": "DS",
    "ativo": "Ativo (S/N)",
}

_SINONIMOS = {
    "nome": ["nome", "nome da unidade", "nome do servico", "nome do equipamento", "descricao"],
    "cnes": ["cnes", "codigo cnes", "código cnes"],
    "tipo": ["tipo"],
    "endereco": ["endereco", "endereço"],
    "bairro": ["bairro"],
    "cidade": ["cidade", "municipio", "município"],
    "uf": ["uf", "estado"],
    "situacao": ["situacao", "situação", "status"],
    "unidade_cnes": ["unidade", "cnes da unidade", "cnes unidade", "unidade (cnes)"],
    "servico_nome": ["servico", "serviço", "nome do servico", "nome do serviço"],
    "unidade_flag": ["unidade"],
    "equipamento_flag": ["equipamento de saude", "equipamento de saúde", "equipamento"],
    "tipo_equipamento": ["tipo equipamento", "tipo do equipamento"],
    "tipo_servico": ["tipo servico", "tipo serviço"],
    "unidade_mista": ["unidade e mista", "unidade é mista", "unidade e mista?", "unidade é mista?", "mista"],
    "nome_curto": ["nome curto"],
    "ds": ["ds", "distrito sanitario", "distrito sanitário"],
    "ativo": ["ativo"],
}


def _normalizar_texto(valor):
    """Normaliza um texto para comparação"""
    if valor is None:
        return ""
    texto = str(valor).strip()
    texto_sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto_sem_acento.strip().lower()


def ler_planilha(caminho, extensao):
    """Lê o arquivo (.csv ou .xlsx) e devolve um DataFrame do pandas, com todas as..."""
    try:
        if extensao == ".csv":
            df = pd.read_csv(caminho, dtype=str, keep_default_na=False, sep=None, engine="python")
        else:
            df = pd.read_excel(caminho, dtype=str, engine="openpyxl")
            df = df.fillna("")
    except Exception as erro:
        raise ArquivoInvalidoError(
            "Não foi possível ler o arquivo — verifique se ele não está corrompido "
            "e se o formato corresponde à extensão enviada."
        ) from erro

    if df.shape[1] == 0:
        raise ArquivoInvalidoError("A planilha está vazia.")

    if all(re.match(r"^Unnamed: \d+$", str(coluna)) for coluna in df.columns):
        raise ArquivoInvalidoError("A planilha não possui uma linha de cabeçalho.")

    if df.shape[0] == 0:
        raise ArquivoInvalidoError("A planilha não possui nenhuma linha de dados.")

    if df.shape[0] > LIMITE_LINHAS:
        raise ArquivoInvalidoError(
            f"A planilha tem {df.shape[0]} linhas — o limite atual é de {LIMITE_LINHAS} "
            "linhas por importação."
        )

    return df


def detectar_mapeamento_automatico(colunas_planilha, entidade):
    """Sugere, para cada campo alvo da entidade, qual coluna da planilha corresponde a..."""
    campos = CAMPOS_POR_ENTIDADE[entidade]["obrigatorios"] + CAMPOS_POR_ENTIDADE[entidade]["opcionais"]
    colunas_normalizadas = {_normalizar_texto(coluna): coluna for coluna in colunas_planilha}

    mapeamento = {}
    for campo in campos:
        encontrado = None
        for sinonimo in _SINONIMOS.get(campo, [campo]):
            if sinonimo in colunas_normalizadas:
                encontrado = colunas_normalizadas[sinonimo]
                break
        mapeamento[campo] = encontrado
    return mapeamento


def aplicar_mapeamento(df, mapeamento):
    """Constrói a lista de linhas (uma por registro da planilha), cada uma com os..."""
    linhas = []
    for posicao, linha_original in df.iterrows():
        dados = {}
        for campo, coluna_planilha in mapeamento.items():
            if coluna_planilha:
                dados[campo] = str(linha_original.get(coluna_planilha, "")).strip()
            else:
                dados[campo] = ""
        linhas.append({"numero_linha": posicao + 2, "dados": dados})
    return linhas


def _erro(lista_erros, linha, campo, valor, motivo):
    lista_erros.append({"linha": linha, "campo": RÓTULOS_CAMPOS.get(campo, campo), "valor": valor, "motivo": motivo})


def _validar_linha_unidade(numero_linha, dados, lista_erros):
    erros_linha = []

    nome = dados.get("nome", "").strip()
    if not nome:
        _erro(lista_erros, numero_linha, "nome", nome, "Nome é obrigatório.")
        erros_linha.append("nome")

    cnes = dados.get("cnes", "").strip()
    if not cnes:
        _erro(lista_erros, numero_linha, "cnes", cnes, "CNES é obrigatório.")
        erros_linha.append("cnes")
    elif not _CNES_REGEX_COMPILADO.match(cnes):
        _erro(lista_erros, numero_linha, "cnes", cnes, "CNES deve conter apenas números (7 a 15 dígitos).")
        erros_linha.append("cnes")

    cidade = dados.get("cidade", "").strip()
    if not cidade:
        _erro(lista_erros, numero_linha, "cidade", cidade, "Cidade é obrigatória.")
        erros_linha.append("cidade")

    uf = dados.get("uf", "").strip().upper()
    if not uf:
        _erro(lista_erros, numero_linha, "uf", uf, "UF é obrigatória.")
        erros_linha.append("uf")
    elif len(uf) != 2:
        _erro(lista_erros, numero_linha, "uf", dados.get("uf", ""), "Informe a sigla da UF (ex.: PE).")
        erros_linha.append("uf")

    situacao_bruta = dados.get("situacao", "").strip().upper()
    if not situacao_bruta:
        _erro(lista_erros, numero_linha, "situacao", situacao_bruta, "Situação é obrigatória.")
        erros_linha.append("situacao")
    elif situacao_bruta not in {item.value for item in SituacaoUnidade}:
        _erro(
            lista_erros, numero_linha, "situacao", dados.get("situacao", ""),
            "Situação deve ser ATIVA, INATIVA ou MANUTENCAO.",
        )
        erros_linha.append("situacao")

    dados_normalizados = {
        "nome": nome,
        "cnes": cnes,
        "tipo": dados.get("tipo", "").strip() or "Não informado",
        "endereco": dados.get("endereco", "").strip() or None,
        "bairro": dados.get("bairro", "").strip() or None,
        "cidade": cidade,
        "uf": uf,
        "situacao": situacao_bruta,
    }

    return (len(erros_linha) == 0), dados_normalizados


def _classificar_unidade(dados_normalizados):
    existente = Unidade.query.filter_by(cnes=dados_normalizados["cnes"]).first()
    if existente is None:
        return "novo", None

    campos_comparaveis = ["nome", "tipo", "endereco", "bairro", "cidade", "uf", "situacao"]
    for campo in campos_comparaveis:
        valor_atual = getattr(existente, campo)
        valor_atual = valor_atual.value if hasattr(valor_atual, "value") else valor_atual
        if str(valor_atual or "") != str(dados_normalizados[campo] or ""):
            return "alterado", existente

    return "sem_alteracao", existente


def _validar_linha_servico(numero_linha, dados, chaves_vistas, lista_erros):
    erros_linha = []

    nome = dados.get("nome", "").strip()
    if not nome:
        _erro(lista_erros, numero_linha, "nome", nome, "Nome é obrigatório.")
        erros_linha.append("nome")

    unidade_cnes = dados.get("unidade_cnes", "").strip()
    unidade = None
    if unidade_cnes:
        unidade = Unidade.query.filter_by(cnes=unidade_cnes).first()
        if unidade is None:
            _erro(
                lista_erros, numero_linha, "unidade_cnes", unidade_cnes,
                "Nenhuma unidade encontrada com este CNES.",
            )
            erros_linha.append("unidade_cnes")

    situacao_bruta = dados.get("situacao", "").strip().upper()
    if not situacao_bruta:
        _erro(lista_erros, numero_linha, "situacao", situacao_bruta, "Situação é obrigatória.")
        erros_linha.append("situacao")
    elif situacao_bruta not in {item.value for item in SituacaoAtivoInativo}:
        _erro(lista_erros, numero_linha, "situacao", dados.get("situacao", ""), "Situação deve ser ATIVO ou INATIVO.")
        erros_linha.append("situacao")

    if nome:
        chave = (_normalizar_texto(nome), unidade.id if unidade else None)
        if chave in chaves_vistas:
            _erro(lista_erros, numero_linha, "nome", nome, "Serviço duplicado (mesmo nome e unidade) dentro desta planilha.")
            erros_linha.append("nome")
        else:
            chaves_vistas.add(chave)

    dados_normalizados = {
        "nome": nome,
        "unidade_id": unidade.id if unidade else None,
        "situacao": situacao_bruta,
    }
    return (len(erros_linha) == 0), dados_normalizados, unidade


def _classificar_servico(dados_normalizados):
    existente = Servico.query.filter_by(
        unidade_id=dados_normalizados["unidade_id"],
    ).filter(
        Servico.nome.ilike(dados_normalizados["nome"])
    ).first()

    if existente is None:
        return "novo", None

    if str(existente.situacao.value) != str(dados_normalizados["situacao"]):
        return "alterado", existente

    return "sem_alteracao", existente


def _validar_linha_equipamento(numero_linha, dados, chaves_vistas, lista_erros):
    erros_linha = []

    nome = dados.get("nome", "").strip()
    if not nome:
        _erro(lista_erros, numero_linha, "nome", nome, "Nome é obrigatório.")
        erros_linha.append("nome")

    tipo = dados.get("tipo", "").strip()
    if not tipo:
        _erro(lista_erros, numero_linha, "tipo", tipo, "Tipo é obrigatório.")
        erros_linha.append("tipo")

    unidade_cnes = dados.get("unidade_cnes", "").strip()
    unidade = None
    if unidade_cnes:
        unidade = Unidade.query.filter_by(cnes=unidade_cnes).first()
        if unidade is None:
            _erro(
                lista_erros, numero_linha, "unidade_cnes", unidade_cnes,
                "Nenhuma unidade encontrada com este CNES.",
            )
            erros_linha.append("unidade_cnes")

    servico = None
    servico_nome = dados.get("servico_nome", "").strip()
    if servico_nome and unidade is not None:
        servico = Servico.query.filter_by(unidade_id=unidade.id).filter(Servico.nome.ilike(servico_nome)).first()
        if servico is None:
            _erro(
                lista_erros, numero_linha, "servico_nome", servico_nome,
                "Nenhum serviço com este nome foi encontrado nessa unidade.",
            )
            erros_linha.append("servico_nome")

    situacao_bruta = dados.get("situacao", "").strip().upper()
    if not situacao_bruta:
        _erro(lista_erros, numero_linha, "situacao", situacao_bruta, "Situação é obrigatória.")
        erros_linha.append("situacao")
    elif situacao_bruta not in {item.value for item in SituacaoAtivoInativo}:
        _erro(lista_erros, numero_linha, "situacao", dados.get("situacao", ""), "Situação deve ser ATIVO ou INATIVO.")
        erros_linha.append("situacao")

    if nome:
        chave = (_normalizar_texto(nome), unidade.id if unidade else None)
        if chave in chaves_vistas:
            _erro(
                lista_erros, numero_linha, "nome", nome,
                "Equipamento duplicado (mesmo nome e unidade) dentro desta planilha.",
            )
            erros_linha.append("nome")
        else:
            chaves_vistas.add(chave)

    dados_normalizados = {
        "nome": nome,
        "tipo": tipo,
        "unidade_id": unidade.id if unidade else None,
        "servico_id": servico.id if servico else None,
        "situacao": situacao_bruta,
    }
    return (len(erros_linha) == 0), dados_normalizados


def _classificar_equipamento(dados_normalizados):
    existente = Equipamento.query.filter_by(
        unidade_id=dados_normalizados["unidade_id"],
    ).filter(
        Equipamento.nome.ilike(dados_normalizados["nome"])
    ).first()

    if existente is None:
        return "novo", None

    campos_comparaveis = ["tipo", "servico_id", "situacao"]
    for campo in campos_comparaveis:
        valor_atual = getattr(existente, campo)
        valor_atual = valor_atual.value if hasattr(valor_atual, "value") else valor_atual
        if str(valor_atual or "") != str(dados_normalizados[campo] or ""):
            return "alterado", existente

    return "sem_alteracao", existente


_TIPOS_REGISTRO_REDE = ("UNIDADE", "SERVICO", "EQUIPAMENTO")


def _texto_e_verdadeiro(valor):
    """'S'/'Sim'/'Yes'/'1'/'true' (sem acento, case-insensitive) -> True."""
    return _normalizar_texto(valor) in {"s", "sim", "yes", "y", "1", "true"}


def _texto_e_falso_explicito(valor):
    """'N'/'Nao'/'No'/'0'/'false' -> True."""
    return _normalizar_texto(valor) in {"n", "nao", "no", "0", "false"}


def _ativo_para_situacao_unidade(valor):
    return SituacaoUnidade.INATIVA.value if _texto_e_falso_explicito(valor) else SituacaoUnidade.ATIVA.value


def _ativo_para_situacao_simples(valor):
    return SituacaoAtivoInativo.INATIVO.value if _texto_e_falso_explicito(valor) else SituacaoAtivoInativo.ATIVO.value


def _validar_linha_rede(numero_linha, dados, lista_erros):
    """Classifica uma linha do formato unificado em 0..3 sub-registros ..."""
    e_unidade = _texto_e_verdadeiro(dados.get("unidade_flag", ""))
    e_equipamento = _texto_e_verdadeiro(dados.get("equipamento_flag", ""))
    tipo_servico = dados.get("tipo_servico", "").strip()
    e_servico = bool(tipo_servico) and not e_equipamento

    if not (e_unidade or e_equipamento or e_servico):
        _erro(
            lista_erros, numero_linha, "unidade_flag", "",
            "Linha sem dados suficientes para identificar o tipo de registro "
            "(nenhum indicador de Unidade, Equipamento ou Serviço preenchido).",
        )
        return None

    nome = dados.get("nome", "").strip()
    cnes = dados.get("cnes", "").strip()
    erros_linha = []

    if not cnes:
        _erro(lista_erros, numero_linha, "cnes", cnes, "CNES é obrigatório.")
        erros_linha.append("cnes")
    elif not _CNES_REGEX_COMPILADO.match(cnes):
        _erro(lista_erros, numero_linha, "cnes", cnes, "CNES deve conter apenas números (7 a 15 dígitos).")
        erros_linha.append("cnes")

    if (e_unidade or e_equipamento) and not nome:
        _erro(
            lista_erros, numero_linha, "nome", nome,
            "Nome é obrigatório para registro de Unidade ou Equipamento.",
        )
        erros_linha.append("nome")

    if erros_linha:
        return None

    registros = []

    if e_unidade:
        registros.append({
            "tipo": "UNIDADE",
            "dados": {
                "nome": nome,
                "cnes": cnes,
                "unidade_e_mista": _texto_e_verdadeiro(dados.get("unidade_mista", "")),
                "endereco": dados.get("endereco", "").strip() or None,
                "bairro": dados.get("bairro", "").strip() or None,
                "cidade": None,
                "uf": None,
                "situacao": _ativo_para_situacao_unidade(dados.get("ativo", "")),
            },
        })

    if e_servico:
        registros.append({
            "tipo": "SERVICO",
            "dados": {
                "nome": tipo_servico,
                "unidade_id": None,
                "situacao": _ativo_para_situacao_simples(dados.get("ativo", "")),
            },
        })

    if e_equipamento:
        registros.append({
            "tipo": "EQUIPAMENTO",
            "dados": {
                "nome": nome,
                "tipo": dados.get("tipo_equipamento", "").strip() or None,
                "unidade_id": None,
                "servico_id": None,
                "situacao": _ativo_para_situacao_simples(dados.get("ativo", "")),
            },
        })

    return registros


def _aviso(lista_avisos, linha, mensagem):
    lista_avisos.append({"linha": linha, "mensagem": mensagem})


def _resolver_vinculo_unidade_existente(cnes, numero_linha, lista_avisos, contexto):
    """Vínculo com Unidade só é aplicado quando 'seguro'"""
    candidatas = Unidade.query.filter_by(cnes=cnes).all()
    if len(candidatas) == 1:
        return candidatas[0].id
    if len(candidatas) > 1:
        _aviso(
            lista_avisos, numero_linha,
            f"Relação ambígua: CNES '{cnes}' corresponde a {len(candidatas)} unidades já "
            f"cadastradas — vínculo de {contexto} com Unidade não aplicado automaticamente; "
            "revise manualmente.",
        )
    return None


def _resolver_vinculos_rede(dados, registros, lista_avisos, numero_linha):
    """Resolve, quando seguro, os vínculos entre os sub-registros produzidos por..."""
    e_unidade = any(registro["tipo"] == "UNIDADE" for registro in registros)
    e_servico = any(registro["tipo"] == "SERVICO" for registro in registros)
    e_equipamento = any(registro["tipo"] == "EQUIPAMENTO" for registro in registros)
    cnes = dados.get("cnes", "").strip()

    if e_unidade:
        if e_servico or e_equipamento:
            _aviso(
                lista_avisos, numero_linha,
                "Esta linha também cria uma Unidade nova — o vínculo com o(s) "
                "Serviço/Equipamento desta mesma linha não pôde ser aplicado "
                "automaticamente (a Unidade ainda não existe antes da aprovação); "
                "vincule manualmente após aprovar os registros.",
            )
    elif (e_servico or e_equipamento) and cnes:
        unidade_id = _resolver_vinculo_unidade_existente(cnes, numero_linha, lista_avisos, "Serviço/Equipamento")
        if unidade_id is not None:
            for registro in registros:
                if registro["tipo"] in ("SERVICO", "EQUIPAMENTO"):
                    registro["dados"]["unidade_id"] = unidade_id

    if e_equipamento:
        tipo_servico = dados.get("tipo_servico", "").strip()
        if tipo_servico:
            candidatos = Servico.query.filter(Servico.nome.ilike(tipo_servico)).all()
            if len(candidatos) == 1:
                for registro in registros:
                    if registro["tipo"] == "EQUIPAMENTO":
                        registro["dados"]["servico_id"] = candidatos[0].id
            elif len(candidatos) > 1:
                _aviso(
                        lista_avisos, numero_linha,
                        f"Relação ambígua: Tipo de Serviço '{tipo_servico}' corresponde a "
                        f"{len(candidatos)} serviços já cadastrados — vínculo do Equipamento "
                        "com Serviço não aplicado automaticamente; revise manualmente.",
                    )


_TIPO_REGISTRO_POR_ENTIDADE_SIMPLES = {
    "unidades": "UNIDADE",
    "servicos": "SERVICO",
    "equipamentos": "EQUIPAMENTO",
}


def validar_e_classificar(df, mapeamento, entidade):
    """Valida e classifica todas as linhas do DataFrame conforme a entidade."""
    linhas_mapeadas = aplicar_mapeamento(df, mapeamento)

    erros = []
    avisos = []
    linhas_resultado = []
    chaves_vistas = set()

    for item in linhas_mapeadas:
        numero_linha = item["numero_linha"]
        dados = item["dados"]

        if entidade == "rede":
            registros = _validar_linha_rede(numero_linha, dados, erros)
            if registros is None:
                linhas_resultado.append(
                    {
                        "numero_linha": numero_linha,
                        "dados": {},
                        "valido": False,
                        "classificacao": "invalido",
                        "tipo": None,
                        "registro_existente_id": None,
                    }
                )
                continue

            _resolver_vinculos_rede(dados, registros, avisos, numero_linha)
            for registro in registros:
                linhas_resultado.append(
                    {
                        "numero_linha": numero_linha,
                        "dados": registro["dados"],
                        "valido": True,
                        "classificacao": "novo",
                        "tipo": registro["tipo"],
                        "registro_existente_id": None,
                    }
                )
            continue

        if entidade == "unidades":
            valido, dados_normalizados = _validar_linha_unidade(numero_linha, dados, erros)
            registro_existente = None
            classificacao = None
            if valido:
                classificacao, registro_existente = _classificar_unidade(dados_normalizados)
        elif entidade == "servicos":
            valido, dados_normalizados, _unidade = _validar_linha_servico(numero_linha, dados, chaves_vistas, erros)
            registro_existente = None
            classificacao = None
            if valido:
                classificacao, registro_existente = _classificar_servico(dados_normalizados)
        else:  # equipamentos
            valido, dados_normalizados = _validar_linha_equipamento(numero_linha, dados, chaves_vistas, erros)
            registro_existente = None
            classificacao = None
            if valido:
                classificacao, registro_existente = _classificar_equipamento(dados_normalizados)

        linhas_resultado.append(
            {
                "numero_linha": numero_linha,
                "dados": dados_normalizados,
                "valido": valido,
                "classificacao": classificacao if valido else "invalido",
                "tipo": _TIPO_REGISTRO_POR_ENTIDADE_SIMPLES[entidade] if valido else None,
                "registro_existente_id": registro_existente.id if registro_existente else None,
            }
        )

    total = len(linhas_resultado)
    invalidos = sum(1 for linha in linhas_resultado if not linha["valido"])
    validos = total - invalidos

    return {
        "total": total,
        "validos": validos,
        "invalidos": invalidos,
        "erros": erros,
        "avisos": avisos,
        "linhas": linhas_resultado,
    }
