"""
Serviço central do importador de planilhas (Fase 10).

Concentra aqui toda a lógica de leitura, mapeamento de colunas e
validação das planilhas de Unidades/Serviços/Equipamentos — as
rotas (app/routes/importacao.py) só orquestram o fluxo (upload,
telas, chamadas ao serviço de alterações).

DECISÃO DE DESIGN — reconciliação (novo/existente/alterado):
Unidades são identificadas por CNES (campo único já existente).
Serviços e Equipamentos não têm um código único próprio, então são
identificados pela combinação (nome, unidade) — a mesma unidade não
deveria ter dois serviços/equipamentos de mesmo nome. Isso NÃO é uma
reconciliação complexa: é só uma chave de igualdade simples, usada
para decidir se uma linha da planilha é um registro novo ou uma
atualização de um já existente.

DECISÃO DE DESIGN — "CNES já cadastrado" como erro vs. atualização:
O enunciado desta fase cita "CNES já cadastrado" como exemplo de erro
de validação, mas também pede para o importador diferenciar
novo/existente/alterado usando o CNES como referência — as duas
coisas juntas seriam contraditórias se um CNES existente fosse
sempre um erro. A leitura que faz as duas partes fazerem sentido
juntas: um CNES que já existe NO BANCO é uma ATUALIZAÇÃO (o caminho
normal de reconciliação); um CNES DUPLICADO DENTRO DA MESMA PLANILHA
é que é tratado como erro, porque nesse caso não há como saber com
qual das duas linhas ficar. Essa decisão está documentada aqui e no
README.

Nenhum registro é escrito no banco por este serviço — ele só lê o
arquivo e retorna a classificação de cada linha. A escrita de fato
acontece via app.services.alteracoes_service.registrar_alteracao,
chamado pela rota de confirmação, respeitando o fluxo de aprovação
da Fase 7.
"""

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
    """Erro amigável de leitura do arquivo (formato, vazio, corrompido,
    sem cabeçalho, sem dados, ou excesso de linhas) — sempre com uma
    mensagem adequada para ser exibida diretamente ao usuário."""


# ----------------------------------------------------------------
# Campos por entidade e sinônimos para o mapeamento automático
# ----------------------------------------------------------------

CAMPOS_POR_ENTIDADE = {
    "unidades": {
        "obrigatorios": ["nome", "cnes", "cidade", "uf", "situacao"],
        "opcionais": ["tipo", "endereco", "bairro"],
    },
    "servicos": {
        "obrigatorios": ["nome", "unidade_cnes", "situacao"],
        "opcionais": [],
    },
    "equipamentos": {
        "obrigatorios": ["nome", "tipo", "unidade_cnes", "situacao"],
        "opcionais": ["servico_nome"],
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
}


def _normalizar_texto(valor):
    """Normaliza um texto para comparação: remove acentos, espaços nas
    pontas e coloca em minúsculas. Usado tanto para casar nomes de
    colunas quanto para comparar valores textuais (situação, nomes)."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    texto_sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto_sem_acento.strip().lower()


# ----------------------------------------------------------------
# Leitura do arquivo
# ----------------------------------------------------------------

def ler_planilha(caminho, extensao):
    """Lê o arquivo (.csv ou .xlsx) e devolve um DataFrame do pandas,
    com todas as células como texto (evita o pandas "inventar" tipos
    numéricos para campos como CNES). Lança ArquivoInvalidoError com
    uma mensagem amigável para qualquer problema de leitura."""
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

    # Quando não há um cabeçalho de verdade, o pandas nomeia as
    # colunas como "Unnamed: 0", "Unnamed: 1"... — se TODAS as
    # colunas caírem nesse padrão, tratamos como planilha sem
    # cabeçalho, em vez de tentar mapear nomes sem sentido.
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


# ----------------------------------------------------------------
# Mapeamento de colunas
# ----------------------------------------------------------------

def detectar_mapeamento_automatico(colunas_planilha, entidade):
    """Sugere, para cada campo alvo da entidade, qual coluna da
    planilha corresponde a ele — por comparação exata de nome
    normalizado com os sinônimos conhecidos. Nunca adivinha por
    semelhança aproximada; se não achar uma correspondência exata,
    deixa em branco para o usuário escolher manualmente."""
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
    """Constrói a lista de linhas (uma por registro da planilha),
    cada uma com os campos-alvo já renomeados conforme o mapeamento
    escolhido. `numero_linha` conta a partir de 2 (linha 1 é o
    cabeçalho), para bater com o que o usuário vê ao abrir a
    planilha."""
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


# ----------------------------------------------------------------
# Validação e classificação (novo / alterado / sem_alteracao)
# ----------------------------------------------------------------

def _erro(lista_erros, linha, campo, valor, motivo):
    lista_erros.append({"linha": linha, "campo": RÓTULOS_CAMPOS.get(campo, campo), "valor": valor, "motivo": motivo})


def _validar_linha_unidade(numero_linha, dados, cnes_vistos, lista_erros):
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
    elif cnes in cnes_vistos:
        _erro(lista_erros, numero_linha, "cnes", cnes, "CNES duplicado dentro desta planilha.")
        erros_linha.append("cnes")
    else:
        cnes_vistos.add(cnes)

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
    if not unidade_cnes:
        _erro(lista_erros, numero_linha, "unidade_cnes", unidade_cnes, "CNES da unidade é obrigatório.")
        erros_linha.append("unidade_cnes")
    else:
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

    if unidade is not None and nome:
        chave = (_normalizar_texto(nome), unidade.id)
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
    if not unidade_cnes:
        _erro(lista_erros, numero_linha, "unidade_cnes", unidade_cnes, "CNES da unidade é obrigatório.")
        erros_linha.append("unidade_cnes")
    else:
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

    if unidade is not None and nome:
        chave = (_normalizar_texto(nome), unidade.id)
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


def validar_e_classificar(df, mapeamento, entidade):
    """Valida e classifica todas as linhas do DataFrame conforme a
    entidade. Retorna um dict com o resumo (totais), a lista de erros
    (linha/campo/valor/motivo) e a lista de linhas processadas — cada
    uma com sua classificação (novo/alterado/sem_alteracao/invalido)
    e os dados já normalizados, prontos para virar uma Alteracao
    quando a importação for confirmada."""
    linhas_mapeadas = aplicar_mapeamento(df, mapeamento)

    erros = []
    linhas_resultado = []
    cnes_vistos = set()
    chaves_vistas = set()

    for item in linhas_mapeadas:
        numero_linha = item["numero_linha"]
        dados = item["dados"]

        if entidade == "unidades":
            valido, dados_normalizados = _validar_linha_unidade(numero_linha, dados, cnes_vistos, erros)
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
        "linhas": linhas_resultado,
    }
