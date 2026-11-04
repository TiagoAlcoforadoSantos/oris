"""API REST do ORIS - v1 (somente leitura)."""

from functools import wraps

from flask import Blueprint, abort, jsonify, render_template, request

from app.extensions import db
from app.models import (Alteracao, Equipamento, Servico, SituacaoAtivoInativo,
                        SituacaoUnidade, StatusAlteracao, Unidade)
from app.utils.decorators import usuario_atual

api_bp = Blueprint("api", __name__, url_prefix="/api")

LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200


@api_bp.after_request
def _nao_cachear(resposta):
    """Respostas da API dependem da sessão: proxies e navegadores não devem guardá-las."""
    resposta.headers.setdefault("Cache-Control", "no-store")
    return resposta


def api_login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        usuario = usuario_atual()
        if usuario is None or not usuario.ativo:
            return _erro(401, "Não autenticado. Faça login em /login e envie o cookie de sessão.")
        return view(*args, **kwargs)
    return wrapper


def _erro(status, mensagem):
    resposta = jsonify({"erro": {"status": status, "mensagem": mensagem}})
    resposta.status_code = status
    return resposta


@api_bp.errorhandler(404)
def _nao_encontrado(_):
    return _erro(404, "Recurso não encontrado.")


def _paginar(query):
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
        limite = min(LIMITE_MAXIMO, max(1, int(request.args.get("limite", LIMITE_PADRAO))))
    except ValueError:
        abort(400)
    total = query.order_by(None).count()
    itens = query.offset((pagina - 1) * limite).limit(limite).all()
    return itens, {"pagina": pagina, "limite": limite, "total": total,
                   "paginas": (total + limite - 1) // limite}


def _situacao(enum_cls):
    valor = request.args.get("situacao")
    if not valor:
        return None
    if valor not in {s.value for s in enum_cls}:
        abort(400)
    return enum_cls(valor)


@api_bp.errorhandler(400)
def _requisicao_invalida(_):
    return _erro(400, "Parâmetro inválido. Confira os valores aceitos em /api/docs.")


def _iso(data):
    return data.isoformat() + "Z" if data else None


def _unidade_json(u, detalhe=False):
    dados = {
        "id": u.id, "nome": u.nome, "cnes": u.cnes, "unidade_e_mista": bool(u.unidade_e_mista),
        "tipo": u.tipo, "bairro": u.bairro, "cidade": u.cidade, "uf": u.uf,
        "situacao": u.situacao.value, "atualizado_em": _iso(u.updated_at),
    }
    if detalhe:
        dados["endereco"] = u.endereco
        dados["criado_em"] = _iso(u.created_at)
        dados["servicos"] = [_servico_json(s) for s in u.servicos]
        dados["equipamentos"] = [_equipamento_json(e) for e in u.equipamentos]
    return dados


def _servico_json(s):
    return {"id": s.id, "nome": s.nome, "unidade_id": s.unidade_id,
            "situacao": s.situacao.value, "atualizado_em": _iso(s.updated_at)}


def _equipamento_json(e):
    return {"id": e.id, "nome": e.nome, "tipo": e.tipo, "unidade_id": e.unidade_id,
            "servico_id": e.servico_id, "situacao": e.situacao.value,
            "atualizado_em": _iso(e.updated_at)}


@api_bp.get("/v1/unidades")
@api_login_required
def listar_unidades():
    query = Unidade.query
    situacao = _situacao(SituacaoUnidade)
    if situacao:
        query = query.filter(Unidade.situacao == situacao)
    if request.args.get("bairro"):
        query = query.filter(Unidade.bairro == request.args["bairro"])
    if request.args.get("cnes"):
        query = query.filter(Unidade.cnes == request.args["cnes"])
    itens, meta = _paginar(query.order_by(Unidade.nome))
    return jsonify({"dados": [_unidade_json(u) for u in itens], "meta": meta})


@api_bp.get("/v1/unidades/<int:unidade_id>")
@api_login_required
def obter_unidade(unidade_id):
    unidade = db.session.get(Unidade, unidade_id)
    if unidade is None:
        return _erro(404, f"Unidade {unidade_id} não encontrada.")
    return jsonify({"dados": _unidade_json(unidade, detalhe=True)})


@api_bp.get("/v1/servicos")
@api_login_required
def listar_servicos():
    query = Servico.query
    situacao = _situacao(SituacaoAtivoInativo)
    if situacao:
        query = query.filter(Servico.situacao == situacao)
    if request.args.get("unidade_id"):
        query = query.filter(Servico.unidade_id == request.args.get("unidade_id", type=int))
    itens, meta = _paginar(query.order_by(Servico.nome))
    return jsonify({"dados": [_servico_json(s) for s in itens], "meta": meta})


@api_bp.get("/v1/equipamentos")
@api_login_required
def listar_equipamentos():
    query = Equipamento.query
    situacao = _situacao(SituacaoAtivoInativo)
    if situacao:
        query = query.filter(Equipamento.situacao == situacao)
    if request.args.get("unidade_id"):
        query = query.filter(Equipamento.unidade_id == request.args.get("unidade_id", type=int))
    if request.args.get("tipo"):
        query = query.filter(Equipamento.tipo == request.args["tipo"])
    itens, meta = _paginar(query.order_by(Equipamento.nome))
    return jsonify({"dados": [_equipamento_json(e) for e in itens], "meta": meta})


@api_bp.get("/v1/indicadores")
@api_login_required
def indicadores():
    def contar(model, **filtro):
        return model.query.filter_by(**filtro).count()
    return jsonify({"dados": {
        "unidades": {"total": Unidade.query.count(),
                     "ativas": contar(Unidade, situacao=SituacaoUnidade.ATIVA),
                     "inativas": contar(Unidade, situacao=SituacaoUnidade.INATIVA),
                     "manutencao": contar(Unidade, situacao=SituacaoUnidade.MANUTENCAO)},
        "servicos": {"total": Servico.query.count(),
                     "ativos": contar(Servico, situacao=SituacaoAtivoInativo.ATIVO)},
        "equipamentos": {"total": Equipamento.query.count(),
                         "ativos": contar(Equipamento, situacao=SituacaoAtivoInativo.ATIVO)},
        "alteracoes": {"pendentes": contar(Alteracao, status=StatusAlteracao.PENDENTE),
                       "aprovadas": contar(Alteracao, status=StatusAlteracao.APROVADO),
                       "rejeitadas": contar(Alteracao, status=StatusAlteracao.REJEITADO)},
    }})


def _parametro(nome, descricao, tipo="string", enum=None, local="query", obrigatorio=False):
    schema = {"type": tipo}
    if enum:
        schema["enum"] = enum
    return {"name": nome, "in": local, "required": obrigatorio,
            "description": descricao, "schema": schema}


PAGINACAO = [
    _parametro("pagina", "Número da página (a partir de 1).", "integer"),
    _parametro("limite", f"Itens por página (1–{LIMITE_MAXIMO}, padrão {LIMITE_PADRAO}).", "integer"),
]

RESPOSTAS_ERRO = {
    "400": {"description": "Parâmetro inválido", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Erro"}}}},
    "401": {"description": "Não autenticado", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Erro"}}}},
}


def _lista(ref):
    return {"type": "object", "properties": {
        "dados": {"type": "array", "items": {"$ref": f"#/components/schemas/{ref}"}},
        "meta": {"$ref": "#/components/schemas/Paginacao"}}}


def especificacao_openapi():
    sit_u = [s.value for s in SituacaoUnidade]
    sit_a = [s.value for s in SituacaoAtivoInativo]
    data = {"type": "string", "format": "date-time", "example": "2026-10-31T12:00:00Z"}
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "ORIS — API da Rede de Saúde Bucal",
            "version": "1.0.0",
            "description": (
                "API REST somente leitura do ORIS (CESAR School × Secretaria de Saúde do Recife). "
                "Autenticação pela sessão web: faça login em /login no mesmo navegador e use "
                "o botão 'Try it out'. Nenhum dado pessoal ou clínico é exposto."
            ),
        },
        "servers": [{"url": "/api/v1"}],
        "components": {
            "securitySchemes": {"sessao": {"type": "apiKey", "in": "cookie", "name": "session"}},
            "schemas": {
                "Erro": {"type": "object", "properties": {"erro": {"type": "object", "properties": {
                    "status": {"type": "integer", "example": 401},
                    "mensagem": {"type": "string"}}}}},
                "Paginacao": {"type": "object", "properties": {
                    "pagina": {"type": "integer", "example": 1}, "limite": {"type": "integer", "example": 50},
                    "total": {"type": "integer", "example": 32}, "paginas": {"type": "integer", "example": 1}}},
                "Unidade": {"type": "object", "properties": {
                    "id": {"type": "integer", "example": 21}, "nome": {"type": "string", "example": "CEO Centro"},
                    "cnes": {"type": "string", "example": "9100021"},
                    "unidade_e_mista": {"type": "boolean"}, "tipo": {"type": "string"},
                    "bairro": {"type": "string", "nullable": True}, "cidade": {"type": "string"},
                    "uf": {"type": "string", "example": "PE"},
                    "situacao": {"type": "string", "enum": sit_u}, "atualizado_em": data}},
                "UnidadeDetalhe": {"allOf": [{"$ref": "#/components/schemas/Unidade"}, {
                    "type": "object", "properties": {
                        "endereco": {"type": "string", "nullable": True}, "criado_em": data,
                        "servicos": {"type": "array", "items": {"$ref": "#/components/schemas/Servico"}},
                        "equipamentos": {"type": "array", "items": {"$ref": "#/components/schemas/Equipamento"}}}}]},
                "Servico": {"type": "object", "properties": {
                    "id": {"type": "integer"}, "nome": {"type": "string", "example": "Endodontia"},
                    "unidade_id": {"type": "integer", "nullable": True},
                    "situacao": {"type": "string", "enum": sit_a}, "atualizado_em": data}},
                "Equipamento": {"type": "object", "properties": {
                    "id": {"type": "integer"}, "nome": {"type": "string"},
                    "tipo": {"type": "string", "example": "Autoclave"},
                    "unidade_id": {"type": "integer", "nullable": True},
                    "servico_id": {"type": "integer", "nullable": True},
                    "situacao": {"type": "string", "enum": sit_a}, "atualizado_em": data}},
                "Indicadores": {"type": "object", "properties": {"dados": {"type": "object"}}},
            },
        },
        "security": [{"sessao": []}],
        "paths": {
            "/unidades": {"get": {
                "tags": ["Unidades"], "summary": "Lista unidades de saúde bucal",
                "parameters": [_parametro("situacao", "Filtra pela situação.", enum=sit_u),
                               _parametro("bairro", "Filtra pelo bairro (igualdade)."),
                               _parametro("cnes", "Filtra pelo CNES (pode retornar mais de um registro).")]
                + PAGINACAO,
                "responses": {"200": {"description": "Lista paginada",
                                      "content": {"application/json": {"schema": _lista("Unidade")}}},
                              **RESPOSTAS_ERRO}}},
            "/unidades/{unidade_id}": {"get": {
                "tags": ["Unidades"], "summary": "Detalhe de uma unidade, com serviços e equipamentos",
                "parameters": [_parametro("unidade_id", "ID interno da unidade.", "integer", local="path",
                                          obrigatorio=True)],
                "responses": {"200": {"description": "Unidade", "content": {"application/json": {"schema": {
                    "type": "object", "properties": {"dados": {"$ref": "#/components/schemas/UnidadeDetalhe"}}}}}},
                    "404": {"description": "Não encontrada", "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/Erro"}}}},
                    "401": RESPOSTAS_ERRO["401"]}}},
            "/servicos": {"get": {
                "tags": ["Serviços"], "summary": "Lista serviços",
                "parameters": [_parametro("situacao", "Filtra pela situação.", enum=sit_a),
                               _parametro("unidade_id", "Filtra pela unidade.", "integer")] + PAGINACAO,
                "responses": {"200": {"description": "Lista paginada",
                                      "content": {"application/json": {"schema": _lista("Servico")}}},
                              **RESPOSTAS_ERRO}}},
            "/equipamentos": {"get": {
                "tags": ["Equipamentos"], "summary": "Lista equipamentos",
                "parameters": [_parametro("situacao", "Filtra pela situação.", enum=sit_a),
                               _parametro("unidade_id", "Filtra pela unidade.", "integer"),
                               _parametro("tipo", "Filtra pelo tipo de equipamento.")] + PAGINACAO,
                "responses": {"200": {"description": "Lista paginada",
                                      "content": {"application/json": {"schema": _lista("Equipamento")}}},
                              **RESPOSTAS_ERRO}}},
            "/indicadores": {"get": {
                "tags": ["Indicadores"], "summary": "Totais da rede e do fluxo de aprovação",
                "responses": {"200": {"description": "Indicadores", "content": {"application/json": {
                    "schema": {"$ref": "#/components/schemas/Indicadores"}}}},
                    "401": RESPOSTAS_ERRO["401"]}}},
        },
    }


@api_bp.get("/v1/openapi.json")
def openapi_json():
    return jsonify(especificacao_openapi())


@api_bp.get("/docs")
def swagger_ui():
    return render_template("api/swagger.html")
