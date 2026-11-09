# ============================================================
# ORIS - Instalar tudo e ligar (um unico script)
# ============================================================
# Como usar (PowerShell):
#   powershell -ExecutionPolicy Bypass -File C:\ORIS\oris\instalar-e-ligar-oris.ps1
# ou clique com o botao direito no arquivo > "Executar com o PowerShell".
#
# O que ele faz, na ordem:
#   1. Entra na pasta do projeto
#   2. Liga o MySQL (se estiver parado)
#   3. Cria o ambiente virtual (se nao existir)
#   4. Instala/atualiza as dependencias (requirements.txt)
#   5. Cria o .env a partir do .env.example (se nao existir)
#   6. Atualiza o banco (tabelas/colunas da Fase 14) - seguro repetir
#   7. Abre o navegador e sobe o servidor
#
# Para PARAR: feche a janela ou pressione Ctrl+C.
# ============================================================

$ErrorActionPreference = "Stop"
$pastaProjeto = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $pastaProjeto) { $pastaProjeto = "C:\ORIS\oris" }

function Passo($t)  { Write-Host ""; Write-Host "==> $t" -ForegroundColor Cyan }
function Ok($t)     { Write-Host "OK: $t" -ForegroundColor Green }
function Falhar($t) {
    Write-Host ""; Write-Host "ERRO: $t" -ForegroundColor Red
    Read-Host "Pressione Enter para fechar"
    exit 1
}

# ---- 1. Pasta do projeto ------------------------------------------------------
Passo "Localizando o projeto..."
if (-not (Test-Path (Join-Path $pastaProjeto "run.py"))) { Falhar "Nao achei run.py em '$pastaProjeto'." }
Set-Location $pastaProjeto
Ok $pastaProjeto

# ---- 2. MySQL -----------------------------------------------------------------
Passo "Verificando o MySQL..."
$servico = Get-Service -Name "MySQL80" -ErrorAction SilentlyContinue
if ($null -eq $servico) { Falhar "Servico 'MySQL80' nao encontrado nesta maquina." }
if ($servico.Status -ne "Running") {
    Write-Host "MySQL parado, iniciando (pode pedir permissao de Administrador)..." -ForegroundColor Yellow
    try {
        Start-Service -Name "MySQL80"
    } catch {
        Start-Process powershell.exe -ArgumentList "-Command Start-Service -Name MySQL80" -Verb RunAs -Wait
    }
    Start-Sleep -Seconds 5
}
if ((Get-Service -Name "MySQL80").Status -ne "Running") { Falhar "O MySQL nao conseguiu iniciar." }
Ok "MySQL rodando."

# ---- 3. Ambiente virtual ------------------------------------------------------
Passo "Preparando o ambiente virtual..."
$py = Join-Path $pastaProjeto "venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Criando venv..." -ForegroundColor Yellow
    python -m venv venv
    if (-not (Test-Path $py)) { Falhar "Nao consegui criar o venv. Python instalado e no PATH?" }
}
Ok "venv pronto."

# ---- 4. Dependencias ----------------------------------------------------------
Passo "Instalando dependencias (requirements.txt)..."
& $py -m pip install --disable-pip-version-check -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Falhar "Falha ao instalar as dependencias." }
Ok "Dependencias instaladas."

# ---- 5. .env ------------------------------------------------------------------
Passo "Conferindo o arquivo .env..."
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Criei o .env a partir do .env.example." -ForegroundColor Yellow
        Write-Host "EDITE o .env (DB_PASSWORD e SECRET_KEY) e rode este script de novo." -ForegroundColor Yellow
        Start-Process notepad.exe ".env"
        Read-Host "Pressione Enter para fechar"
        exit 0
    }
    Falhar "Nao existe .env nem .env.example."
}
Ok ".env encontrado."

# ---- 6. Banco de dados --------------------------------------------------------
Passo "Atualizando o banco de dados..."
& $py "database\aplicar_migracoes.py"
if ($LASTEXITCODE -ne 0) {
    Falhar "Nao consegui atualizar o banco. Confira DB_HOST/DB_USER/DB_PASSWORD/DB_NAME no .env e se o banco existe."
}

# ---- 7. Ligar -----------------------------------------------------------------
Passo "Iniciando o ORIS em http://127.0.0.1:5000 ..."
Write-Host "Deixe esta janela ABERTA. Para parar: Ctrl+C." -ForegroundColor Yellow
Start-Job -ScriptBlock { Start-Sleep -Seconds 3; Start-Process "http://127.0.0.1:5000" } | Out-Null
& $py run.py
