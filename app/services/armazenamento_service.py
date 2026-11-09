"""
Exportação de relatórios para armazenamento em nuvem — Amazon S3
(Requisito 4).

AUTENTICAÇÃO: nenhuma credencial fica no código nem no .env do ORIS. O
boto3 resolve as credenciais pela cadeia padrão da AWS (variáveis de
ambiente AWS_*, perfil em ~/.aws ou IAM Role da instância). As
requisições são assinadas com AWS Signature V4 pelo próprio boto3.

PROTEÇÕES:
- criptografia em repouso (SSE-S3, AES256) em todo objeto enviado;
- a chave do objeto é montada só com valores controlados pelo sistema
  (prefixo de configuração + entidade da lista fixa + data + UUID) —
  nenhum texto vindo do usuário entra no caminho;
- o download é por URL pré-assinada de curta duração (padrão 15 min),
  sem tornar o bucket público;
- erros do provedor são registrados em log e nunca repassados ao
  usuário (podem conter nomes de bucket/contas).
"""

import uuid

from flask import current_app

from app.utils.datetime_utils import utcnow


class ArmazenamentoError(Exception):
    """Falha ao falar com o armazenamento em nuvem."""


def s3_configurado(config=None):
    config = config if config is not None else current_app.config
    return bool(config.get("S3_BUCKET"))


def _criar_cliente(config):
    import boto3

    opcoes = {}
    if config.get("S3_REGION"):
        opcoes["region_name"] = config["S3_REGION"]
    if config.get("S3_ENDPOINT_URL"):
        opcoes["endpoint_url"] = config["S3_ENDPOINT_URL"]
    return boto3.client("s3", **opcoes)


def montar_chave(entidade, config=None):
    config = config if config is not None else current_app.config
    prefixo = (config.get("S3_PREFIX") or "").strip("/")
    carimbo = utcnow().strftime("%Y/%m/%d")
    nome = f"{entidade}-{utcnow().strftime('%H%M%S')}-{uuid.uuid4().hex[:12]}.csv"
    return "/".join(parte for parte in (prefixo, entidade, carimbo, nome) if parte)


def enviar_relatorio(conteudo, entidade, cliente=None, config=None):
    """Envia o CSV ao bucket e devolve a chave do objeto. `cliente`
    permite injetar um cliente S3 (testes usam um falso)."""
    config = config if config is not None else current_app.config
    if not s3_configurado(config):
        raise ArmazenamentoError("S3_BUCKET não configurado.")

    chave = montar_chave(entidade, config)
    try:
        cliente = cliente or _criar_cliente(config)
        cliente.put_object(
            Bucket=config["S3_BUCKET"],
            Key=chave,
            Body=conteudo,
            ContentType="text/csv; charset=utf-8",
            ServerSideEncryption="AES256",
        )
    except Exception as erro:
        current_app.logger.exception("Falha ao enviar relatório ao S3")
        raise ArmazenamentoError("Não foi possível enviar o relatório ao armazenamento.") from erro
    return chave


def gerar_url_download(chave, cliente=None, config=None):
    """URL pré-assinada (GET) de curta duração para o objeto."""
    config = config if config is not None else current_app.config
    try:
        cliente = cliente or _criar_cliente(config)
        return cliente.generate_presigned_url(
            "get_object",
            Params={"Bucket": config["S3_BUCKET"], "Key": chave},
            ExpiresIn=int(config.get("S3_URL_EXPIRA_SEGUNDOS", 900)),
        )
    except Exception as erro:
        current_app.logger.exception("Falha ao gerar URL pré-assinada")
        raise ArmazenamentoError("Não foi possível gerar o link de download.") from erro
