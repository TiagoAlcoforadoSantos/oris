# ORIS na AWS (EC2 + Docker + HTTPS)

Arquitetura: internet -> **Caddy** (80/443, HTTPS Let's Encrypt, HSTS) -> **app** (gunicorn, só na rede interna) -> **MySQL 8** (só na rede interna, volume em disco EBS criptografado). O servidor usa o `LabInstanceProfile` para falar com o S3, sem chave de acesso em arquivo.

## Servidor (Ubuntu 24.04, t3.medium, IP elástico)

```bash
sudo apt-get update && sudo apt-get install -y git docker.io docker-compose-v2
sudo systemctl enable --now docker
git clone --branch iago-etapa11-seguranca https://github.com/figueiroaiago-dev-cs/oris.git
cd oris
```

## Segredos (`.env.aws`, nunca vai para o Git)

```bash
cat > .env.aws <<EOT
ORIS_DOMAIN=54-174-10-29.sslip.io
DB_PASSWORD=$(openssl rand -hex 16)
DB_ROOT_PASSWORD=$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)
DATA_ENCRYPTION_KEY=$(python3 -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())")
ORIS_DEMO_SENHA=<escolha uma senha forte para os usuários de demonstração>
EOT
chmod 600 .env.aws
```

## Subir

```bash
sudo docker compose -f docker-compose.aws.yml --env-file .env.aws up -d --build
sudo docker compose -f docker-compose.aws.yml ps
sudo docker compose -f docker-compose.aws.yml logs app | tail
```

Abrir `https://<ORIS_DOMAIN>`. A primeira emissão do certificado leva ~1 minuto e exige as portas 80 e 443 abertas no security group.

## Cuidados

- **`DATA_ENCRYPTION_KEY` é obrigatória** desde a criptografia de dados (uploads e alterações pendentes). Num servidor já implantado, antes do `git pull` + `up -d --build`, acrescente-a ao `.env.aws` (comando da seção "Segredos") e **guarde uma cópia segura**: trocar ou perder a chave torna ilegíveis os dados já cifrados. Sem ela o `docker compose` recusa subir, com a mensagem "defina DATA_ENCRYPTION_KEY".

- O **Learner Lab desliga o servidor** ao fim da sessão (~4 h). Ao religar, o IP elástico e os dados continuam; os contêineres sobem sozinhos (`restart: unless-stopped`).
- Os usuários `@oris.example` usam a senha de `ORIS_DEMO_SENHA`, nunca a do repositório.
- O SSH foi restringido ao serviço EC2 Instance Connect; se a conexão pelo navegador deixar de funcionar, confira a faixa de IP da região na documentação da AWS.

## Validação da implantação (10/11/2026)

- Contêineres `db` (healthy), `app` (healthy) e `caddy` em execução; certificado Let's Encrypt emitido.
- HTTPS com HSTS; senha pública dos usuários demo recusada; login falho registrado na auditoria.
- S3: bucket privado com versionamento e SSE-S3; exportação pelo ORIS gerou URL pré-assinada; acesso direto ao objeto retornou `AccessDenied`.
- LDAP real: `sincronizar-ldap` criou 4 usuários e a repetição não alterou nada. OIDC real: login SSO como ADMINISTRADOR e GESTOR contra o Keycloak.
- Religamento testado (End Lab -> Start Lab): o servidor voltou em ~3 min, com dados preservados e SSO funcionando. Ligar o lab ~10 min antes de apresentar.
- SSH restrito à faixa do EC2 Instance Connect (18.206.107.24/29); HTTP/HTTPS abertos ao mundo; banco, LDAP e Keycloak sem porta pública.
- Disco EBS criptografado (confirmado no console).

## LDAP e OIDC reais (Requisito 3 do professor)

Acrescenta **OpenLDAP** (STARTTLS com certificado de uma CA própria; a app valida o certificado) e **Keycloak** (OIDC com Authorization Code + PKCE, emissor em `https://kc.<dominio>/realms/oris`, console admin bloqueado na internet). No LDAP, o ORIS só **sincroniza** usuários e grupos para as tabelas locais; o **login** de pessoas do diretório é pelo OIDC.

```bash
cd ~/oris && git pull
sh docker/ldap/gerar-certs.sh docker/ldap/certs
printf 'LDAP_ADMIN_PASSWORD=%s\nKC_ADMIN_PASSWORD=%s\nOIDC_CLIENT_SECRET=%s\n' "$(openssl rand -hex 16)" "$(openssl rand -hex 16)" "$(openssl rand -hex 24)" >> .env.aws
set -a; . ./.env.aws; set +a; python3 docker/keycloak/gerar-realm.py
sudo docker compose -f docker-compose.aws.yml -f docker-compose.idp.yml --env-file .env.aws up -d --build
```

Sincronizar o LDAP e conferir:

```bash
sudo docker compose -f docker-compose.aws.yml -f docker-compose.idp.yml --env-file .env.aws exec app flask --app run sincronizar-ldap --simular
sudo docker compose -f docker-compose.aws.yml -f docker-compose.idp.yml --env-file .env.aws exec app flask --app run sincronizar-ldap
```

Login OIDC: na tela de login, o botão de login institucional leva ao Keycloak (`oidc.admin@oris.example`, `oidc.gestao`, `oidc.saude`, `oidc.gestor`, todos com a senha `ORIS_DEMO_SENHA`; `oidc.semgrupo` deve ser **negado**).

Validação do LDAP: o `sincronizar-ldap` foi executado contra um OpenLDAP 2.5 real (STARTTLS + CA própria): 4 usuários criados com o perfil do grupo, 1 sem grupo ignorado, 2ª execução sem alterações, CA errada recusada, conexão sem TLS recusada.

### Usuários do LDAP entrando pelo SSO (federação LDAP no Keycloak)

O Keycloak lê o OpenLDAP (federação, **somente leitura**, STARTTLS validando a CA do laboratório). Assim quem está no LDAP (`ana.admin`, `bruno.gestao`, `carla.saude`, `davi.gestor`) entra pelo botão de login institucional **com a senha do LDAP**, e o ORIS reconhece que é a **mesma conta** criada pela `sincronizar-ldap` (claim `ldap_uid`, emitida só para usuários federados). `eva.semgrupo` continua **negada**.

Para aplicar num servidor que já está no ar (o Keycloak só importa o realm quando é criado do zero; ele não tem volume de dados, então recriar o contêiner basta):

```bash
cd ~/oris && git pull
set -a; . ./.env.aws; set +a
python3 docker/keycloak/gerar-realm.py          # agora inclui a federação com o LDAP
sudo docker compose -f docker-compose.aws.yml -f docker-compose.idp.yml --env-file .env.aws up -d --build --force-recreate keycloak app
sh docker/ldap/definir-senhas.sh                 # senha dos usuários do LDAP = ORIS_DEMO_SENHA
```

Conferir: entrar pelo SSO como `ana.admin` (perfil ADMINISTRADOR, origem LDAP na tela de usuários) e como `eva.semgrupo` (negado). Rodar `sincronizar-ldap` de novo não cria conta duplicada.

**Não testado ainda em servidor real** (escrito sem acesso à AWS): se o Keycloak não subir, veja `docker compose logs keycloak` (o mais provável é o certificado do LDAP ou o caminho do truststore).
