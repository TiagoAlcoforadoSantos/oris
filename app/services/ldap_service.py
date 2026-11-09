"""
Leitura de usuários e grupos de um diretório LDAP (Requisito 3).

Só LÊ o diretório e devolve `UsuarioExterno`; quem grava nas tabelas
locais é app/services/diretorio_service.py.

Segurança: a conexão exige TLS (`ldaps://` ou STARTTLS); um `ldap://`
sem STARTTLS só é aceito com LDAP_ALLOW_INSECURE=true (uso de
laboratório), porque a senha da conta de serviço trafegaria em texto
puro. Essa senha vem do .env, nunca do código.

A associação usuário -> grupo é obtida pelos grupos (atributo de
membros, ex.: `member` = DN do usuário) e, se existir, também pelo
atributo `memberOf` do próprio usuário.
"""

from flask import current_app

from app.services.diretorio_service import DiretorioConfigError, UsuarioExterno


def _abrir_conexao(config):
    """Abre a conexão autenticada com a conta de serviço."""
    from ldap3 import ALL, Connection, Server

    uri = config.get("LDAP_URI") or ""
    if not uri:
        raise DiretorioConfigError("LDAP_URI não configurado.")

    usa_tls = uri.lower().startswith("ldaps://") or config.get("LDAP_USE_STARTTLS")
    if not usa_tls and not config.get("LDAP_ALLOW_INSECURE"):
        raise DiretorioConfigError(
            "Conexão LDAP sem TLS recusada: use ldaps:// ou LDAP_USE_STARTTLS=true "
            "(ou LDAP_ALLOW_INSECURE=true apenas em laboratório)."
        )

    servidor = Server(uri, get_info=ALL, connect_timeout=10)
    conexao = Connection(
        servidor,
        user=config.get("LDAP_BIND_DN") or None,
        password=config.get("LDAP_BIND_PASSWORD") or None,
        receive_timeout=20,
    )
    if config.get("LDAP_USE_STARTTLS") and not uri.lower().startswith("ldaps://"):
        conexao.open()
        conexao.start_tls()
    if not conexao.bind():
        raise DiretorioConfigError("Falha ao autenticar a conta de serviço no LDAP.")
    return conexao


def _valores(entrada, atributo):
    if atributo not in entrada.entry_attributes:
        return []
    valor = entrada[atributo].values
    return [str(v) for v in valor]


def buscar_usuarios_ldap(config=None, conexao=None):
    """Devolve a lista de `UsuarioExterno` do diretório. `conexao`
    permite injetar uma conexão já aberta (testes usam o modo MOCK do
    próprio ldap3)."""
    config = config if config is not None else current_app.config
    propria = conexao is None
    if propria:
        conexao = _abrir_conexao(config)

    try:
        attr_id = config.get("LDAP_ATTR_ID", "uid")
        attr_nome = config.get("LDAP_ATTR_NOME", "cn")
        attr_email = config.get("LDAP_ATTR_EMAIL", "mail")
        attr_grupo_nome = config.get("LDAP_ATTR_GROUP_NAME", "cn")
        attr_membros = config.get("LDAP_ATTR_GROUP_MEMBER", "member")

        # 1) Grupos: DN do usuário -> nomes dos grupos.
        grupos_por_dn = {}
        base_grupos = config.get("LDAP_GROUP_BASE")
        if base_grupos:
            conexao.search(
                base_grupos,
                config.get("LDAP_GROUP_FILTER", "(objectClass=groupOfNames)"),
                attributes=[attr_grupo_nome, attr_membros],
            )
            for grupo in conexao.entries:
                nomes = _valores(grupo, attr_grupo_nome)
                if not nomes:
                    continue
                for dn_membro in _valores(grupo, attr_membros):
                    grupos_por_dn.setdefault(dn_membro.strip().lower(), set()).add(nomes[0])

        # 2) Usuários.
        conexao.search(
            config.get("LDAP_USER_BASE", ""),
            config.get("LDAP_USER_FILTER", "(objectClass=person)"),
            attributes=[attr_id, attr_nome, attr_email, "memberOf"],
        )
        externos = []
        for entrada in conexao.entries:
            ids = _valores(entrada, attr_id)
            if not ids:
                continue
            grupos = set(grupos_por_dn.get(str(entrada.entry_dn).strip().lower(), set()))
            for dn_grupo in _valores(entrada, "memberOf"):
                # "CN=oris-admin,OU=Grupos,..." -> "oris-admin"
                primeiro = dn_grupo.split(",")[0]
                if "=" in primeiro:
                    grupos.add(primeiro.split("=", 1)[1])
            nomes = _valores(entrada, attr_nome)
            emails = _valores(entrada, attr_email)
            externos.append(
                UsuarioExterno(
                    identificador=ids[0],
                    nome=nomes[0] if nomes else ids[0],
                    email=emails[0] if emails else "",
                    grupos=sorted(grupos),
                )
            )
        return externos
    finally:
        if propria:
            conexao.unbind()
