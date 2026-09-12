# ORIS — Plataforma de Governança da Rede de Saúde Bucal

> ⚠️ **Status do projeto:** em desenvolvimento — FASE 5 concluída (CRUD de Unidades).
> Este README será expandido a cada fase concluída.

## O que é o ORIS

O ORIS é um sistema web acadêmico que centraliza o cadastro e a governança das
informações de **Unidades de Saúde Bucal**, seus **Serviços** e **Equipamentos**,
resolvendo o problema da fragmentação dessas informações entre o CNES e
planilhas paralelas.

## Problema

As informações da rede de Saúde Bucal hoje estão espalhadas entre o CNES e
planilhas paralelas mantidas manualmente, dificultando a governança, a
auditoria e a tomada de decisão.

## Objetivo

Oferecer uma plataforma web centralizada, segura e auditável para cadastro,
validação e aprovação de alterações relacionadas a unidades, serviços e
equipamentos de Saúde Bucal, preparada para uma futura integração com o CNES.

## Escopo do MVP

- Unidades de Saúde Bucal
- Serviços de Saúde Bucal
- Equipamentos
- Login e gestão de acesso (RBAC simples por perfil)
- Fluxo de aprovação de alterações
- Auditoria (audit log)
- Dashboard simples

Fora de escopo (não faz parte deste projeto): prontuário de pacientes, sistema
hospitalar, laudos ou qualquer módulo assistencial ao paciente.

## Tecnologias

- **Backend:** Python 3 + Flask
- **Banco de dados:** MySQL
- **Frontend:** HTML, CSS, Bootstrap, JavaScript
- **Segurança:** bcrypt (hash de senha), sessões do Flask, controle de acesso
  baseado em perfil, `.env` para configurações sensíveis

## Estrutura do projeto

```
ORIS/
│
├── app/
│   ├── __init__.py        # application factory
│   ├── extensions.py      # instância do SQLAlchemy
│   ├── forms.py            # formulários (Flask-WTF) — LoginForm
│   ├── cli.py               # comando `flask criar-usuario`
│   ├── routes/
│   │   ├── auth.py               # /login, /logout
│   │   ├── main.py               # "/" (rota protegida)
│   │   ├── areas.py              # /admin, /gestao, /responsavel, /gestor (RBAC)
│   │   └── unidades.py           # CRUD de Unidades de Saúde Bucal
│   ├── models/
│   │   ├── enums.py             # PerfilUsuario, situações, status
│   │   ├── mixins.py            # TimestampMixin (created_at/updated_at)
│   │   ├── usuario.py
│   │   ├── unidade.py
│   │   ├── servico.py
│   │   ├── equipamento.py
│   │   ├── alteracao.py
│   │   └── auditoria.py
│   ├── templates/
│   │   ├── base.html            # layout com Bootstrap
│   │   ├── login.html
│   │   ├── index.html           # página protegida provisória
│   │   ├── area_perfil.html     # áreas de teste do RBAC
│   │   ├── acesso_negado.html   # página de erro 403
│   │   ├── nao_encontrado.html  # página de erro 404
│   │   └── unidades/
│   │       ├── lista.html
│   │       ├── form.html         # cadastro e edição
│   │       └── detalhe.html
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   ├── services/           # regras de negócio — próximas fases
│   └── utils/
│       ├── datetime_utils.py    # helper de data/hora (UTC)
│       ├── security.py          # hash/verificação de senha (bcrypt)
│       ├── decorators.py        # login_required, roles_required
│       └── rbac.py               # matriz de acesso das áreas de teste
│
├── database/
│   └── schema.sql           # DDL completo das tabelas (MySQL)
│
├── tests/
│   ├── test_fase1_estrutura.py
│   ├── test_fase2_models.py
│   ├── test_fase3_autenticacao.py
│   ├── test_fase4_rbac.py
│   └── test_fase5_unidades.py
│
├── .env                     # configuração local (NÃO versionar)
├── .env.example             # modelo de configuração
├── .gitignore
├── requirements.txt
├── config.py
├── run.py
└── README.md
```

## Como instalar

### 1. Pré-requisitos

- Python 3.10+
- MySQL Server 8.x
- pip

### 2. Clonar o projeto e criar o ambiente virtual

```bash
cd ORIS
python3 -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Instalar as dependências

```bash
pip install -r requirements.txt
```

## Como configurar o MySQL

Crie o banco de dados e um usuário dedicado para a aplicação:

```sql
CREATE DATABASE oris_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'oris_user'@'localhost' IDENTIFIED BY 'sua_senha_aqui';
GRANT ALL PRIVILEGES ON oris_db.* TO 'oris_user'@'localhost';
FLUSH PRIVILEGES;
```

Depois, crie as tabelas de uma das duas formas:

**Opção A — via schema.sql (manual):**

```bash
mysql -u root < database/schema.sql
```

**Opção B — via SQLAlchemy (recomendado em desenvolvimento):**

```bash
python -c "from app import create_app; from app.extensions import db; app = create_app(); app.app_context().push(); db.create_all()"
```

A Opção B garante que as tabelas fiquem sempre sincronizadas com os models
em `app/models/`.

## Modelo de dados (FASE 2)

Tabelas implementadas:

| Tabela        | Descrição                                                            |
|---------------|-----------------------------------------------------------------------|
| `usuarios`    | Usuários do sistema (nome, email único, senha_hash, perfil, ativo)    |
| `unidades`    | Unidades de Saúde Bucal (nome, CNES único, endereço, situação)        |
| `servicos`    | Serviços oferecidos por uma unidade (N:1 com `unidades`)              |
| `equipamentos`| Equipamentos de uma unidade, opcionalmente ligados a um serviço       |
| `alteracoes`  | Estrutura para o futuro fluxo de aprovação (usuário criador/aprovador)|
| `auditorias`  | Trilha de auditoria (audit log) — quem fez o quê e quando             |

Relacionamentos:

```
Usuario
 ├── alteracoes_criadas   (1:N — Alteracao.usuario_id)
 ├── alteracoes_aprovadas (1:N — Alteracao.approved_by)
 └── auditorias           (1:N — Auditoria.usuario_id)

Unidade
 ├── servicos             (1:N)
 └── equipamentos         (1:N)

Servico
 └── equipamentos         (1:N, opcional)
```

Nesta fase os campos `perfil` (Usuario) e `status` (Alteracao) já existem
com os valores previstos, mas as **regras** de permissão (RBAC) e o **fluxo**
de aprovação ainda não estão implementados — isso acontece nas Fases 4 e 7.

Nenhum dado de paciente, prontuário ou informação clínica é armazenado —
fora do escopo do MVP do ORIS.

## Como configurar o .env

Copie o arquivo de exemplo e ajuste os valores:

```bash
cp .env.example .env
```

Edite o `.env` com os dados do seu MySQL:

```
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=gere-uma-chave-forte-aqui
DB_HOST=localhost
DB_PORT=3306
DB_NAME=oris_db
DB_USER=oris_user
DB_PASSWORD=sua_senha_aqui
SESSION_LIFETIME_MINUTES=60
```

> O arquivo `.env` nunca deve ser enviado ao repositório (já está no
> `.gitignore`).

## Como executar

```bash
python run.py
```

A aplicação sobe em `http://127.0.0.1:5000`.

Para verificar que a aplicação e a conexão com o banco estão funcionando,
acesse:

```
GET http://127.0.0.1:5000/health
```

Resposta esperada:

```json
{
  "status": "ok",
  "app": "ORIS",
  "fase": "5 - crud de unidades"
}
```

## Autenticação (FASE 3)

O ORIS possui login individual por email/senha. Rotas disponíveis:

| Rota      | Método    | Descrição                                            |
|-----------|-----------|-------------------------------------------------------|
| `/login`  | GET, POST | Tela de login e processamento da autenticação          |
| `/logout` | GET       | Encerra a sessão e volta para `/login`                 |
| `/`       | GET       | Página protegida — exige sessão autenticada             |

**Como o login funciona:**

1. O usuário informa email e senha.
2. O sistema busca o usuário pelo email.
3. Verifica se o usuário existe, está **ativo** e se a senha confere
   (comparação feita via bcrypt, nunca texto puro).
4. Se tudo estiver correto, cria uma sessão Flask com o mínimo necessário
   (`usuario_id` e `autenticado`) e redireciona para `/`.
5. Se qualquer verificação falhar (usuário inexistente, senha errada ou
   usuário inativo), a mensagem exibida é sempre a mesma — genérica —
   para não revelar detalhes sobre a conta.

**Logout:** limpa toda a sessão e redireciona para `/login`.

**Rota protegida:** o decorator `login_required`
(`app/utils/decorators.py`) verifica a sessão no backend antes de liberar
o acesso — a proteção nunca depende apenas da interface.

## RBAC — Controle de acesso por perfil (FASE 4)

Toda rota restrita a um ou mais perfis usa o decorator
`roles_required(*perfis)` (`app/utils/decorators.py`), que:

1. verifica se existe sessão autenticada (senão, redireciona para `/login`);
2. verifica se o usuário ainda existe e está **ativo** (senão, encerra a
   sessão e redireciona para `/login` — mesmo que a sessão já existisse
   antes de o usuário ser desativado);
3. verifica se o `perfil` do usuário está entre os perfis permitidos
   (senão, HTTP 403 — página "Acesso negado").

Rotas de teste do RBAC (ainda sem funcionalidade real — servem apenas
para comprovar a autorização):

| Rota           | Quem acessa                              |
|----------------|-------------------------------------------|
| `/admin`       | ADMINISTRADOR                              |
| `/gestao`      | ADMINISTRADOR, GESTAO_INFORMACAO           |
| `/responsavel` | ADMINISTRADOR, RESPONSAVEL_SAUDE_BUCAL     |
| `/gestor`      | ADMINISTRADOR, GESTOR                      |

O ADMINISTRADOR acessa todas as áreas (conforme a Fase 4 define que esse
perfil "acessa todas as áreas administrativas"); os demais perfis só
acessam a própria área.

A página inicial (`/`) só mostra, no menu, os links das áreas que o
perfil do usuário autenticado pode acessar — mas isso é só uma
conveniência de interface; o bloqueio de verdade acontece sempre no
backend, mesmo que alguém digite a URL diretamente.

Quando um usuário autenticado tenta acessar uma área sem permissão, vê a
página "403 — Acesso negado", sem detalhes internos do sistema.

## CRUD de Unidades (FASE 5)

Primeira funcionalidade de negócio completa do ORIS — cadastro,
consulta, edição e alteração de situação das Unidades de Saúde Bucal.
Nenhuma exclusão física é feita: a situação (`ATIVA`/`INATIVA`/
`MANUTENCAO`) é o que muda, preservando o histórico.

| Rota                          | Método    | Quem acessa                                              |
|-------------------------------|-----------|-----------------------------------------------------------|
| `/unidades`                   | GET       | Qualquer usuário autenticado (inclusive GESTOR)             |
| `/unidades/<id>`              | GET       | Qualquer usuário autenticado (inclusive GESTOR)             |
| `/unidades/nova`               | GET, POST | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL   |
| `/unidades/<id>/editar`        | GET, POST | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL   |
| `/unidades/<id>/situacao`      | POST      | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL   |

GESTOR nunca altera dados — só consulta. A permissão para
GESTAO_INFORMACAO criar/editar segue a matriz de "Alterar dados"
definida na Fase 4 (`SIM*`, já que o fluxo de aprovação em si ainda
não existe — chega na Fase 7).

**Validações no backend:**

- Nome, CNES, tipo, cidade e UF são obrigatórios.
- CNES precisa ter só números (7 a 15 dígitos).
- CNES duplicado é bloqueado com mensagem amigável — tanto no cadastro
  quanto na edição — sem expor erro interno do banco.
- Situação só aceita `ATIVA`, `INATIVA` ou `MANUTENCAO`.
- Unidade inexistente retorna a página amigável "404 — Não encontrado".

A interface esconde os botões de criar/editar de quem não tem
permissão (só por usabilidade) — a proteção de verdade está sempre no
backend, através do `roles_required` já existente desde a Fase 4.

## Usuário de teste

Não existe usuário fixo/hardcoded no código. Para criar um usuário
(desenvolvimento ou demonstração), use o comando de CLI do Flask, que
pede a senha de forma oculta e já salva o hash bcrypt:

```bash
flask --app run.py criar-usuario
```

O comando pergunta:

- Nome completo
- Email
- Senha (digitada duas vezes, para confirmar — não aparece na tela)
- Perfil (`ADMINISTRADOR`, `GESTAO_INFORMACAO`, `RESPONSAVEL_SAUDE_BUCAL` ou `GESTOR`)

> Evite domínios reservados para teste como `.local`, `.test` ou
> `.example` no email — a validação de formato os rejeita. Prefira algo
> como `usuario@oris.com.br`.

Crie um usuário de cada perfil para demonstrar a matriz de acesso da
Fase 4 (`/admin`, `/gestao`, `/responsavel`, `/gestor`).

## Como rodar os testes

```bash
python -m pytest tests/ -v
```

## Perfis de usuário

O sistema tem 4 perfis:

1. **ADMINISTRADOR** — acesso total, gestão de usuários, acessa todas as áreas
2. **GESTAO_INFORMACAO** — consulta dados, valida/aprova alterações (fluxo real na Fase 7), consulta auditoria
3. **RESPONSAVEL_SAUDE_BUCAL** — consulta dados, cadastra/edita unidades, serviços e equipamentos (CRUDs reais nas Fases 5/6)
4. **GESTOR** — somente leitura, apenas consulta e visualização

As regras de acesso de cada perfil (RBAC) já estão implementadas desde a
Fase 4 — veja a seção "RBAC — Controle de acesso por perfil" acima. Os
CRUDs de negócio em si (unidades, serviços, equipamentos, aprovação)
ainda serão implementados nas próximas fases.

## Segurança implementada

Até o momento (FASE 5):

- Nenhuma credencial sensível fica hardcoded no código — tudo vem do `.env`
  via `python-dotenv`.
- `.env` está no `.gitignore` para nunca ser versionado.
- Conexão com o MySQL configurada via SQLAlchemy com usuário de banco
  dedicado (privilégio mínimo, sem usar o `root`).
- Senhas nunca são armazenadas em texto puro — apenas o hash bcrypt
  (biblioteca `bcrypt`), gerado com salt aleatório a cada chamada.
- Sessão do Flask guarda apenas `usuario_id` e `autenticado` — nunca a
  senha ou o hash.
- Cookies de sessão com `HttpOnly` e `SameSite=Lax` (e `Secure` em
  produção); `SECRET_KEY` sempre lida do `.env`.
- Proteção CSRF nativa do Flask-WTF em todos os formulários (login,
  cadastro/edição de unidade, alteração de situação).
- Mensagem de erro de login sempre genérica ("Email ou senha inválidos."),
  sem revelar se o email existe, se a senha está errada ou se a conta
  está inativa.
- Controle de acesso por perfil (RBAC) verificado sempre no backend
  (`roles_required`), nunca apenas escondendo links/botões na interface —
  segue o princípio de menor privilégio e prepara a segregação de
  funções entre quem edita (`RESPONSAVEL_SAUDE_BUCAL`) e quem aprova
  (`GESTAO_INFORMACAO`).
- Um usuário desativado perde o acesso imediatamente, mesmo que já
  tivesse uma sessão ativa antes de ser desativado.
- Páginas dedicadas de "Acesso negado" (HTTP 403) e "Não encontrado"
  (HTTP 404), sem expor detalhes internos do sistema (ex.: erro de
  banco de dados) para o usuário.
- Todo acesso ao banco passa pelo ORM (SQLAlchemy), sem SQL manual —
  proteção nativa contra SQL Injection.
- Unicidade de CNES validada tanto na aplicação (mensagem amigável)
  quanto no banco (constraint), cobrindo também condições de corrida.

Itens de segurança das próximas fases (fluxo de aprovação, auditoria
detalhada, LGPD) serão documentados aqui conforme forem implementados.

## Roadmap de fases

- [x] FASE 1 — Estrutura do projeto, ambiente, Flask, MySQL
- [x] FASE 2 — Banco de dados, models, usuários, perfis
- [x] FASE 3 — Login, bcrypt, sessão, logout
- [x] FASE 4 — RBAC e gerenciamento de acesso
- [x] FASE 5 — CRUD de Unidades
- [ ] FASE 6 — Serviços e equipamentos
- [ ] FASE 7 — Fluxo de aprovação
- [ ] FASE 8 — Auditoria
- [ ] FASE 9 — Dashboard
- [ ] FASE 10 — Testes, segurança, acabamento, README final

## Dados de demonstração

⚠️ Todos os dados de unidades, serviços, equipamentos e usuários utilizados
neste projeto são **fictícios**, criados exclusivamente para fins de
demonstração acadêmica. Nenhum dado real de paciente é utilizado ou
armazenado pelo sistema.
