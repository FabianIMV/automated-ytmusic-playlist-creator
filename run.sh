#!/usr/bin/env bash
# Levanta la API (FastAPI con uvicorn) y, si existe frontend/node_modules, también la UI (Vite).
# Ctrl+C detiene ambos procesos.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creando entorno virtual en .venv..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
echo "Instalando dependencias de Python..."
if command -v uv >/dev/null 2>&1; then
  uv pip install -q -r requirements.txt
else
  python -m pip install -q -r requirements.txt
fi

# Detiene un proceso y sus hijos (por ejemplo, npm y el vite que lanza).
kill_tree() {
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

PIDS=()
cleanup() {
  trap - INT TERM EXIT
  echo ""
  echo "Deteniendo procesos..."
  for pid in ${PIDS[@]+"${PIDS[@]}"}; do
    kill_tree "$pid"
  done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM EXIT

uvicorn playlist_creator.api.main:app --reload --port 8000 &
PIDS+=("$!")
echo "API: http://localhost:8000 (documentación en /docs)"

if [ -d frontend/node_modules ]; then
  (cd frontend && exec npm run dev) &
  PIDS+=("$!")
  echo "UI:  http://localhost:5173"
else
  echo "Aviso: no existe frontend/node_modules; solo se levanta la API."
  echo "       Para la UI ejecuta: cd frontend && npm install"
fi

wait
