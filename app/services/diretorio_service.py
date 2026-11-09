"""
Provisionamento de usuários e grupos a partir de diretórios externos
(Requisito 3 — LDAP e OIDC populando as tabelas locais).

Este módulo é independente do protocolo: `ldap_service` e
`oidc_service` só LEEM o diretório e devolvem objetos `UsuarioExterno`;
aqui é aplicada a regra única de negócio que os transforma em linhas de
`usuarios`, `grupos` e `usuario_grupos`.

REGRAS DE SEGURANÇA (todas cobertas por testes em
tests/test_fase14_diretorio_relatorios.py):

- A permissão do usuário continua sendo o `perfil` (RBAC). O perfil é
  calculado a partir dos grupos do diretório pelo mapa
  `DIRETORIO_MAPA_GRUPO_PERFIL`; havendo mais de um grupo mapeado,
  vale o perfil de MAIOR privilégio.
- Usuário sem nenhum grupo mapeado NUNCA é criado (e, se já existia
  como conta externa, é desativado): estar no diretório não basta para
  acessar o ORIS.
- Contas LOCAL nunca são alteradas por uma sincronização (um e-mail
  igual ao de uma conta local é ignorado, e relatado), evitando que um
  diretório "assuma" uma conta local existente.
- O sistema nunca fica sem ADMINISTRADOR ativo: desativar ou rebaixar
  o último administrador é bloqueado, como na administração manual
  (app/routes/usuarios.py).
- Contas externas recebem uma senha aleatória descartável (hash
  bcrypt); a senha local nunca é usada para elas (ver app/routes/
  auth.py), a autenticação é sempre no diretório.
- Toda mudança é auditada (atribuída ao próprio usuário afetado, pois
  uma sincronização não tem um usuário "logado") e a operação inteira
  roda em UMA transação: se algo falhar, nada é gravado.
"""

import json
import secrets
from dataclasses import dataclass, field

from flask import current_app

from app.extensions import db
from app.models import Grupo, OrigemDiretorio, PerfilUsuario, Usuario
from app.services.auditoria_service import registrar_auditoria
from app.utils.security import gerar_hash_senha

# Do maior para o menor privilégio.
PRIORIDADE_PERFIS = [
    PerfilUsuario.ADMINISTRADOR,
    PerfilUsuario.GESTAO_INFORMACAO,
    PerfilUsuario.RESPONSAVEL_SAUDE_BUCAL,
    PerfilUsuario.GESTOR,
]


class DiretorioConfigError(Exception):
    """Configuração do diretório ausente ou insegura (mensagem segura
    para exibir a quem administra o sistema)."""


@dataclass
class UsuarioExterno:
    identificador: str
    nome: str
    email: str
    grupos: list = field(default_factory=list)


def carregar_mapa_grupo_perfil(config=None):
    """Lê e valida `DIRETORIO_MAPA_GRUPO_PERFIL` (JSON grupo -> perfil)."""
    config = config if config is not None else current_app.config
    bruto = config.get("DIRETORIO_MAPA_GRUPO_PERFIL") or "{}"
    try:
        mapa = json.loads(bruto) if isinstance(bruto, str) else dict(bruto)
    except ValueError as erro:
        raise DiretorioConfigError("DIRETORIO_MAPA_GRUPO_PERFIL não é um JSON válido.") from erro

    validos = {perfil.value for perfil in PerfilUsuario}
    resultado = {}
    for grupo, perfil in mapa.items():
        if perfil not in validos:
            raise DiretorioConfigError(f"Perfil '{perfil}' do grupo '{grupo}' não existe no ORIS.")
        resultado[str(grupo).strip().lower()] = PerfilUsuario(perfil)
    return resultado


def resolver_perfil(grupos, mapa):
    """Perfil de maior privilégio entre os grupos mapeados, ou None."""
    encontrados = {mapa[g.strip().lower()] for g in grupos if g.strip().lower() in mapa}
    for perfil in PRIORIDADE_PERFIS:
        if perfil in encontrados:
            return perfil
    return None


def _e_ultimo_admin_ativo(usuario):
    if usuario.perfil != PerfilUsuario.ADMINISTRADOR or not usuario.ativo:
        return False
    outros = Usuario.query.filter(
        Usuario.perfil == PerfilUsuario.ADMINISTRADOR,
        Usuario.ativo.is_(True),
        Usuario.id != usuario.id,
    ).count()
    return outros == 0


def _sincronizar_grupos(usuario, nomes_grupos, origem):
    """Substitui a participação do usuário nos grupos DESTA origem
    (grupos de outras origens ficam intactos)."""
    manter = [g for g in usuario.grupos if g.origem != origem]
    for nome in sorted({n.strip() for n in nomes_grupos if n.strip()}):
        grupo = Grupo.query.filter_by(nome=nome, origem=origem).first()
        if grupo is None:
            grupo = Grupo(nome=nome, origem=origem)
            db.session.add(grupo)
        manter.append(grupo)
    usuario.grupos = manter


def _aplicar_usuario(externo, origem, mapa, resumo):
    email = externo.email.strip().lower()
    if not externo.identificador or not email:
        resumo["ignorados"].append(f"{externo.identificador or '(sem id)'}: sem identificador ou e-mail")
        return None

    perfil = resolver_perfil(externo.grupos, mapa)

    usuario = Usuario.query.filter_by(origem=origem, identificador_externo=externo.identificador).first()
    if usuario is None:
        por_email = Usuario.query.filter_by(email=email).first()
        if por_email is not None:
            if por_email.origem != origem:
                resumo["ignorados"].append(f"{email}: já existe uma conta {por_email.origem.value} com este e-mail")
                return None
            if por_email.identificador_externo and por_email.identificador_externo != externo.identificador:
                # Conta já vinculada a outra identidade: nunca re-vincular por e-mail.
                resumo["ignorados"].append(f"{email}: e-mail já vinculado a outro identificador externo")
                return None
            usuario = por_email
            usuario.identificador_externo = externo.identificador

    if usuario is None:
        if perfil is None:
            resumo["ignorados"].append(f"{email}: nenhum grupo mapeado para um perfil")
            return None
        usuario = Usuario(
            nome=externo.nome.strip() or email,
            email=email,
            senha_hash=gerar_hash_senha(secrets.token_urlsafe(32)),
            perfil=perfil,
            ativo=True,
            origem=origem,
            identificador_externo=externo.identificador,
        )
        db.session.add(usuario)
        db.session.flush()
        _sincronizar_grupos(usuario, externo.grupos, origem)
        registrar_auditoria(
            usuario=usuario,
            acao="CRIAR_USUARIO",
            tabela="usuarios",
            registro_id=usuario.id,
            descricao=f"Usuário '{email}' provisionado via {origem.value}, perfil {perfil.value}.",
        )
        resumo["criados"] += 1
        return usuario

    alterou = False
    nome_novo = externo.nome.strip() or usuario.nome
    if usuario.nome != nome_novo:
        usuario.nome = nome_novo
        alterou = True
    if usuario.email != email:
        usuario.email = email
        alterou = True

    if perfil is None:
        if usuario.ativo:
            if _e_ultimo_admin_ativo(usuario):
                resumo["protegidos"].append(f"{usuario.email}: único ADMINISTRADOR ativo, não desativado")
            else:
                usuario.ativo = False
                registrar_auditoria(
                    usuario=usuario, acao="DESATIVAR_USUARIO", tabela="usuarios", registro_id=usuario.id,
                    descricao=f"Desativação de '{usuario.email}' via {origem.value}: sem grupo mapeado.",
                )
                resumo["desativados"] += 1
    else:
        if perfil != usuario.perfil:
            if _e_ultimo_admin_ativo(usuario):
                resumo["protegidos"].append(f"{usuario.email}: único ADMINISTRADOR ativo, perfil mantido")
            else:
                anterior = usuario.perfil
                usuario.perfil = perfil
                registrar_auditoria(
                    usuario=usuario, acao="ALTERAR_PERFIL", tabela="usuarios", registro_id=usuario.id,
                    descricao=f"Perfil de '{usuario.email}' alterado via {origem.value}.",
                    valor_anterior={"perfil": anterior.value}, valor_novo={"perfil": perfil.value},
                )
                alterou = True
        if not usuario.ativo:
            usuario.ativo = True
            registrar_auditoria(
                usuario=usuario, acao="ATIVAR_USUARIO", tabela="usuarios", registro_id=usuario.id,
                descricao=f"Reativação de '{usuario.email}' via {origem.value}.",
            )
            alterou = True

    _sincronizar_grupos(usuario, externo.grupos, origem)
    if alterou:
        resumo["atualizados"] += 1
    return usuario


def sincronizar_usuarios(externos, origem, desativar_ausentes=True, mapa=None, config=None, simular=False):
    """Aplica a lista de `UsuarioExterno` às tabelas locais, numa única
    transação. Retorna um resumo (criados/atualizados/desativados e
    listas de ignorados/protegidos). Faz commit; em erro, rollback.
    Com `simular=True` calcula o resumo e desfaz tudo (rollback)."""
    if mapa is None:
        mapa = carregar_mapa_grupo_perfil(config)
    if not mapa:
        raise DiretorioConfigError("DIRETORIO_MAPA_GRUPO_PERFIL está vazio: nenhum usuário poderia receber um perfil.")

    resumo = {"criados": 0, "atualizados": 0, "desativados": 0, "ignorados": [], "protegidos": []}
    try:
        vistos = set()
        for externo in externos:
            usuario = _aplicar_usuario(externo, origem, mapa, resumo)
            if usuario is not None:
                vistos.add(usuario.id)
            vistos.add(("ext", externo.identificador))

        if desativar_ausentes:
            ativos = Usuario.query.filter_by(origem=origem, ativo=True).all()
            for usuario in ativos:
                if ("ext", usuario.identificador_externo) in vistos:
                    continue
                if _e_ultimo_admin_ativo(usuario):
                    resumo["protegidos"].append(f"{usuario.email}: único ADMINISTRADOR ativo, não desativado")
                    continue
                usuario.ativo = False
                registrar_auditoria(
                    usuario=usuario, acao="DESATIVAR_USUARIO", tabela="usuarios", registro_id=usuario.id,
                    descricao=f"Desativação de '{usuario.email}' via {origem.value}: ausente no diretório.",
                )
                resumo["desativados"] += 1

        if simular:
            db.session.rollback()
        else:
            db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return resumo


def provisionar_usuario_externo(externo, origem, config=None):
    """Provisiona UM usuário (login OIDC). Devolve o Usuario ativo, ou
    None se ele não tem grupo mapeado / está bloqueado."""
    mapa = carregar_mapa_grupo_perfil(config)
    resumo = sincronizar_usuarios([externo], origem, desativar_ausentes=False, mapa=mapa or None, config=config)
    usuario = Usuario.query.filter_by(origem=origem, identificador_externo=externo.identificador).first()
    if usuario is None or not usuario.ativo:
        return None
    return usuario
