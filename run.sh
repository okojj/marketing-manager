#!/usr/bin/env bash
set -euo pipefail
cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-}"
case "$MODE" in local|dev|stop) ;; *) echo 'Usage: ./run.sh {local|dev|stop}'; exit 2;; esac
command -v docker >/dev/null || { echo 'Docker Desktop / Docker Compose is required.'; exit 1; }
docker compose version >/dev/null
if [ ! -f .env ]; then cp .env.example .env; chmod 600 .env; echo 'Created .env from .env.example'; fi
case "$MODE" in
  dev) docker compose up --build -d --wait --wait-timeout 240; docker compose ps ;;
  stop) docker compose down ;;
  local)
    command -v node >/dev/null || { echo 'Install Node.js 20.9+ (24 LTS recommended).'; exit 1; }
    node -e 'const [a,b]=process.versions.node.split(".").map(Number);if(a<20||(a===20&&b<9))process.exit(1)' || { echo 'Node.js 20.9+ is required.'; exit 1; }
    PYTHON="${PYTHON_BIN:-python3}"
    "$PYTHON" -c 'import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"'
    if [ ! -d .venv ]; then "$PYTHON" -m venv .venv; fi
    .venv/bin/python -m pip install -r backend/requirements.txt
    npm --prefix frontend ci --no-audit --no-fund
    exec .venv/bin/python scripts/local.py
    ;;
esac
