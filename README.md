# ORIS — Plataforma de Governança da Rede de Saúde Bucal

> ⚠️ **Status do projeto:** em desenvolvimento — FASE 3 concluída (autenticação: login, bcrypt, sessão, logout).
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
│   │   └── main.py               # "/" (rota protegida)
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
│   │   └── index.html           # página protegida provisória
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   ├── services/           # regras de negócio — próximas fases
│   └── utils/
│       ├── datetime_utils.py    # helper de data/hora (UTC)
│       ├── security.py          # hash/verificação de senha (bcrypt)
│       └── decorators.py        # login_required
│
├── database/
│   └── schema.sql           # DDL completo das tabelas (MySQL)
│
├── tests/
│   ├── test_fase1_estrutura.py
│   ├── test_fase2_models.py
│   └── test_fase3_autenticacao.py
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
  "fase": "3 - autenticacao (login, bcrypt, sessao, logout)"
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
   (comparação seria feita via bcrypt, nunca texto puro).
4. Se tudo estiver correto, cria uma sessão Flask com o mínimo necessário
   (`usuario_id` e `autenticado`) e redireciona para `/`.
5. Se qualquer verificação falhar (usuário inexistente, senha errada ou
   usuário inativo), a mensagem exibida é sempre a mesma — genérica —
   para não revelar detalhes sobre a conta.

**Logout:** limpa toda a sessão e redireciona para `/login`.

**Rota protegida:** o decorator `login_required`
(`app/utils/decorators.py`) verifica a sessão no backend antes de liberar
o acesso — a proteção nunca depende apenas da interface.

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

## Como rodar os testes

```bash
python -m pytest tests/ -v
```

## Usuários de teste

Veja a seção "Usuário de teste" acima — use `flask --app run.py criar-usuario`
para criar quantos usuários forem necessários para a demonstração.

## Perfis de usuário

O sistema terá 4 perfis:

1. **ADMINISTRADOR** — acesso total, gestão de usuários
2. **GESTAO_INFORMACAO** — valida e aprova/rejeita alterações
3. **RESPONSAVEL_SAUDE_BUCAL** — cadastra e edita unidades/serviços/equipamentos
4. **GESTOR** — apenas consulta (dashboard e visualização)

O campo `perfil` já existe em `usuarios` desde a Fase 2, mas as regras de
permissão de cada perfil (RBAC) serão implementadas na **FASE 4** — por
enquanto, qualquer usuário autenticado acessa a única rota protegida
existente (`/`).

## Segurança implementada

Até o momento (FASE 3):

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
- Proteção CSRF nativa do Flask-WTF no formulário de login.
- Mensagem de erro de login sempre genérica ("Email ou senha inválidos."),
  sem revelar se o email existe, se a senha está errada ou se a conta
  está inativa.
- A verificação de permissão da rota protegida acontece no backend
  (`login_required`), nunca apenas escondendo botões na interface.

Itens de segurança das próximas fases (RBAC completo, fluxo de aprovação,
auditoria detalhada, LGPD) serão documentados aqui conforme forem
implementados.

## Roadmap de fases

- [x] FASE 1 — Estrutura do projeto, ambiente, Flask, MySQL
- [x] FASE 2 — Banco de dados, models, usuários, perfis
- [x] FASE 3 — Login, bcrypt, sessão, logout
- [ ] FASE 4 — Gestão de acesso, proteção de rotas
- [ ] FASE 5 — Unidades
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
