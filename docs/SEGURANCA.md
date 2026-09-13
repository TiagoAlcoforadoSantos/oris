# ORIS — Relatório de Segurança (Fase 12)

Este documento registra a auditoria técnica de segurança realizada no
projeto ORIS ao final da Fase 11, os achados encontrados, o que foi
corrigido, e as recomendações que ficam como melhoria futura (fora do
escopo deste projeto acadêmico).

> Este relatório reflete uma revisão feita por quem desenvolveu o
> projeto, com o apoio de uma IA, sobre o próprio código-fonte. Não
> substitui um pentest profissional nem uma auditoria de terceiros.

## Metodologia

A auditoria revisou, sistematicamente, cada rota da aplicação
(`app/routes/`), os models (`app/models/`), os serviços
(`app/services/`), os templates (`app/templates/`), a configuração
(`config.py`, `.env.example`, `.gitignore`) e as dependências
(`requirements.txt`), cobrindo: autenticação, RBAC, IDOR, CSRF, XSS,
SQL Injection, upload de planilhas, auditoria/integridade,
administração de usuários, fluxo de importação + aprovação,
validação de entrada, tratamento de erros, secrets e dependências.

## Achados

| ID | Achado | Severidade | Situação |
|----|--------|------------|----------|
| SEC-001 | `CSRFProtect` não estava registrado globalmente — `{{ csrf_token() }}` usado sem `FlaskForm` em `alteracoes/lista.html` quebrava a página para um aprovador real vendo alterações de outra pessoa | ALTO | Corrigido na Fase 10 |
| SEC-002 | `login_required` não reverificava se o usuário continuava ativo a cada requisição (só `roles_required` fazia isso) — uma sessão antiga de usuário desativado ainda acessava telas de só-consulta | MÉDIO | Corrigido na Fase 11 |
| SEC-003 | Nenhum header HTTP de segurança nas respostas (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`) | MÉDIO | **Corrigido nesta fase** |
| SEC-004 | Sem página de erro 500 amigável — em caso de erro inesperado sem `errorhandler`, o Flask usaria a página padrão do Werkzeug | BAIXO | **Corrigido nesta fase** |
| SEC-005 | Nenhuma proteção contra tentativas repetidas de login (força bruta) | MÉDIO | **Corrigido nesta fase** (rate limiting leve, em memória, sem Redis) |
| SEC-006 | Nenhuma página de transparência/privacidade documentando finalidade, dados tratados e retenção | INFORMATIVO (LGPD) | **Corrigido nesta fase** (`/privacidade`) |
| SEC-007 | `cryptography` presente no `requirements.txt` sem import direto no código da aplicação | INFORMATIVO | Documentado — é dependência transitiva legítima do `PyMySQL` para o método de autenticação padrão do MySQL 8 (`caching_sha2_password`); sem ela, a conexão ao MySQL real falha. Mantida. |
| SEC-008 | O sistema aceita upload de CSV/XLSX — risco teórico de *formula injection* (`=`, `+`, `-`, `@`) se esses dados fossem depois reexportados para planilha | INFORMATIVO | Não aplicável: o ORIS **só lê** planilhas enviadas pelo usuário; nunca gera um arquivo de download contendo dados vindos de fora (o único CSV gerado — o modelo de importação — tem apenas cabeçalhos fixos, sem dados de banco ou de terceiros). Documentado como limitação/não-funcionalidade, não implementada proteção desnecessária. |
| — | RBAC de todas as rotas (`/usuarios`, `/auditoria`, `/alteracoes`, `/unidades`, `/servicos`, `/equipamentos`, `/importacao`, `/dashboard`) | — | Revisado — todas as rotas mutáveis usam `roles_required` com o(s) perfil(is) corretos; nenhuma rota depende só de esconder o link do menu |
| — | IDOR (acesso a registros por ID) | — | Revisado — todo endpoint com `<id>` usa um `_buscar_..._ou_404`, retornando 404 para inexistente e 403 (via RBAC) para quem não tem permissão; o ORIS não tem modelo de "dono do registro", então não há isolamento por usuário a criar |
| — | XSS | — | Revisado — nenhum uso de `\|safe` ou `Markup()` com dados de usuário em nenhum template; autoescape do Jinja nunca foi desativado |
| — | SQL Injection | — | Revisado — nenhuma consulta SQL manual/concatenada em todo o projeto; 100% via SQLAlchemy ORM |
| — | Secrets no código/histórico do projeto | — | Revisado — `.env` nunca foi commitado (confirmado via `git log`), `.env.example` só tem placeholders, nenhuma senha real ou token está no código-fonte ou nos testes |

### Nota sobre um achado fora do código-fonte

Durante o desenvolvimento deste projeto (fora do escopo desta
auditoria de código), um token de acesso do GitHub foi colado
diretamente na conversa com a IA em várias ocasiões, para viabilizar
o `git push`. Esse token **nunca foi salvo no repositório** (era
removido da configuração local do Git logo após o uso), mas ficou
exposto no histórico da conversa. Isso já foi sinalizado
repetidamente durante o desenvolvimento, recomendando a revogação do
token — reforça-se aqui essa recomendação, caso ainda não tenha sido
feita.

## Controles implementados

- **Autenticação:** login/logout, bcrypt (salt gerenciado
  automaticamente pela biblioteca), usuário inativo bloqueado no
  login e em qualquer área protegida, mensagem de erro genérica,
  rate limiting leve por (IP, email).
- **RBAC:** decorators `login_required`/`roles_required`, sempre
  verificados no backend, nunca só na interface.
- **CSRF:** `CSRFProtect` global, cobrindo tanto formulários
  `FlaskForm` quanto os formulários simples do importador.
- **Auditoria:** somente leitura (sem rota de edição/exclusão),
  acesso restrito a ADMINISTRADOR/GESTAO_INFORMACAO, nunca registra
  senha/hash, viaja na mesma transação da operação que descreve.
- **Validação de entrada:** todos os formulários e a leitura de
  planilhas validam no backend (campos obrigatórios, formato de CNES,
  UF, enumerações de situação, existência de relacionamentos) — nunca
  dependem só da validação HTML do navegador.
- **Upload seguro:** extensão validada contra lista fechada, tamanho
  e número de linhas limitados, nome de arquivo gerado pelo servidor,
  pasta temporária dedicada, remoção do arquivo após uso, mensagens
  de erro que nunca expõem caminhos internos.
- **Sessão:** cookies `HttpOnly`, `SameSite=Lax`, `Secure` em
  produção; `session.clear()` no login (mitiga session fixation) e no
  logout.
- **Headers HTTP:** `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy` e uma `Content-Security-Policy` básica em toda
  resposta.
- **Proteção de secrets:** `SECRET_KEY` e credenciais de banco vêm do
  `.env` (nunca hardcoded, nunca versionado).
- **LGPD/proteção de dados:** ver seção correspondente no
  `README.md` — finalidade, minimização, retenção e página de
  transparência (`/privacidade`).

## Limitações conhecidas (dependem do ambiente de produção)

- **HTTPS/TLS:** o código já está preparado (`SESSION_COOKIE_SECURE`
  fica `True` em `ProductionConfig`), mas o ambiente de execução real
  (servidor web, proxy reverso, certificado) precisa fornecer TLS —
  isso está fora do que uma aplicação Flask sozinha controla.
- **Rate limiting:** a implementação atual é em memória, por
  processo — não é compartilhada entre múltiplos processos/workers
  nem sobrevive a um restart. Para produção com múltiplos workers,
  recomenda-se um backend compartilhado (ex.: Redis) — deliberadamente
  fora do escopo desta fase.
- **Content-Security-Policy com `unsafe-inline`:** vários templates
  usam pequenos handlers inline (`onchange="this.form.submit()"`) em
  filtros de listagem. Uma CSP realmente restrita exigiria mover esse
  JavaScript para arquivos `.js` próprios — planejado para a futura
  fase de UX/UI, não feito agora para não redesenhar templates fora
  do escopo desta fase.
- **DEBUG em produção:** o código já diferencia `DevelopmentConfig`
  (`DEBUG=True`) de `ProductionConfig` (`DEBUG=False`); cabe a quem
  fizer o deploy garantir que `FLASK_ENV=production` seja usado de
  fato no ambiente real.
- **Dependências:** nenhuma foi identificada como não utilizada ou
  duplicada; nenhuma atualização de versão foi considerada
  criticamente necessária para esta fase — evitou-se atualizar
  indiscriminadamente para não correr o risco de quebrar o projeto
  por mudanças incompatíveis sem necessidade concreta.
