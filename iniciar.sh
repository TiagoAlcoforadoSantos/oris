#!/usr/bin/env sh
# ORIS - instala e liga tudo (Linux/Mac). Uso: sh iniciar.sh
cd "$(dirname "$0")" || exit 1
PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
exec "$PY" iniciar.py "$@"
