# ORIS — Plataforma de Governança da Rede de Saúde Bucal

> ⚠️ **Status do projeto:** em desenvolvimento — Redesign Premium da Importação concluído (glassmorphism + gradiente navy→petróleo→turquesa).
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
  baseado em perfil, `.env` para configurações sensíveis, `CSRFProtect` global
- **Planilhas:** `pandas` + `openpyxl` (leitura de `.xlsx`/`.csv` no importador)

## Estrutura do projeto

```
ORIS/
│
├── app/
│   ├── __init__.py        # application factory
│   ├── extensions.py      # instância do SQLAlchemy
│   ├── forms.py            # formulários (Flask-WTF)
│   ├── cli.py               # comando `flask criar-usuario`
│   ├── routes/
│   │   ├── auth.py               # /login, /logout
│   │   ├── main.py               # "/" (rota protegida)
│   │   ├── areas.py              # /admin, /gestao, /responsavel, /gestor (RBAC)
│   │   ├── unidades.py           # CRUD de Unidades (com fluxo de aprovação)
│   │   ├── servicos.py           # CRUD de Serviços (com fluxo de aprovação)
│   │   ├── equipamentos.py       # CRUD de Equipamentos (com fluxo de aprovação)
│   │   ├── alteracoes.py         # listar, visualizar, aprovar, rejeitar
│   │   ├── auditoria.py          # /auditoria (somente leitura)
│   │   ├── dashboard.py          # /dashboard
│   │   ├── importacao.py         # importador de planilhas (.xlsx/.csv)
│   │   ├── usuarios.py           # administração de usuários (só ADMINISTRADOR)
│   │   ├── privacidade.py        # /privacidade (pública)
│   │   └── design_system.py      # /design-system (referência visual, pública)
│   ├── models/
│   │   ├── enums.py             # PerfilUsuario, situações, status, TipoOperacaoAlteracao
│   │   ├── mixins.py            # TimestampMixin (created_at/updated_at)
│   │   ├── usuario.py
│   │   ├── unidade.py
│   │   ├── servico.py
│   │   ├── equipamento.py
│   │   ├── alteracao.py          # + operacao, dados_novos (Fase 7)
│   │   └── auditoria.py          # + valor_anterior, valor_novo (Fase 8)
│   ├── templates/
│   │   ├── base.html            # layout com Bootstrap
│   │   ├── login.html
│   │   ├── index.html           # página protegida provisória
│   │   ├── dashboard.html       # indicadores, resumo, aprovações, atividade
│   │   ├── area_perfil.html     # áreas de teste do RBAC
│   │   ├── acesso_negado.html   # página de erro 403
│   │   ├── nao_encontrado.html  # página de erro 404
│   │   ├── erro_interno.html    # página de erro 500 (Fase 12)
│   │   ├── privacidade.html     # transparência/LGPD (Fase 12)
│   │   ├── design_system.html   # referência de tokens/componentes (Fase 13A)
│   │   ├── unidades/
│   │   │   ├── lista.html
│   │   │   ├── form.html         # cadastro e edição
│   │   │   └── detalhe.html
│   │   ├── servicos/              # mesmo padrão de unidades/
│   │   ├── equipamentos/          # mesmo padrão de unidades/
│   │   ├── alteracoes/
│   │   │   ├── lista.html
│   │   │   └── detalhe.html
│   │   ├── auditoria/
│   │   │   ├── lista.html
│   │   │   └── detalhe.html
│   │   ├── importacao/
│   │   │   ├── index.html
│   │   │   ├── nova.html
│   │   │   ├── mapeamento.html
│   │   │   ├── validacao_erros.html
│   │   │   └── previa.html
│   │   └── usuarios/
│   │       ├── lista.html
│   │       └── form.html         # criar e editar (+ mini-form de redefinir senha)
│   ├── static/
│   │   ├── css/
│   │   │   ├── tokens.css              # variáveis de cor/tipografia/raio/sombra (Fase 13A)
│   │   │   ├── oris-design-system.css  # componentes (botões, badges...) sobre o Bootstrap (Fase 13A)
│   │   │   ├── layout.css              # sidebar/header/breadcrumb/responsividade (Fase 13B)
│   │   │   └── dashboard.css           # hero/KPI cards/timeline do Dashboard (Fase 13B)
│   │   ├── js/
│   │   └── images/
│   ├── services/
│   │   ├── alteracoes_service.py  # registrar/aplicar/aprovar/rejeitar (Fase 7)
│   │   ├── auditoria_service.py   # registrar_auditoria (Fase 8)
│   │   ├── dashboard_service.py   # indicadores e listagens do dashboard (Fase 9)
│   │   └── importacao_service.py  # leitura, mapeamento e validação de planilhas (Fase 10)
│   └── utils/
│       ├── datetime_utils.py    # helper de data/hora (UTC)
│       ├── security.py          # hash/verificação de senha (bcrypt)
│       ├── decorators.py        # login_required, roles_required
│       ├── rbac.py               # matriz de acesso das áreas de teste
│       └── rate_limit.py         # rate limiting leve de login (Fase 12)
│
├── docs/
│   └── SEGURANCA.md         # relatório de auditoria de segurança (Fase 12)
│
├── database/
│   └── schema.sql           # DDL completo das tabelas (MySQL)
│
├── tests/
│   ├── test_fase1_estrutura.py
│   ├── test_fase2_models.py
│   ├── test_fase3_autenticacao.py
│   ├── test_fase4_rbac.py
│   ├── test_fase5_unidades.py
│   ├── test_fase6_servicos_equipamentos.py
│   ├── test_fase7_alteracoes.py
│   ├── test_fase8_auditoria.py
│   ├── test_fase9_dashboard.py
│   ├── test_fase10_importacao.py
│   ├── test_fase11_usuarios.py
│   ├── test_fase12_seguranca.py
│   ├── test_fase13a_design_system.py
│   └── test_fase13b_etapa1.py
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
  "fase": "13b-stage567 - ux/ui importacao usuarios e autenticacao"
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

## CRUD de Serviços e Equipamentos (FASE 6)

Segue exatamente o mesmo padrão do CRUD de Unidades (Fase 5).

| Rota                            | Método    | Quem acessa                                              |
|----------------------------------|-----------|-----------------------------------------------------------|
| `/servicos`                      | GET       | Qualquer usuário autenticado (inclusive GESTOR)             |
| `/servicos/<id>`                 | GET       | Qualquer usuário autenticado (inclusive GESTOR)             |
| `/servicos/novo`                  | GET, POST | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL   |
| `/servicos/<id>/editar`           | GET, POST | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL   |
| `/servicos/<id>/situacao`         | POST      | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL   |
| `/equipamentos`                   | GET       | Qualquer usuário autenticado (inclusive GESTOR)             |
| `/equipamentos/<id>`              | GET       | Qualquer usuário autenticado (inclusive GESTOR)             |
| `/equipamentos/novo`               | GET, POST | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL   |
| `/equipamentos/<id>/editar`        | GET, POST | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL   |
| `/equipamentos/<id>/situacao`      | POST      | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL   |

Diferente da Fase 5 (onde havia ambiguidade), aqui a Fase 6 definiu
explicitamente que GESTAO_INFORMACAO também cria/edita/altera situação
de Serviços e Equipamentos — igual a ADMINISTRADOR e
RESPONSAVEL_SAUDE_BUCAL. GESTOR continua só leitura.

**Relacionamentos e validações:**

- Todo Serviço pertence obrigatoriamente a uma Unidade existente — o
  formulário só lista unidades que existem no banco no momento da
  requisição, e o backend confere de novo antes de salvar.
- Todo Equipamento pertence obrigatoriamente a uma Unidade.
- A associação de um Equipamento a um Serviço é opcional — mas, se
  informada, o Serviço precisa existir **e** pertencer à mesma Unidade
  selecionada para o equipamento. Um serviço de outra unidade é
  bloqueado com mensagem amigável.
- Situação de Serviço/Equipamento aceita apenas `ATIVO` ou `INATIVO`.
- Nenhuma exclusão física — apenas alteração de situação.

A página de detalhes de uma Unidade lista os Serviços e Equipamentos
associados a ela. A listagem de Serviços e Equipamentos aceita filtros
simples via querystring (`?unidade_id=`, `?situacao=`, e também
`?servico_id=` para equipamentos).

## Fluxo de alterações e aprovação (FASE 7)

A partir desta fase, **criar, editar ou alterar a situação** de uma
Unidade, Serviço ou Equipamento não grava mais direto no banco.
Cada uma dessas ações registra uma `Alteracao` com status `PENDENTE`
e só é de fato aplicada quando aprovada por um usuário autorizado —
que nunca pode ser quem fez a solicitação.

```
Solicitante (ADMIN / GESTAO_INFORMACAO / RESPONSAVEL_SAUDE_BUCAL)
        │
        ▼
   Realiza uma ação (criar/editar/alterar situação)
        │
        ▼
  Alteracao registrada — status PENDENTE
        │
        ▼
  ADMINISTRADOR ou GESTAO_INFORMACAO (nunca o solicitante)
        │
     ┌──┴──┐
     ▼     ▼
 APROVAR  REJEITAR
     │       │
     ▼       ▼
 Aplicada  Nada é alterado
```

**Quem solicita:** `ADMINISTRADOR`, `GESTAO_INFORMACAO`,
`RESPONSAVEL_SAUDE_BUCAL`. `GESTOR` nunca solicita (é só leitura).

**Quem aprova/rejeita:** somente `ADMINISTRADOR` e `GESTAO_INFORMACAO`
— e nunca o próprio solicitante, mesmo que o perfil dele permita
aprovar em geral. Essa regra é sempre verificada no backend
(`app/services/alteracoes_service.py`), nunca só na interface.

| Rota                              | Método | Quem acessa                              |
|------------------------------------|--------|--------------------------------------------|
| `/alteracoes`                      | GET    | Qualquer usuário autenticado                |
| `/alteracoes/<id>`                 | GET    | Qualquer usuário autenticado                |
| `/alteracoes/<id>/aprovar`         | POST   | ADMINISTRADOR, GESTAO_INFORMACAO (exceto o solicitante) |
| `/alteracoes/<id>/rejeitar`        | POST   | ADMINISTRADOR, GESTAO_INFORMACAO (exceto o solicitante) |

A listagem aceita filtro por `?status=` (`PENDENTE`/`APROVADO`/
`REJEITADO`) e por `?tabela=` (`unidades`/`servicos`/`equipamentos`).

**Como a aprovação aplica a mudança:** o model `Alteracao` ganhou dois
campos nesta fase — `operacao` (CRIAR/EDITAR/ALTERAR_SITUACAO) e
`dados_novos` (JSON com os valores necessários). Sem eles não haveria
como saber, no momento da aprovação, o que fazer nem com quais
valores — a alternativa seria aplicar a mudança na hora e "fingir"
que está pendente, o que contraria exatamente o objetivo da fase. Por
isso `registro_id` também passou a ser opcional: enquanto uma
solicitação de **criação** está pendente, o registro ainda não
existe.

Aprovar e aplicar acontecem na mesma transação: se a aplicação falhar
(por exemplo, duas solicitações pendentes de criação com o mesmo
CNES — a segunda só conflita quando alguém tenta aprová-la), nada é
salvo e a alteração continua `PENDENTE`, pronta para ser corrigida ou
rejeitada.

## Auditoria e rastreabilidade (FASE 8)

A tabela `Auditoria` (criada na Fase 2) passa a ser preenchida de
verdade. Toda ação relevante do sistema gera um registro, sempre na
mesma transação da operação que descreve — se a operação falhar e
sofrer rollback, a auditoria correspondente cai junto.

**Ações auditadas:** `LOGIN`, `LOGOUT`, `SOLICITAR_ALTERACAO`,
`APROVAR_ALTERACAO`, `REJEITAR_ALTERACAO`, e — só quando uma alteração
é efetivamente aprovada — `CRIAR`, `EDITAR` ou `ALTERAR_SITUACAO`.

**Distinção importante (exigida pela própria Fase 8):** solicitar uma
criação/edição/alteração de situação NUNCA gera uma auditoria de
`CRIAR`/`EDITAR`/`ALTERAR_SITUACAO` enquanto a alteração está
`PENDENTE` — só `SOLICITAR_ALTERACAO`. A auditoria da mudança de fato
(com valores antes/depois) só é criada no momento em que a alteração é
aprovada e aplicada. Uma alteração rejeitada nunca gera auditoria de
`CRIAR`/`EDITAR`/`ALTERAR_SITUACAO`, porque nada chegou a ser
escrito no registro de negócio.

Cada evento de aprovação gera, na prática, dois registros de
auditoria: um creditado ao **solicitante original** (a mudança em si
— ex.: `EDITAR` com `valor_anterior`/`valor_novo`) e outro creditado
ao **aprovador** (`APROVAR_ALTERACAO`, referenciando a alteração
decidida). Isso mantém claro tanto quem propôs a mudança quanto quem
autorizou.

**Valores antes/depois:** `valor_anterior` e `valor_novo` guardam, em
JSON, só os campos que realmente mudaram (nunca o registro inteiro,
nunca senha ou hash) — ex.: `{"situacao": "ATIVA"}` →
`{"situacao": "MANUTENCAO"}`.

**Quem consulta:** somente `ADMINISTRADOR` e `GESTAO_INFORMACAO`
(mesma matriz da Fase 4), via `/auditoria` (listagem, com filtro por
usuário/ação/entidade/data) e `/auditoria/<id>` (detalhe, com
valores antes/depois). `RESPONSAVEL_SAUDE_BUCAL` e `GESTOR` recebem
403.

**Proteção:** a auditoria é somente leitura — propositalmente não
existe nenhuma rota de edição ou exclusão de registros de auditoria,
nem mesmo para ADMINISTRADOR. A única forma de um registro existir é
através do serviço central `app/services/auditoria_service.py`,
chamado internamente pelo próprio sistema.

## Dashboard (FASE 9)

`/dashboard` reúne uma visão geral da Rede de Saúde Bucal, com dados
reais calculados direto do banco (`app/services/dashboard_service.py`)
— nenhum dado fictício. Acessível aos 4 perfis (`ADMINISTRADOR`,
`GESTAO_INFORMACAO`, `RESPONSAVEL_SAUDE_BUCAL`, `GESTOR`).

**Indicadores:** total/ativas/inativas/em manutenção de Unidades;
total/ativos/inativos de Serviços e de Equipamentos;
pendentes/aprovadas/rejeitadas de Alterações.

**Resumo da rede:** lista das unidades (nome, CNES, município, UF,
situação), com filtro por situação via `?situacao=`.

**Alterações pendentes:** reaproveita a listagem já existente da
Fase 7 — nenhum mecanismo novo de aprovação foi criado. Quem tem
permissão para aprovar (`ADMINISTRADOR`/`GESTAO_INFORMACAO`) vê um
atalho direto para agir; os demais perfis só visualizam.

**Atividade recente:** reaproveita a auditoria da Fase 8, respeitando
a mesma restrição de acesso já estabelecida lá — `ADMINISTRADOR` e
`GESTAO_INFORMACAO` veem a atividade de todo o sistema;
`RESPONSAVEL_SAUDE_BUCAL` e `GESTOR` veem só a própria atividade (e
o dashboard avisa isso explicitamente), já que esses dois perfis não
têm acesso à auditoria administrativa completa. Nunca exibe senha ou
hash — o model `Auditoria` nunca armazena esses dados.

## Importador de Planilhas (FASE 10)

Importa Unidades, Serviços e Equipamentos a partir de planilhas
**.xlsx** ou **.csv** (`pandas` + `openpyxl`), sem nunca escrever
direto nas tabelas de negócio — cada linha nova ou alterada vira uma
solicitação de alteração comum, passando pelo mesmo mecanismo de
aprovação da Fase 7.

**Fluxo:** upload → leitura → mapeamento de colunas → validação →
pré-visualização → confirmação → solicitação `PENDENTE` → aprovação
(Fase 7) → aplicação → auditoria (Fase 8).

| Rota                          | Método | Quem acessa                                            |
|--------------------------------|--------|----------------------------------------------------------|
| `/importacao`                   | GET    | Qualquer usuário autenticado (GESTOR só consulta)         |
| `/importacao/template/<entidade>` | GET  | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL |
| `/importacao/nova`               | GET   | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL |
| `/importacao/mapear`             | POST  | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL |
| `/importacao/validar`            | POST  | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL |
| `/importacao/confirmar`          | POST  | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL |

`GESTOR` nunca importa — apenas consulta a tela principal, coerente
com a matriz de RBAC já estabelecida (é sempre somente leitura).

**Entidades importáveis e campos:**

- **Unidades:** nome, CNES, tipo, endereço, bairro, cidade, UF,
  situação — mesmas validações do cadastro manual (Fase 5): CNES
  numérico de 7 a 15 dígitos, UF com 2 letras, situação em
  `ATIVA`/`INATIVA`/`MANUTENCAO`.
- **Serviços:** nome, **CNES da unidade** (identifica a unidade já
  cadastrada — não se inventou um novo identificador), situação em
  `ATIVO`/`INATIVO`.
- **Equipamentos:** nome, tipo, CNES da unidade, nome do serviço
  (opcional), situação. Mantém a regra já existente (Fase 6): se um
  serviço for informado, ele precisa pertencer à mesma unidade.

**Mapeamento de colunas:** a planilha não precisa ter os mesmos nomes
de coluna do ORIS — o sistema sugere automaticamente por sinônimos
exatos (ex.: "Código CNES", "Município", "Estado"), mas sempre permite
conferência e correção manual antes de validar.

**Validação:** todas as linhas são validadas de uma vez. Se houver
qualquer linha inválida, a planilha inteira é rejeitada (nenhuma
importação parcial nesta versão) — o usuário corrige o arquivo e
envia novamente. O resumo mostra total/válidos/com erros, e cada erro
aponta linha, campo, valor recebido e o motivo.

**Novo vs. existente vs. alterado:** Unidades são reconciliadas pelo
CNES (campo único já existente); Serviços e Equipamentos, por
nome + unidade (não têm um código próprio). Se o CNES/nome já existe
no banco, a linha é uma **atualização** (comparando campo a campo);
se não muda nada, é marcada "sem alteração" e não gera solicitação
nenhuma. Um **CNES duplicado dentro da própria planilha** (não no
banco) é tratado como erro, já que não haveria como saber qual das
duas linhas deveria prevalecer — essa é a leitura adotada para
conciliar o exemplo de erro do enunciado ("CNES já cadastrado") com o
pedido de diferenciar novo/existente/alterado usando o CNES; os dois
pedidos juntos só fazem sentido dessa forma, e essa decisão está
documentada em `app/services/importacao_service.py`.

**Integração com a Fase 7:** a confirmação nunca insere/atualiza
direto — cada linha nova ou alterada vira uma `Alteracao` `PENDENTE`
(via o mesmo `app.services.alteracoes_service.registrar_alteracao`
usado pelos formulários manuais). Quem importou não pode aprovar a
própria importação — a mesma segregação de funções da Fase 7 se
aplica integralmente, sem nenhum mecanismo de aprovação paralelo.

**Integração com a Fase 8:** a solicitação, a aprovação/rejeição e a
mudança efetivamente aplicada geram os mesmos tipos de registro de
auditoria de qualquer outra alteração (`SOLICITAR_ALTERACAO`,
`APROVAR_ALTERACAO`/`REJEITAR_ALTERACAO`, `CRIAR`/`EDITAR`). Além
disso, a confirmação do lote inteiro gera um registro extra
`IMPORTAR_PLANILHA`, com um resumo (quantas linhas novas, alteradas e
sem alteração). Nenhuma senha, hash ou conteúdo bruto do arquivo é
registrado.

**Segurança do upload:** extensão validada contra uma lista fechada
(`.csv`/`.xlsx`); tamanho máximo de 5 MB; até 2000 linhas por
planilha; o nome do arquivo em disco é sempre gerado pelo servidor
(nunca o nome enviado pelo usuário); armazenamento em uma pasta
temporária dedicada, fora de `static`/`templates`; nenhum arquivo é
executado; o arquivo é removido assim que deixa de ser necessário
(falha de validação ou confirmação concluída).

**Template de planilha:** cada entidade tem um modelo `.csv` para
download (`/importacao/template/<entidade>`), só com os cabeçalhos
esperados — sem nenhum dado de exemplo, para nunca acabar sendo
importado por engano como um registro real.

**Limitações atuais:** não há importação parcial (tudo ou nada); um
arquivo cuja aba/pré-visualização foi aberta mas nunca confirmada nem
rejeitada fica temporariamente em disco até ser processado ou até uma
limpeza manual — não há um job de limpeza automática (fora do escopo
desta fase, que evita processamento assíncrono); não há integração
real com o CNES (a validação do código é só de formato).

**Correção de segurança feita nesta fase:** `CSRFProtect` passou a ser
inicializado globalmente na aplicação. Antes, `{{ csrf_token() }}` só
funcionava dentro de páginas que recebiam uma `FlaskForm` — o que
quebrava silenciosamente a listagem de alterações (Fase 7) sempre que
um aprovador de verdade (diferente de quem solicitou) via a lista com
itens pendentes. Registrar `CSRFProtect` corrige isso e também
protege, de forma consistente, os novos formulários do importador.

## Administração de Usuários (FASE 11)

Módulo exclusivo do **ADMINISTRADOR** para gerenciar os usuários do
sistema — os outros três perfis (`GESTAO_INFORMACAO`,
`RESPONSAVEL_SAUDE_BUCAL`, `GESTOR`) recebem HTTP 403 ao tentar
acessar qualquer rota de `/usuarios`, sempre verificado no backend
via `roles_required`, nunca só escondendo o link do menu.

| Rota                          | Método    | Descrição                                    |
|--------------------------------|-----------|-------------------------------------------------|
| `/usuarios`                     | GET       | Listagem, com busca por nome/email e filtro por perfil/situação |
| `/usuarios/novo`                | GET, POST | Criar usuário                                    |
| `/usuarios/<id>/editar`         | GET, POST | Editar nome, email e perfil                      |
| `/usuarios/<id>/situacao`       | POST      | Ativar/desativar                                 |
| `/usuarios/<id>/senha`          | POST      | Redefinição administrativa de senha              |

**Criação:** nome, email, senha e perfil. Email precisa ser único
(mesma verificação amigável já usada em Unidades/CNES). A senha é
transformada em hash bcrypt antes de ser salva — nunca fica em texto
puro em nenhum momento, nem na criação nem depois. **Regra mínima de
senha:** esta é a primeira vez que o projeto codifica um tamanho
mínimo de senha (8 caracteres) — o `LoginForm` da Fase 3 nunca exigiu
isso, só que o campo não estivesse vazio; adotamos 8 caracteres como
esse mínimo, tanto na criação quanto na redefinição de senha.

**Edição:** nome, email e perfil — não a senha (ver "Redefinir
senha" abaixo) nem a situação (tem seu próprio botão/rota, seguindo o
mesmo padrão já usado em Unidade/Serviço/Equipamento).

**Ativar/desativar:** nenhuma exclusão física de usuário existe em
lugar nenhum do sistema. Um usuário desativado:
- não consegue fazer login (checado desde a Fase 3, reaproveitado
  aqui sem alterações);
- perde o acesso a **qualquer** área protegida imediatamente, mesmo
  que já tivesse uma sessão ativa antes de ser desativado. Isso já
  valia para rotas que exigem um perfil específico (`roles_required`,
  desde a Fase 4) — nesta fase, a mesma checagem de "o usuário
  continua ativo?" foi estendida também para `login_required`
  (usada pelas telas só de consulta), fechando uma lacuna: antes,
  uma sessão antiga de um usuário desativado ainda conseguia ver,
  por exemplo, a listagem de Unidades, embora não conseguisse fazer
  login de novo.

**Proteção do último administrador:** o sistema nunca pode ficar sem
nenhum `ADMINISTRADOR` ativo. Duas ações são bloqueadas quando
deixariam a contagem de administradores ativos chegar a zero:
- desativar o último `ADMINISTRADOR` ativo;
- mudar o perfil do último `ADMINISTRADOR` ativo para qualquer outro.

A regra vale tanto para um administrador mexendo em outra conta
quanto na própria — é a mesma verificação nos dois casos.

**Redefinição de senha:** o `ADMINISTRADOR` pode definir uma nova
senha para qualquer usuário (por exemplo, se ele esquecer a própria).
A senha nova também vira hash bcrypt antes de salvar; a senha antiga
nunca é exibida (e não há como recuperá-la, só substituí-la). Não há
e-mail de recuperação nem token de redefinição nesta fase — é uma
ação administrativa direta, feita pelo `ADMINISTRADOR` logado.

**Auditoria:** toda ação gera um registro rastreável —
`CRIAR_USUARIO`, `EDITAR_USUARIO`, `ATIVAR_USUARIO`,
`DESATIVAR_USUARIO`, `ALTERAR_PERFIL` e `REDEFINIR_SENHA` — cada um
atribuído ao `ADMINISTRADOR` que executou a ação. Uma única edição
pode gerar mais de um registro (ex.: mudar nome e perfil ao mesmo
tempo gera `EDITAR_USUARIO` e `ALTERAR_PERFIL` separadamente), cada
um só com os campos que de fato mudaram. Nunca é registrada senha,
hash ou qualquer credencial — nem na criação, nem na redefinição.

## Segurança e LGPD (FASE 12)

Esta fase foi dedicada a uma auditoria técnica de segurança do
projeto inteiro e à implementação dos controles de proteção de dados
compatíveis com o escopo do ORIS. O relatório completo — achados
classificados por severidade, o que foi corrigido, e as limitações
que dependem do ambiente de produção — está em
[`docs/SEGURANCA.md`](docs/SEGURANCA.md).

**Novidades técnicas desta fase:**

- **Headers HTTP de segurança** em toda resposta:
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin` e uma
  `Content-Security-Policy` básica.
- **Página de erro 500 amigável** — nenhum erro inesperado expõe
  stack trace, SQL ou caminhos internos ao usuário.
- **Rate limiting leve de login** (em memória, sem Redis): após 5
  tentativas malsucedidas para o mesmo (IP, email) em 5 minutos, o
  login fica temporariamente bloqueado — inclusive para a senha
  correta, até a janela passar. É por processo (não distribuído);
  para produção com múltiplos workers, recomenda-se um backend
  compartilhado.
- **`/privacidade`** — página pública de transparência (não exige
  login) com finalidade do sistema, categorias de dados tratados,
  quem tem acesso, controles de segurança e política de retenção.

**Achados corrigidos nesta fase:** ausência de headers de segurança,
ausência de página de erro 500 dedicada, ausência de rate limiting no
login, ausência de página de transparência. Dois achados de fases
anteriores (CSRF global e revalidação de usuário ativo em
`login_required`) já haviam sido corrigidos nas Fases 10 e 11,
respectivamente, e são revalidados no relatório.

**O que foi revisado e confirmado sem alterações necessárias:** RBAC
de todas as rotas, proteção contra IDOR (todo acesso por ID retorna
404 para inexistente e é protegido por RBAC), ausência de XSS
(autoescape do Jinja nunca desativado, nenhum uso de `\|safe`),
ausência de SQL Injection (100% via ORM), e nenhuma credencial real
no código-fonte ou no histórico do Git.

### LGPD — finalidade, minimização e retenção

**Finalidade:** o ORIS existe para apoiar a gestão e governança das
informações da Rede de Saúde Bucal — organizar cadastros, controlar
alterações via aprovação, manter rastreabilidade e apoiar a gestão
através do dashboard. O sistema **não trata** prontuários, dados
clínicos, diagnósticos ou dados de pacientes — isso está fora do
escopo deste MVP.

**Minimização:** os únicos dados pessoais tratados hoje são os dos
usuários do próprio sistema — nome, email, perfil, situação
(ativo/inativo) e os registros de auditoria da atividade desses
usuários. Não são coletados CPF, telefone, endereço residencial ou
qualquer outro dado sem necessidade funcional direta.

**Retenção:** usuários desativados não são excluídos (preserva
histórico/auditoria); registros de auditoria não são apagados pela
aplicação; dados operacionais seguem a necessidade administrativa
definida pelo responsável pelo sistema. Prazos específicos de
retenção e descarte ainda precisam ser definidos pelo órgão
responsável — o ORIS não inventa um prazo legal.

**Consentimento e base legal:** o ORIS é uma plataforma de gestão
administrativa; este projeto não afirma uma base legal específica de
tratamento nem exige um checkbox genérico de "concordo com a LGPD" —
isso depende do contexto jurídico real de quem opera o sistema.

**HTTPS/TLS em produção:** o código já diferencia
`SESSION_COOKIE_SECURE=True` em `ProductionConfig` (exigindo HTTPS
para o cookie de sessão trafegar) de `False` em desenvolvimento local
— mas o TLS em si é responsabilidade do ambiente de implantação
(servidor web/proxy reverso), não algo que uma aplicação Flask sozinha
resolve.

**Criptografia:** senhas usam hash bcrypt (irreversível, nunca
criptografia reversível). O ORIS não introduziu nenhum campo
artificial só para justificar o uso de AES — não há, hoje, nenhum
dado no MVP que exija criptografia reversível em repouso; se um
campo assim surgir no futuro, a recomendação é AES-256-GCM, com a
chave fora do código-fonte.

## Design System e Identidade Visual (FASE 13A)

Esta fase criou o **Design System** do ORIS — a base visual reutilizável
para as próximas telas — sem redesenhar ainda cada tela de negócio
(isso é a Fase 13B) e sem alterar nenhuma regra de negócio, model,
autenticação, RBAC, aprovação, auditoria, importação ou segurança.

**Direção visual:** Health-Tech + Gov-Tech + plataforma de governança —
tecnologia, saúde, confiança e institucionalidade, evitando parecer
hospital genérico, sistema de governo datado, SaaS de fintech,
cyberpunk ou interface "futurista"/gamer.

**Tokens de cor** (`app/static/css/tokens.css`), com função semântica
clara — o azul profundo estrutura a interface, a turquesa é usada como
destaque, e as cores de status (sucesso/atenção/erro) nunca mudam de
significado:

| Token | Cor | Uso |
|-------|-----|-----|
| `--oris-navy` | `#0B2A4A` | Estrutura (navbar, títulos) |
| `--oris-blue` | `#123B63` | Apoio ao navy (gradientes, textos escuros) |
| `--oris-petroleum` | `#155E75` | Links, botões secundários |
| `--oris-teal` | `#18B7B0` | Destaque/marca (botão principal, foco) |
| `--oris-cyan` | `#39C6D3` | Realces e estados de hover |
| `--oris-bg` / `--oris-surface` | `#F7FAFA` / `#DDF4F5` | Fundo da aplicação / superfícies suaves |
| `--oris-success` / `--oris-warning` / `--oris-danger` | `#39A96B` / `#E9A23B` / `#D9534F` | Status semânticos |

Também há tokens de tipografia, raio de borda, sombra e dimensões de
layout (sidebar, navbar, largura de conteúdo) — ver o arquivo para a
lista completa.

**Tipografia:** duas famílias, claramente distintas —
[Space Grotesk](https://fonts.google.com/specimen/Space+Grotesk) para
títulos (geométrica, técnica, sem parecer "futurista") e
[IBM Plex Sans](https://fonts.google.com/specimen/IBM+Plex+Sans) para
texto de interface/corpo (extremamente legível, de caráter
institucional/técnico).

**Onde já está aplicado nesta fase:** o "chrome" compartilhado por
todas as telas em `base.html` — navegação, tipografia global, botões,
badges de status, alertas e foco de teclado — construído em
`app/static/css/oris-design-system.css`, uma camada **sobre** o
Bootstrap (não o substitui, não introduz um framework novo). O layout
interno de cada tela de negócio (tabelas e formulários específicos de
Unidade/Serviço/Equipamento etc.) continua com a mesma estrutura até a
Fase 13B.

**Onde ver:** a página [`/design-system`](/design-system) (pública,
sem exigir login) mostra a paleta, a tipografia e os componentes
básicos (botões, badges, alertas, formulário) vivos, com os tokens
reais aplicados — serve como referência para a aplicação detalhada da
Fase 13B.

## UX/UI Final — Etapa 1: Estrutura Global + Dashboard (FASE 13B)

Esta é a **primeira etapa** da Fase 13B (UX/UI Final). Ela aplicou o
Design System da Fase 13A à estrutura global da aplicação e ao
Dashboard — **as demais telas (Unidades, Serviços, Equipamentos,
Aprovações, Auditoria, Importação, Usuários, Privacidade, Login)
ainda não foram redesenhadas** e ficam para as próximas etapas.

**Estrutura global:** a antiga barra de navegação horizontal foi
substituída por **sidebar + header + conteúdo**:

- **Sidebar** (azul navy, com gradiente e fallback sólido): logo ORIS
  no topo e os itens Dashboard, Unidades de Saúde, Serviços,
  Equipamentos, Aprovações, Auditoria, Importar e Usuários — cada um
  com ícone (Bootstrap Icons), estado normal, hover e um destaque em
  turquesa para o item ativo. **O RBAC não mudou**: Auditoria continua
  visível só para `ADMINISTRADOR`/`GESTAO_INFORMACAO`, e Usuários só
  para `ADMINISTRADOR` — validado explicitamente para os 4 perfis.
- **Header**: breadcrumb à esquerda (`Início / Dashboard`, definido
  por um bloco Jinja que cada tela pode sobrescrever — só o Dashboard
  o faz nesta etapa) e, à direita, um avatar simples (inicial do
  nome), nome e perfil do usuário logado, e o botão de sair.
- **Menu mobile**: implementado com a técnica do "checkbox hack" (um
  `<input type="checkbox">` oculto + `<label>` como botão) — abre e
  fecha a sidebar em telas estreitas **sem nenhum JavaScript**,
  mantendo a CSP restrita da Fase 12.

**Dashboard redesenhado:** hero de boas-vindas ("Olá, [nome]" +
descrição da finalidade do sistema, com um elemento gráfico
decorativo discreto de "pontos conectados"), os mesmos indicadores da
Fase 9 em cards com ícone e um pequeno resumo (ex.: "3 ativas · 1
inativa"), com o card de **Alterações pendentes** visualmente
destacado por representar uma ação de governança. O resumo da rede e
a atividade recente (com a mesma regra de visibilidade por perfil da
Fase 9, inalterada) foram reapresentados como painéis e uma timeline.
**Nenhum indicador novo foi criado** — todos os números vêm,
exatamente como antes, de `app/services/dashboard_service.py`.

**Responsividade:** grade de KPIs de 4 colunas em telas largas, 2 em
tablets e 1 em celulares; sidebar recolhida por padrão em telas até
992px, reaberta pelo botão de menu; testado visualmente em 1440px e
375px.

**Acessibilidade básica:** foco de teclado visível (contorno em
turquesa) em links, botões e campos; `aria-label` no botão de menu e
na sidebar; texto sempre acompanhando a cor nos badges de status
(nunca só a cor sozinha).

**Microinterações:** transições de 150–250ms em hover de links do
menu e nos KPI cards (leve elevação) — nada além disso.

**Screenshots:** geradas em `docs/screenshots/` (`dashboard-desktop.png`,
`dashboard-mobile.png`, `sidebar.png`, `header.png`). Duas correções
reais de compatibilidade foram feitas durante a geração: um
`background-color` sólido como reforço antes de cada gradiente
(navegadores/motores sem suporte a gradiente moderno) e a troca da
sidebar de `position: fixed` para `position: sticky` + Flexbox — mais
robusta e correta para o layout pretendido em qualquer navegador.

## UX/UI Final — Stage 2A: Unidades de Saúde (FASE 13B)

Segunda etapa da Fase 13B: aplica o Design System às 3 telas de
Unidades (listagem, detalhe, formulário de criar/editar). **As demais
telas continuam como antes** — Serviços, Equipamentos, Aprovações,
Auditoria, Importação, Usuários, Privacidade e Login ficam para
etapas futuras.

**O que mudou:** cabeçalho de página reutilizável (título + descrição
+ ação principal), uma tira de indicadores agregados na listagem
(Total/Ativas/Inativas/Em manutenção — calculados a partir da mesma
lista de unidades já carregada pela rota, **nenhuma consulta nova**),
tabela refinada com badges de situação, tela de detalhe organizada em
seções (Identificação/Localização/Registro), e formulário de
criar/editar agrupado da mesma forma. **Nenhuma rota, validação,
regra de negócio ou permissão foi alterada** — validado explicitamente
para os 4 perfis (GESTOR continua sem poder criar/editar/alterar
situação) e para o fluxo de aprovação da Fase 7 (criar/editar continua
gerando uma solicitação `PENDENTE`, nunca aplicando direto).

**Componentes reutilizados do Design System:** `.oris-page-header`,
`.oris-stat-strip`, `.oris-panel`, `.oris-empty-state`,
`.oris-detail-grid`, `.oris-back-link` — todos em
`app/static/css/oris-design-system.css`; nenhum CSS novo específico
de Unidades foi necessário.

**Correções feitas durante esta etapa:**
- `.oris-panel` estava definido só em `dashboard.css` (carregado
  apenas na página do Dashboard) mas era usado pelas telas de
  Unidades — movido para `oris-design-system.css`, onde já é
  carregado globalmente.
- Breadcrumbs longos podiam sobrepor a identidade do usuário no
  header em telas muito estreitas — em telas ≤576px, o breadcrumb
  agora mostra só a página atual (padrão comum de breadcrumb
  responsivo).

**Screenshots:** `unidades-desktop.png`, `unidades-mobile.png`,
`unidade-detalhe-desktop.png`, `unidade-nova-desktop.png`,
`unidade-nova-mobile.png`, `unidade-editar-desktop.png`, em
`docs/screenshots/`.

## UX/UI Final — Stage 2B: Serviços e Equipamentos (FASE 13B)

Terceira etapa da Fase 13B: aplica o mesmo padrão visual da Stage 2A
às 8 telas de Serviços e Equipamentos (listagem, detalhe,
criar/editar de cada um). **As demais telas continuam como antes** —
Dashboard, Aprovações, Auditoria, Importação, Usuários, Privacidade e
Login ficam para etapas futuras; Unidades não foi tocada de novo.

**O que mudou:** mesmo cabeçalho de página, tira de indicadores
(Total/Ativos/Inativos — calculados a partir da mesma lista já
carregada, **nenhuma consulta nova**), filtros existentes
reorganizados visualmente (sem alterar a lógica), tabelas com badges
de situação, telas de detalhe organizadas em seções, formulários
agrupados. Na listagem e no detalhe de Equipamentos, a associação
Equipamento → Unidade → Serviço ficou visualmente clara (usando os
mesmos relacionamentos já carregados pela rota). **Nenhuma rota,
validação, regra de negócio ou permissão foi alterada** — validado
explicitamente para os 4 perfis e para o fluxo de aprovação completo
das duas entidades (solicitar → bloquear autoaprovação → aprovar →
aplicar → auditar), incluindo a regra de compatibilidade
"Serviço do equipamento precisa pertencer à mesma unidade".

**Componentes reutilizados:** exatamente os mesmos da Stage 2A
(`.oris-page-header`, `.oris-stat-strip`, `.oris-panel`,
`.oris-empty-state`, `.oris-detail-grid`, `.oris-back-link`) —
**nenhum CSS novo foi necessário** para esta etapa.

**Screenshots:** `servicos-desktop.png`, `servicos-mobile.png`,
`servico-detalhe-desktop.png`, `servico-form-desktop.png`,
`equipamentos-desktop.png`, `equipamentos-mobile.png`,
`equipamento-detalhe-desktop.png`, `equipamento-form-desktop.png`,
em `docs/screenshots/`.

## UX/UI Final — Stage 3: Módulo de Aprovações (FASE 13B)

Quarta etapa da Fase 13B: aplica o Design System à listagem e ao
detalhe de Alterações (`/alteracoes`), tornando o fluxo de aprovação
já existente (Fase 7) muito mais fácil de entender visualmente. **As
demais telas continuam como antes.**

**O que mudou:** mesmo cabeçalho de página e tira de indicadores
(Total/Pendentes/Aprovadas/Rejeitadas — calculados a partir da mesma
lista já carregada, **nenhuma consulta nova**). Na tela de detalhe —
a mais importante desta etapa — a informação agora é organizada em
blocos claros: **Solicitante**, **Alteração** (entidade, registro,
operação, e quem decidiu/quando), **O que muda** (comparação
antes → depois, extraída da própria descrição já gravada pela Fase 7)
e **Valores propostos** (campos da alteração, decodificados do JSON
já existente em `Alteracao.dados_novos` — omitindo IDs técnicos como
`unidade_id`, já que o contexto relacional aparece em texto). Para
uma criação (`CRIAR`), a tela mostra "Novo registro" em vez de uma
comparação, já que não existe um "antes". **Nenhuma regra de
aprovação, rejeição, autoaprovação ou auditoria foi alterada** —
validado explicitamente com MySQL real (solicitar → bloquear
autoaprovação → outro usuário aprova/rejeita → aplica ou não →
audita) e para os 4 perfis.

**Achado corrigido:** o badge de "Rejeitado" usava a cor cinza
(`bg-secondary`) em vez da cor de erro do Design System
(`bg-danger`) — corrigido para seguir a mesma convenção de
Pendente=aviso / Aprovado=sucesso / Rejeitado=erro.

**Componentes reutilizados:** os mesmos das etapas anteriores
(`.oris-page-header`, `.oris-stat-strip`, `.oris-panel`,
`.oris-empty-state`, `.oris-detail-grid`, `.oris-back-link`) — só
foram adicionados dois filtros de template (`from_json`,
`campos_visiveis`, `rotulo_campo`), puramente de apresentação, para
decodificar e rotular os dados que já existiam.

**Screenshots:** `aprovacoes-desktop.png`, `aprovacoes-mobile.png`,
`aprovacao-pendente-desktop.png`, `aprovacao-pendente-mobile.png`,
`aprovacao-aprovada-desktop.png`, `aprovacao-rejeitada-desktop.png`,
em `docs/screenshots/`.

## UX/UI Final — Stage 4: Auditoria (FASE 13B)

Quinta etapa da Fase 13B: aplica o Design System à tela de Auditoria
(`/auditoria`), mantendo-a **estritamente somente leitura** — nenhuma
rota de edição ou exclusão existe, nem mesmo para ADMINISTRADOR.

**O que mudou:** cabeçalho de página com um selo "Somente leitura"
sempre visível, filtros existentes (usuário, ação, entidade, data)
reorganizados visualmente, contagem de resultados, tabela com badges
de ação coloridos por significado semântico (aprovações em verde,
rejeições/desativações em vermelho, login/logout em neutro — só uma
recolorização dos valores que já existiam, nada novo), e estado vazio
diferenciando "nenhum registro" de "nenhum resultado para o filtro".
No detalhe, os campos `valor_anterior`/`valor_novo` (Fase 8) agora são
decodificados e exibidos lado a lado como "Antes"/"Depois" —
reaproveitando os mesmos filtros de template (`from_json`,
`campos_visiveis`, `rotulo_campo`) já criados na Stage 3 para o mesmo
formato de dado em `Alteracao.dados_novos`. **Nenhuma paginação foi
adicionada** (não existia antes) e **nenhum dado foi inventado**.

**Componentes reutilizados:** os mesmos de sempre
(`.oris-page-header`, `.oris-panel`, `.oris-empty-state`,
`.oris-detail-grid`, `.oris-back-link`) — só um pequeno utilitário
CSS novo (`.oris-detail-grid-full`, para a descrição ocupar a largura
toda) foi acrescentado ao Design System existente.

**Screenshots:** `auditoria-desktop.png` (com os registros reais do
ambiente de desenvolvimento) e `auditoria-detalhe-desktop.png`
(mostrando uma alteração de perfil real, com Antes/Depois), em
`docs/screenshots/`.

## UX/UI Final — Stages 5, 6 e 7: Importação, Usuários, Privacidade e Login (FASE 13B)

Encerra a aplicação do Design System nas telas de negócio existentes:
**Stage 5** (as 5 telas do fluxo de importação — início, upload,
mapeamento, validação e prévia), **Stage 6** (listagem e formulário
de Administração de Usuários) e **Stage 7** (Login, `/privacidade` e
a página de erro 403). As três foram feitas em sequência, com um
checkpoint de testes e validação MySQL real entre cada uma.

**Importação (Stage 5):** cabeçalho de página, área de upload com
destaque visual (`.oris-upload-area`, um novo utilitário simples do
Design System), tabela de mapeamento mostrando claramente
coluna da planilha → campo do ORIS, indicadores de
total/válidos/com erros na validação, e total/novos/alterados/sem
alteração na prévia. **O fluxo em si não mudou** — upload → mapeamento
→ validação → prévia → confirmação → pendente → aprovação → aplicação,
validado de ponta a ponta com MySQL real.

**Usuários (Stage 6):** mesma hierarquia das demais telas
administrativas, com um badge de cor própria para cada perfil
(ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL, GESTOR).
RBAC (só ADMINISTRADOR acessa), proteção do último administrador e
segurança de senha (bcrypt, nunca exibida) — tudo confirmado
inalterado.

**Privacidade e Login (Stage 7):** a tela de login ganhou uma
identidade visual mais institucional (um selo circular com o
gradiente da marca), mantendo exatamente o mesmo formulário e
comportamento (bcrypt, sessão, rate limiting, CSRF, bloqueio de
usuário inativo). A página `/privacidade` foi reorganizada em painéis
temáticos — **todo o conteúdo textual foi preservado palavra por
palavra**, nada foi adicionado ou reescrito. A tela de erro 403
(`acesso_negado.html`) ganhou a mesma identidade visual das demais
páginas internas.

**Componentes reutilizados:** os mesmos de sempre
(`.oris-page-header`, `.oris-panel`, `.oris-empty-state`,
`.oris-stat-strip`, `.oris-back-link`) — só dois utilitários novos e
pequenos: `.oris-upload-area` (Stage 5) e `.oris-login-logo`/
`.oris-login-row` (Stage 7).

**Screenshots:** `importacao-desktop.png`, `importacao-mobile.png`,
`importacao-mapeamento-desktop.png`, `importacao-validacao-desktop.png`,
`importacao-previa-desktop.png`, `usuarios-desktop.png`,
`usuarios-mobile.png`, `usuario-form-desktop.png`, `login-desktop.png`,
`login-mobile.png`, `privacidade-desktop.png`,
`acesso-negado-desktop.png`, em `docs/screenshots/`.

## Redesign Premium da Importação

Uma segunda passada visual, só sobre as 5 telas de Importação
(`index`, `nova`, `mapeamento`, `validacao_erros`, `previa`),
elevando o acabamento visual para um padrão "Health-Tech/Gov-Tech
premium" — glassmorphism sutil, gradiente navy → petróleo → turquesa,
profundidade e microinterações discretas, sem neon, sem glow
exagerado e sem excesso de efeitos 3D.

**O que mudou:** um novo arquivo,
`app/static/css/importacao-premium.css`, carregado **somente** nessas
5 telas (via `{% block extra_css %}`) — nenhuma outra tela do sistema
é afetada. Construído inteiramente sobre os tokens já existentes em
`tokens.css` (nenhuma cor nova foi inventada): hero com gradiente
navy→petróleo→turquesa e um elemento gráfico discreto de
conectividade; cards de entidade em vidro fosco
(`backdrop-filter: blur`) com uma fina borda gradiente no topo e
elevação sutil ao passar o mouse; área de upload com borda tracejada
e ícone circular em gradiente; linhas de mapeamento como "chips"
fluidos em vez de uma tabela rígida; indicadores com uma barra de cor
semântica sutil.

**O que NÃO mudou:** nenhuma rota, nenhuma variável de template,
nenhum `name` de campo de formulário, nenhuma regra de negócio,
validação, RBAC, CSRF, auditoria ou fluxo de aprovação — só a camada
visual, confirmado pelos 32 testes de importação existentes passando
sem nenhuma alteração.

**Achado corrigido durante a validação visual:** o ícone circular da
área de upload usava `display: inline-flex` com `margin: 0 auto`, que
não centraliza de forma confiável (a técnica de `margin: auto` exige
um elemento de nível de bloco) — corrigido para `display: flex`.

**Screenshots:** `importacao-index-premium.png`,
`importacao-nova-premium.png`, `importacao-mapeamento-premium.png`,
`importacao-validacao-premium.png`, `importacao-previa-premium.png`,
em `docs/screenshots/`.

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

Até o momento (FASE 12) — ver também o relatório completo em
[`docs/SEGURANCA.md`](docs/SEGURANCA.md):

- Nenhuma credencial sensível fica hardcoded no código — tudo vem do `.env`
  via `python-dotenv`.
- `.env` está no `.gitignore` para nunca ser versionado.
- Conexão com o MySQL configurada via SQLAlchemy com usuário de banco
  dedicado (privilégio mínimo, sem usar o `root`).
- Senhas nunca são armazenadas em texto puro — apenas o hash bcrypt
  (biblioteca `bcrypt`), gerado com salt aleatório a cada chamada —
  também na criação e na redefinição administrativa (Fase 11).
- Sessão do Flask guarda apenas `usuario_id` e `autenticado` — nunca a
  senha ou o hash. `session.clear()` no login e no logout mitiga
  session fixation.
- Cookies de sessão com `HttpOnly` e `SameSite=Lax` (e `Secure` em
  produção); `SECRET_KEY` sempre lida do `.env`.
- `CSRFProtect` inicializado globalmente (Fase 10) — cobre tanto os
  formulários baseados em `FlaskForm` quanto as telas do importador,
  que usam formulários simples com campos dinâmicos por entidade.
- **Headers HTTP de segurança** em toda resposta (Fase 12):
  `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` e uma
  `Content-Security-Policy` básica.
- **Rate limiting leve de login** (Fase 12): bloqueia temporariamente
  após 5 tentativas malsucedidas para o mesmo (IP, email) em 5 minutos.
- **Página de erro 500 dedicada** (Fase 12): nenhum erro inesperado
  expõe stack trace, SQL ou caminhos internos.
- Mensagem de erro de login sempre genérica ("Email ou senha inválidos."),
  sem revelar se o email existe, se a senha está errada ou se a conta
  está inativa.
- Controle de acesso por perfil (RBAC) verificado sempre no backend
  (`roles_required`), nunca apenas escondendo links/botões na interface.
  A Administração de Usuários (Fase 11) é exclusiva do ADMINISTRADOR.
- Um usuário desativado perde o acesso imediatamente a **qualquer**
  área protegida, mesmo com uma sessão antiga ainda "logada" — desde
  a Fase 11, essa checagem vale tanto para rotas com perfil específico
  quanto para as que só exigem estar autenticado.
- Proteção contra o sistema ficar sem nenhum ADMINISTRADOR ativo: não
  é possível desativar nem trocar o perfil do último administrador
  ativo (Fase 11).
- Segregação de funções real: criar/editar/alterar situação de Unidade,
  Serviço e Equipamento (manualmente ou via importação de planilha)
  passa a exigir aprovação de um ADMINISTRADOR ou GESTAO_INFORMACAO —
  e nunca do próprio solicitante, verificado sempre no backend
  (`app/services/alteracoes_service.py`), nunca só na interface.
- Aprovação e aplicação da mudança acontecem na mesma transação: se a
  aplicação falhar (ex.: conflito de CNES), nada é salvo e a alteração
  continua PENDENTE — nenhuma auditoria falsa é gerada em um rollback.
- Auditoria funcional e protegida: login/logout, solicitação, aprovação,
  rejeição, a mudança efetivamente aplicada e toda a administração de
  usuários (criação, edição, ativação/desativação, troca de perfil,
  redefinição de senha) geram registros rastreáveis (quem, quando, o
  quê, valores antes/depois quando aplicável) — nunca senha ou hash. A
  auditoria é somente leitura: não existe rota de edição ou exclusão
  pela aplicação, e só ADMINISTRADOR/GESTAO_INFORMACAO podem consultá-la.
- O Dashboard reaproveita essa mesma restrição: a seção "Atividade
  recente" só mostra o histórico completo para ADMINISTRADOR/
  GESTAO_INFORMACAO — RESPONSAVEL_SAUDE_BUCAL e GESTOR veem apenas a
  própria atividade, nunca a de outros usuários.
- Upload de planilhas com extensão validada, tamanho e número de
  linhas limitados, nome de arquivo gerado pelo servidor (nunca o do
  usuário), armazenamento temporário fora de `static`/`templates`, e
  remoção do arquivo assim que deixa de ser necessário — sem exposição
  de caminhos internos em mensagens de erro.
- Páginas dedicadas de "Acesso negado" (HTTP 403) e "Não encontrado"
  (HTTP 404), sem expor detalhes internos do sistema (ex.: erro de
  banco de dados) para o usuário.
- Todo acesso ao banco passa pelo ORM (SQLAlchemy), sem SQL manual —
  proteção nativa contra SQL Injection; revisado e confirmado na
  Fase 12.
- Autoescape do Jinja nunca desativado e nenhum uso de `|safe` com
  dados de usuário em nenhum template — proteção contra XSS revisada
  e confirmada na Fase 12.
- Unicidade de CNES e de email de usuário validada tanto na aplicação
  (mensagem amigável) quanto no banco (constraint), cobrindo também
  condições de corrida.
- Integridade referencial de Serviços/Equipamentos validada no
  backend: unidade sempre precisa existir, e um equipamento nunca pode
  ser associado a um serviço de outra unidade — inclusive quando os
  dados vêm de uma planilha importada.
- Nenhuma exclusão física de usuário existe em nenhuma rota — apenas
  ativação/desativação, preservando histórico e auditoria.
- Página `/privacidade` (Fase 12) documentando finalidade, categorias
  de dados tratados, controles de segurança e retenção — sem afirmar
  conformidade legal absoluta nem inventar informações institucionais.

Limitações conhecidas (dependem do ambiente de produção): HTTPS/TLS
real depende do servidor/proxy de implantação; o rate limiting é em
memória por processo (não distribuído); a Content-Security-Policy usa
`unsafe-inline` por causa de pequenos handlers JS inline nos filtros
de listagem — ver detalhes em `docs/SEGURANCA.md`.

## Roadmap de fases

- [x] FASE 1 — Estrutura do projeto, ambiente, Flask, MySQL
- [x] FASE 2 — Banco de dados, models, usuários, perfis
- [x] FASE 3 — Login, bcrypt, sessão, logout
- [x] FASE 4 — RBAC e gerenciamento de acesso
- [x] FASE 5 — CRUD de Unidades
- [x] FASE 6 — CRUD de Serviços e Equipamentos
- [x] FASE 7 — Fluxo de alterações e aprovação
- [x] FASE 8 — Auditoria e rastreabilidade
- [x] FASE 9 — Dashboard
- [x] FASE 10 — Importador de Planilhas (.xlsx/.csv)
- [x] FASE 11 — Administração de Usuários
- [x] FASE 12 — Segurança, LGPD e Proteção de Dados
- [x] FASE 13A — Design System e Identidade Visual
- [x] FASE 13B — Etapa 1: Estrutura Global (sidebar/header) + Dashboard
- [x] FASE 13B — Stage 2A: UX/UI de Unidades de Saúde
- [x] FASE 13B — Stage 2B: UX/UI de Serviços e Equipamentos
- [x] FASE 13B — Stage 3: UX/UI do Módulo de Aprovações
- [x] FASE 13B — Stage 4: UX/UI da tela de Auditoria
- [x] FASE 13B — Stages 5, 6, 7: UX/UI de Importação, Usuários,
      Privacidade e Login
- [ ] Próximas fases — polimento final e revisão visual geral

## Dados de demonstração

⚠️ Todos os dados de unidades, serviços, equipamentos e usuários utilizados
neste projeto são **fictícios**, criados exclusivamente para fins de
demonstração acadêmica. Nenhum dado real de paciente é utilizado ou
armazenado pelo sistema.
