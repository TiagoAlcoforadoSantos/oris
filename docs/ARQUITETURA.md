# ORIS — Arquitetura conceitual, papéis e recursos

Documento do **Requisito 1** (análise do contexto: papéis, recursos e arquitetura conceitual).

## 1. Contexto

O ORIS é a plataforma de governança da Rede de Saúde Bucal: cadastra
**unidades de saúde**, seus **serviços** e **equipamentos**, controla quem pode
alterar esses dados (com fluxo de aprovação) e registra tudo em trilha de auditoria.

## 2. Papéis (perfis RBAC)

| Papel | Descrição | Origem do papel |
|---|---|---|
| ADMINISTRADOR | Acesso total, gerencia usuários | Local ou grupo LDAP/OIDC |
| GESTAO_INFORMACAO | Edita, valida/aprova alterações, consulta auditoria | idem |
| RESPONSAVEL_SAUDE_BUCAL | Cadastra/edita unidades, serviços e equipamentos (sujeito a aprovação) | idem |
| GESTOR | Somente leitura | idem |

Definidos em `app/models/enums.py::PerfilUsuario`.

## 3. Recursos

| Recurso | Operações | Código |
|---|---|---|
| Unidades | listar, ver, criar, editar, alterar situação | `app/routes/unidades.py` |
| Serviços | idem | `app/routes/servicos.py` |
| Equipamentos | idem | `app/routes/equipamentos.py` |
| Alterações (aprovação) | listar, ver, aprovar, rejeitar | `app/routes/alteracoes.py` |
| Auditoria | listar, ver | `app/routes/auditoria.py` |
| Usuários | CRUD, situação, senha | `app/routes/usuarios.py` |
| Importação de planilhas | prévia e confirmação | `app/routes/importacao.py` |
| Dashboard | consulta | `app/routes/dashboard.py` |
| **Relatórios (novo)** | baixar CSV; exportar ao S3 | `app/routes/relatorios.py` |
| **Diretório (novo)** | sincronizar usuários/grupos (CLI), login SSO | `app/services/diretorio_service.py`, `app/routes/auth.py` |

## 4. Matriz de permissões (Requisito 2 — RBAC)

Legenda: ✔ permitido · — negado (HTTP 403, sempre validado no backend por `roles_required`).

| Recurso / ação | ADMIN | GESTAO_INFO | RESP_SAUDE_BUCAL | GESTOR |
|---|:-:|:-:|:-:|:-:|
| Consultar unidades/serviços/equipamentos | ✔ | ✔ | ✔ | ✔ |
| Criar/editar/alterar situação | ✔ | ✔ | ✔ | — |
| Aprovar/rejeitar alterações | ✔ | ✔ | — | — |
| Consultar auditoria | ✔ | ✔ | — | — |
| Gerenciar usuários | ✔ | — | — | — |
| Importar planilhas | ✔ | ✔ | ✔ | — |
| Baixar relatório CSV | ✔ | ✔ | ✔ | ✔ |
| Exportar relatório para S3 | ✔ | ✔ | — | — |

Implementação: `app/utils/decorators.py` (`login_required`, `roles_required`).
Testes: `tests/test_fase4_rbac.py`, `tests/test_fase14_diretorio_relatorios.py`.

## 5. Arquitetura conceitual

```
                    ┌────────────────────────┐
   Usuário ───────► │  Flask (blueprints)    │
 (navegador)        │  auth / recursos /     │
                    │  relatorios            │
                    └───────┬────────────────┘
                            │ roles_required (RBAC) + auditoria
        ┌───────────────────┼──────────────────────────┐
        ▼                   ▼                          ▼
 ┌─────────────┐   ┌────────────────────┐    ┌───────────────────┐
 │ Serviços    │   │ Modelos SQLAlchemy │    │ Serviços externos │
 │ (regras)    │──►│ usuarios, grupos,  │    │ ldap_service      │──► LDAP/AD
 │ diretorio / │   │ unidades, ...      │    │ oidc_service      │──► IdP OIDC
 │ relatorio / │   └─────────┬──────────┘    │ armazenamento_svc │──► Amazon S3
 │ armazenamento│            ▼               └───────────────────┘
 └─────────────┘        MySQL
```

Camadas: **rotas** (HTTP + RBAC) → **serviços** (regras de negócio e integrações) →
**modelos** (persistência). Integrações externas ficam isoladas em serviços próprios,
substituíveis em testes.

## 6. Fluxos

**6.1 Login local** — `/login` valida e-mail/senha (bcrypt); só contas `origem = LOCAL`.

**6.2 Sincronização LDAP (Requisito 3)** — `flask sincronizar-ldap`:
`ldap_service.buscar_usuarios_ldap` lê usuários e grupos → `diretorio_service.sincronizar_usuarios`
mapeia grupo→perfil (`DIRETORIO_MAPA_GRUPO_PERFIL`, maior privilégio vence), cria/atualiza em
`usuarios`/`grupos`/`usuario_grupos`, desativa quem saiu do diretório e audita.

**6.3 Login OIDC (Requisito 3)** — `/login/oidc` (Authorization Code + PKCE S256 + state + nonce)
→ IdP → `/login/oidc/callback` valida tudo, provisiona o usuário via o mesmo serviço e abre a sessão.

**6.4 Exportação ao S3 (Requisito 4)** — `/relatorios` → `relatorio_service.gerar_csv` (sanitiza
fórmulas) → `armazenamento_service.enviar_relatorio` (SSE AES256) → URL pré-assinada → auditoria.

## 7. Regras de segurança do diretório

- Contas externas nunca autenticam com senha local; contas LOCAL nunca são alteradas pela sincronização.
- Sem grupo mapeado → usuário não é provisionado (negado por padrão).
- O último administrador ativo é protegido contra desativação/rebaixamento.
- LDAP exige TLS (ldaps:// ou STARTTLS); OIDC exige HTTPS.
- Credenciais (bind LDAP, client secret, AWS) vêm do ambiente, nunca do código.

## 8. Configuração

Ver `.env.example` (variáveis `DIRETORIO_*`, `LDAP_*`, `OIDC_*`, `S3_*`) e `config.py`.
