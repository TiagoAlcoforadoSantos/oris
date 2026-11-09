@echo off
REM ORIS - clique duas vezes neste arquivo para instalar e ligar tudo.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python nao encontrado. Instale o Python 3.10+ em https://www.python.org e marque "Add to PATH".
  pause
  exit /b 1
)
python iniciar.py %*
if errorlevel 1 pause
