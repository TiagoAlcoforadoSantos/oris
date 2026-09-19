# ORIS — Plataforma de Governança da Rede de Saúde Bucal

Projeto acadêmico desenvolvido no CESAR School, para a Secretaria de
Saúde do Recife.

## Sobre o projeto

O ORIS é um sistema web que centraliza o cadastro e a governança das
informações de **Unidades de Saúde Bucal**, seus **Serviços** e
**Equipamentos**, resolvendo o problema da fragmentação dessas
informações entre o CNES e planilhas paralelas mantidas manualmente —
o que hoje dificulta a governança, a auditoria e a tomada de decisão
sobre a rede.

## Objetivo

Oferecer uma plataforma web centralizada, segura e auditável para
cadastro, validação e aprovação de alterações relacionadas a
unidades, serviços e equipamentos de Saúde Bucal, preparada para uma
futura integração com o CNES.

## Escopo

**Dentro do escopo do MVP:**

- Cadastro de Unidades de Saúde Bucal, Serviços e Equipamentos
- Login e gestão de acesso por perfil (RBAC)
- Fluxo de solicitação e aprovação de alterações
- Auditoria (audit log) de toda ação relevante
- Dashboard com indicadores da rede
- Importação de dados via planilha (.xlsx/.csv)
- Administração de usuários

**Fora do escopo:** prontuário de pacientes, sistema hospitalar,
laudos ou qualquer módulo assistencial ao paciente. Nenhum dado
clínico ou de paciente é tratado pelo sistema.

## Funcionalidades

### Unidades, Serviços e Equipamentos

CRUD completo das três entidades centrais do sistema. Nenhuma
exclusão física é feita em nenhuma delas — apenas alteração de
situação (`ATIVA`/`INATIVA`/`MANUTENCAO` para Unidades,
`ATIVO`/`INATIVO` para Serviços e Equipamentos), preservando o
histórico.

| Rota                          | Método    | Quem acessa                                              |
|-------------------------------|-----------|-----------------------------------------------------------|
| `/unidades`, `/unidades/<id>` | GET       | Qualquer usuário autenticado (inclusive GESTOR)            |
| `/unidades/nova`, `/unidades/<id>/editar`, `/unidades/<id>/situacao` | GET/POST | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL |
| `/servicos`, `/servicos/<id>`, `/equipamentos`, `/equipamentos/<id>` | GET | Qualquer usuário autenticado (inclusive GESTOR) |
| `/servicos/novo`, `/servicos/<id>/editar`, `/servicos/<id>/situacao`, `/equipamentos/novo`, `/equipamentos/<id>/editar`, `/equipamentos/<id>/situacao` | GET/POST | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL |

GESTOR nunca altera dados — só consulta, em qualquer entidade. A
interface esconde os botões de quem não tem permissão por
usabilidade, mas a proteção de verdade está sempre no backend, via
`roles_required`.

**Validações principais:** nome, CNES, tipo, cidade e UF são
obrigatórios para Unidade (CNES numérico, de 7 a 15 dígitos); um
Equipamento associado a um Serviço precisa ter o Serviço pertencendo
à mesma Unidade selecionada; registro inexistente retorna a página
"404 — Não encontrado".

### Dashboard

`/dashboard` reúne uma visão geral da rede, com dados calculados
direto do banco (`app/services/dashboard_service.py`) — total,
ativas, inativas e em manutenção de Unidades; totais de Serviços e
Equipamentos; alterações pendentes/aprovadas/rejeitadas; listagem da
rede com filtro por situação; e um resumo da atividade recente
(auditoria), com visibilidade ajustada por perfil. Acessível aos 4
perfis.

### Administração de usuários

Módulo exclusivo do `ADMINISTRADOR` (`/usuarios`) para criar, editar,
ativar/desativar e redefinir a senha de usuários. Nenhuma exclusão
física de usuário existe — apenas ativação/desativação. O sistema
nunca permite que o último `ADMINISTRADOR` ativo seja desativado ou
tenha o perfil alterado, para que a aplicação nunca fique sem
nenhum administrador. Toda ação gera um registro de auditoria
próprio (`CRIAR_USUARIO`, `EDITAR_USUARIO`, `ATIVAR_USUARIO`,
`DESATIVAR_USUARIO`, `ALTERAR_PERFIL`, `REDEFINIR_SENHA`).

### Página de transparência (LGPD)

`/privacidade` é uma página pública (sem exigir login) que documenta
a finalidade do sistema, as categorias de dados tratados, quem tem
acesso e a política de retenção — ver a seção "Segurança e LGPD"
abaixo.

## Arquitetura

- **Padrão de acesso a dados:** SQLAlchemy ORM, sem nenhuma consulta
  SQL manual ou concatenada em todo o projeto.
- **Controle de acesso:** decorators `login_required`/
  `roles_required` (`app/utils/decorators.py`), sempre verificados no
  backend — a interface só esconde botões/links por conveniência,
  nunca é a única proteção.
- **Camada de serviços:** regras de negócio que cruzam mais de uma
  entidade (aprovação de alterações, auditoria, dashboard,
  importação) ficam em `app/services/`, não nas rotas.
- **Fluxo de aprovação como padrão central:** criar, editar ou alterar
  a situação de uma Unidade, Serviço ou Equipamento nunca grava
  direto no banco — sempre passa por uma `Alteracao` pendente (ver
  "Fluxo de aprovação" abaixo). O mesmo vale para a importação de
  planilhas.

**Modelo de dados (tabelas principais):**

| Tabela        | Descrição                                                              |
|---------------|--------------------------------------------------------------------------|
| `usuarios`    | Usuários do sistema (nome, email único, senha_hash, perfil, ativo)       |
| `unidades`    | Unidades de Saúde Bucal (nome, CNES, endereço, situação, `unidade_e_mista`) |
| `servicos`    | Serviços de Saúde Bucal (podem existir sem Unidade associada)            |
| `equipamentos`| Equipamentos (podem existir sem Unidade e/ou sem Serviço associados)     |
| `alteracoes`  | Fluxo de aprovação (solicitante, aprovador, operação, dados novos)       |
| `auditorias`  | Trilha de auditoria — quem fez o quê e quando, somente leitura           |

O CNES **não é um identificador único** no modelo atual — reflete o
modelo real da rede, em que uma mesma unidade mista pode aparecer sob
o mesmo CNES em mais de um registro; o campo `unidade_e_mista`
sinaliza esse caso. O CNES `9999999` é usado como convenção para
registros sem CNES real.

Nenhum dado de paciente, prontuário ou informação clínica é
armazenado — fora do escopo do MVP do ORIS.

## Tecnologias utilizadas

- **Backend:** Python 3 + Flask
- **Banco de dados:** MySQL (SQLAlchemy como ORM)
- **Frontend:** HTML, CSS, Bootstrap, JavaScript
- **Segurança:** bcrypt (hash de senha), sessões do Flask, controle
  de acesso baseado em perfil, `.env` para configurações sensíveis,
  `CSRFProtect` global
- **Planilhas:** `pandas` + `openpyxl` (leitura de `.xlsx`/`.csv` no
  importador)

## Segurança e LGPD

O relatório técnico completo — achados, severidade, o que foi
corrigido e as limitações que dependem do ambiente de produção —
está em [`docs/SEGURANCA.md`](docs/SEGURANCA.md). Resumo dos
controles implementados:

- Nenhuma credencial sensível fica hardcoded — tudo vem do `.env`
  (fora do controle de versão).
- Senhas nunca são armazenadas em texto puro — apenas hash bcrypt com
  salt aleatório, também na redefinição administrativa.
- Sessão guarda apenas `usuario_id` e `autenticado`; cookies
  `HttpOnly`, `SameSite=Lax` (e `Secure` em produção);
  `session.clear()` no login e no logout mitiga session fixation.
- `CSRFProtect` inicializado globalmente, cobrindo tanto os
  formulários `FlaskForm` quanto as telas do importador.
- Headers HTTP de segurança em toda resposta
  (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
  `Content-Security-Policy` básica).
- Rate limiting leve de login (em memória, por processo): bloqueia
  temporariamente após 5 tentativas malsucedidas para o mesmo (IP,
  email) em 5 minutos.
- Página de erro 500 dedicada — nenhum erro inesperado expõe stack
  trace, SQL ou caminhos internos.
- RBAC sempre verificado no backend; um usuário desativado perde
  acesso imediato a qualquer área protegida, mesmo com sessão antiga.
- Auditoria somente leitura, sem nenhuma rota de edição/exclusão.
- Todo acesso ao banco via ORM (sem SQL Injection); autoescape do
  Jinja nunca desativado e nenhum uso de `|safe` com dado de usuário
  (sem XSS); upload de planilha com extensão/tamanho/linhas
  limitados, nome de arquivo gerado pelo servidor.
- Página pública `/privacidade` documentando finalidade, dados
  tratados, controles e retenção.

**LGPD — finalidade, minimização e retenção:** os únicos dados
pessoais tratados hoje são os dos próprios usuários do sistema (nome,
email, perfil, situação) e os registros de auditoria da atividade
deles — não são coletados CPF, telefone ou endereço residencial sem
necessidade funcional direta. Usuários desativados e registros de
auditoria não são excluídos pela aplicação, preservando histórico.
Prazos específicos de retenção e descarte, assim como a base legal de
tratamento, dependem do contexto jurídico de quem opera o sistema —
o ORIS não os define nem os presume.

**Limitações conhecidas** (dependem do ambiente de produção): HTTPS/
TLS real depende do servidor/proxy de implantação; o rate limiting
não é distribuído entre múltiplos processos; a
Content-Security-Policy ainda permite pequenos handlers inline em
alguns filtros de listagem. Detalhes em `docs/SEGURANCA.md`.

> Este projeto passou por uma revisão de segurança feita por quem o
> desenvolveu, com apoio de uma IA, sobre o próprio código-fonte — não
> substitui um pentest profissional nem uma auditoria de terceiros.

## Perfis de acesso

O sistema tem 4 perfis:

1. **ADMINISTRADOR** — acesso total, gestão de usuários, acessa todas
   as áreas administrativas.
2. **GESTAO_INFORMACAO** — consulta dados, cria/edita e valida/aprova
   alterações, consulta auditoria.
3. **RESPONSAVEL_SAUDE_BUCAL** — consulta dados, cadastra/edita
   unidades, serviços e equipamentos.
4. **GESTOR** — somente leitura, em todas as áreas.

Toda rota restrita usa `roles_required(*perfis)`, que verifica sessão
autenticada, se o usuário continua ativo, e se o perfil está entre os
permitidos — devolvendo 403 ("Acesso negado") quando não está. A
página inicial só mostra, no menu, os links das áreas que o perfil
autenticado pode acessar, mas isso é só conveniência de interface; o
bloqueio de verdade está sempre no backend.

## Fluxo de aprovação

Criar, editar ou alterar a situação de uma Unidade, Serviço ou
Equipamento (manualmente ou via importação) nunca grava direto no
banco: cada ação registra uma `Alteracao` com status `PENDENTE`, que
só é aplicada quando aprovada por um usuário autorizado — nunca por
quem fez a solicitação.

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

| Rota                        | Método | Quem acessa                                             |
|------------------------------|--------|------------------------------------------------------------|
| `/alteracoes`, `/alteracoes/<id>` | GET | Qualquer usuário autenticado                          |
| `/alteracoes/<id>/aprovar`, `/alteracoes/<id>/rejeitar` | POST | ADMINISTRADOR, GESTAO_INFORMACAO (exceto o solicitante) |

A aprovação e a aplicação da mudança acontecem na mesma transação: se
a aplicação falhar (por exemplo, duas solicitações pendentes de
criação em conflito), nada é salvo e a alteração continua
`PENDENTE`, pronta para ser corrigida ou rejeitada — nenhuma
auditoria falsa é gerada nesse caso. A listagem aceita filtro por
`?status=` e por `?tabela=`.

## Auditoria

A tabela `Auditoria` registra toda ação relevante do sistema, sempre
na mesma transação da operação que descreve — se a operação sofrer
rollback, a auditoria correspondente cai junto.

**Ações registradas:** `LOGIN`, `LOGOUT`, `SOLICITAR_ALTERACAO`,
`APROVAR_ALTERACAO`, `REJEITAR_ALTERACAO`, e — só quando a alteração
é efetivamente aprovada — `CRIAR`, `EDITAR` ou `ALTERAR_SITUACAO`.
Solicitar uma mudança nunca gera, por si só, uma auditoria de
`CRIAR`/`EDITAR`/`ALTERAR_SITUACAO` enquanto está `PENDENTE`; essa só
é criada no momento em que a alteração é aprovada e aplicada. Uma
alteração rejeitada nunca gera esse tipo de registro.

`valor_anterior` e `valor_novo` guardam, em JSON, só os campos que
realmente mudaram (nunca senha ou hash). A consulta (`/auditoria`,
`/auditoria/<id>`) é restrita a `ADMINISTRADOR` e `GESTAO_INFORMACAO`.
A auditoria é somente leitura — não existe nenhuma rota de edição ou
exclusão, nem para `ADMINISTRADOR`; a única forma de um registro
existir é pelo serviço central `app/services/auditoria_service.py`,
chamado internamente pelo próprio sistema.

## Importação de dados

Importa Unidades, Serviços e Equipamentos a partir de planilhas
**.xlsx** ou **.csv**, sem nunca escrever direto nas tabelas de
negócio — cada linha nova ou alterada vira uma solicitação de
alteração comum, passando pelo mesmo fluxo de aprovação descrito
acima.

**Fluxo:** upload → leitura → mapeamento de colunas → validação →
pré-visualização → confirmação → solicitação `PENDENTE` → aprovação →
aplicação → auditoria.

| Rota                                | Método | Quem acessa                                              |
|---------------------------------------|--------|--------------------------------------------------------------|
| `/importacao`                         | GET    | Qualquer usuário autenticado (GESTOR só consulta)             |
| `/importacao/template/<entidade>`, `/importacao/nova` | GET | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL |
| `/importacao/mapear`, `/importacao/validar`, `/importacao/confirmar` | POST | ADMINISTRADOR, GESTAO_INFORMACAO, RESPONSAVEL_SAUDE_BUCAL |

**Mapeamento de colunas:** a planilha não precisa ter os mesmos nomes
de coluna do ORIS — o sistema sugere automaticamente por sinônimos
(ex.: "Código CNES", "Município", "Estado"), sempre com conferência e
correção manual antes de validar.

**Validação:** todas as linhas são validadas de uma vez; se houver
qualquer linha inválida, a planilha inteira é rejeitada (sem
importação parcial) — o resumo mostra total/válidos/com erros, com
linha, campo, valor recebido e motivo para cada erro.

**Segurança do upload:** extensão validada contra lista fechada
(`.csv`/`.xlsx`), tamanho máximo de 5 MB, até 2000 linhas por
planilha, nome de arquivo gerado pelo servidor, armazenamento em
pasta temporária dedicada (fora de `static`/`templates`), remoção do
arquivo assim que deixa de ser necessário.

Quem importa não pode aprovar a própria importação — a mesma
segregação de funções do fluxo de aprovação se aplica integralmente.
A confirmação do lote gera um registro extra de auditoria
`IMPORTAR_PLANILHA`, com um resumo de linhas novas/alteradas/sem
alteração.

## Estrutura do projeto

```
ORIS/
│
├── app/
│   ├── __init__.py           # application factory
│   ├── extensions.py         # instância do SQLAlchemy
│   ├── forms.py               # formulários (Flask-WTF)
│   ├── cli.py                  # comando `flask criar-usuario`
│   ├── routes/
│   │   ├── auth.py                  # /login, /logout
│   │   ├── main.py                  # "/" (rota protegida)
│   │   ├── areas.py                 # /admin, /gestao, /responsavel, /gestor (RBAC)
│   │   ├── unidades.py              # CRUD de Unidades (com fluxo de aprovação)
│   │   ├── servicos.py              # CRUD de Serviços (com fluxo de aprovação)
│   │   ├── equipamentos.py          # CRUD de Equipamentos (com fluxo de aprovação)
│   │   ├── alteracoes.py            # listar, visualizar, aprovar, rejeitar
│   │   ├── auditoria.py             # /auditoria (somente leitura)
│   │   ├── dashboard.py             # /dashboard
│   │   ├── importacao.py            # importador de planilhas (.xlsx/.csv)
│   │   ├── usuarios.py              # administração de usuários (só ADMINISTRADOR)
│   │   ├── privacidade.py           # /privacidade (pública)
│   │   └── design_system.py         # /design-system (referência visual, pública)
│   ├── models/
│   │   ├── enums.py                # PerfilUsuario, situações, status, TipoOperacaoAlteracao
│   │   ├── mixins.py                # TimestampMixin (created_at/updated_at)
│   │   ├── usuario.py
│   │   ├── unidade.py
│   │   ├── servico.py
│   │   ├── equipamento.py
│   │   ├── alteracao.py             # operacao, dados_novos
│   │   └── auditoria.py             # valor_anterior, valor_novo
│   ├── templates/
│   │   ├── base.html               # layout com sidebar/header
│   │   ├── login.html
│   │   ├── index.html
│   │   ├── dashboard.html
│   │   ├── area_perfil.html        # áreas de teste do RBAC
│   │   ├── acesso_negado.html      # página de erro 403
│   │   ├── nao_encontrado.html     # página de erro 404
│   │   ├── erro_interno.html       # página de erro 500
│   │   ├── privacidade.html        # transparência/LGPD
│   │   ├── design_system.html      # referência de tokens/componentes
│   │   ├── unidades/               # lista.html, form.html, detalhe.html
│   │   ├── servicos/                # mesmo padrão de unidades/
│   │   ├── equipamentos/            # mesmo padrão de unidades/
│   │   ├── alteracoes/              # lista.html, detalhe.html
│   │   ├── auditoria/               # lista.html, detalhe.html
│   │   ├── importacao/              # index, nova, mapeamento, validacao_erros, previa
│   │   └── usuarios/                # lista.html, form.html
│   ├── static/
│   │   ├── css/
│   │   │   ├── tokens.css               # variáveis de cor/tipografia/raio/sombra
│   │   │   ├── oris-design-system.css   # componentes (botões, badges...) sobre o Bootstrap
│   │   │   ├── layout.css               # sidebar/header/breadcrumb/responsividade
│   │   │   └── dashboard.css            # hero/KPI cards/timeline do Dashboard
│   │   ├── js/
│   │   └── images/
│   ├── services/
│   │   ├── alteracoes_service.py    # registrar/aplicar/aprovar/rejeitar
│   │   ├── auditoria_service.py     # registrar_auditoria
│   │   ├── dashboard_service.py     # indicadores e listagens do dashboard
│   │   └── importacao_service.py    # leitura, mapeamento e validação de planilhas
│   └── utils/
│       ├── datetime_utils.py       # helper de data/hora (UTC)
│       ├── security.py             # hash/verificação de senha (bcrypt)
│       ├── decorators.py           # login_required, roles_required
│       ├── rbac.py                  # matriz de acesso das áreas de teste
│       └── rate_limit.py           # rate limiting leve de login
│
├── docs/
│   ├── SEGURANCA.md          # relatório de auditoria de segurança
│   └── screenshots/          # capturas de tela representativas das telas principais
│
├── database/
│   ├── schema.sql            # DDL completo das tabelas (MySQL)
│   └── migrations/           # migrações não destrutivas aplicadas ao schema
│
├── tests/                     # suíte de testes automatizados (pytest)
│
├── .env.example               # modelo de configuração
├── .gitignore
├── requirements.txt
├── config.py
├── run.py
└── README.md
```

## Como executar

### Pré-requisitos

- Python 3.10+
- MySQL Server 8.x
- pip

### Instalação

```bash
cd ORIS
python -m venv venv

# Linux/Mac
source venv/bin/activate
# Windows (por padrão, o PowerShell bloqueia scripts de "autores
# desconhecidos" — se necessário, ajuste a política de execução antes)
venv\Scripts\activate

pip install -r requirements.txt
```

### Banco de dados

Crie o banco de dados e um usuário dedicado para a aplicação:

```sql
CREATE DATABASE oris_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'oris_user'@'localhost' IDENTIFIED BY 'sua_senha_aqui';
GRANT ALL PRIVILEGES ON oris_db.* TO 'oris_user'@'localhost';
FLUSH PRIVILEGES;
```

Depois, crie as tabelas de uma das duas formas:

```bash
# Opção A — via schema.sql (manual)
mysql -u root < database/schema.sql

# Opção B — via SQLAlchemy (recomendado em desenvolvimento)
python -c "from app import create_app; from app.extensions import db; app = create_app(); app.app_context().push(); db.create_all()"
```

A Opção B garante que as tabelas fiquem sempre sincronizadas com os
models em `app/models/`.

### Configuração (.env)

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

### Executando

```bash
python run.py
```

A aplicação sobe em `http://127.0.0.1:5000`. Para verificar que a
aplicação e a conexão com o banco estão funcionando:

```
GET http://127.0.0.1:5000/health
```

### Usuário de teste

Não existe usuário fixo/hardcoded no código. Para criar um usuário
(desenvolvimento ou demonstração), use o comando de CLI do Flask, que
pede a senha de forma oculta e já salva o hash bcrypt:

```bash
flask --app run.py criar-usuario
```

O comando pergunta nome completo, email, senha (duas vezes, para
confirmar) e perfil (`ADMINISTRADOR`, `GESTAO_INFORMACAO`,
`RESPONSAVEL_SAUDE_BUCAL` ou `GESTOR`).

> Evite domínios reservados para teste como `.local`, `.test` ou
> `.example` no email — a validação de formato os rejeita. Prefira
> algo como `usuario@oris.com.br`.

Crie um usuário de cada perfil para demonstrar a matriz de acesso.

## Testes

```bash
python -m pytest tests/ -v
```

## Estado atual

Todas as funcionalidades listadas no escopo do MVP estão
implementadas: autenticação, RBAC por perfil, CRUD de Unidades/
Serviços/Equipamentos, fluxo de solicitação e aprovação de
alterações, auditoria, dashboard, importação de planilhas,
administração de usuários, segurança/LGPD e identidade visual
aplicada a todas as telas.

O histórico completo de commits (`git log`) preserva a evolução do
projeto fase a fase, incluindo a etapa de design system e o redesign
visual aplicado a cada módulo.

## Observações acadêmicas

- Todos os dados de unidades, serviços, equipamentos e usuários
  utilizados neste projeto são **fictícios**, criados exclusivamente
  para fins de demonstração acadêmica. Nenhum dado real de paciente é
  utilizado ou armazenado pelo sistema.
- Este é um projeto acadêmico desenvolvido para a disciplina de
  Cybersecurity do CESAR School, em parceria com a Secretaria de
  Saúde do Recife. A revisão de segurança em `docs/SEGURANCA.md` não
  substitui um pentest profissional nem uma auditoria de terceiros.
