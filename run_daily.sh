#!/bin/bash
# run_daily.sh — Executado pelo cron 1x por dia
# 
# Instalação do cron (roda todo dia às 04:00):
#   crontab -e
#   0 4 * * * /caminho/para/run_daily.sh >> /caminho/para/logs/scanner.log 2>&1
#
# Ou rode manualmente:
#   chmod +x run_daily.sh
#   ./run_daily.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

echo ""
echo "=============================="
echo " ONYX TV Scanner — $(date '+%Y-%m-%d %H:%M')"
echo "=============================="

cd "$SCRIPT_DIR"

# Ativa venv se existir
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Roda scanner
python scanner.py

# Publica no GitHub (se token configurado)
if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPO" ]; then
    echo ""
    python deploy.py
else
    echo ""
    echo "⚠  GITHUB_TOKEN ou GITHUB_REPO não definidos — pulando deploy"
    echo "   Para ativar, edite este script e defina:"
    echo "   export GITHUB_TOKEN=ghp_seutoken"
    echo "   export GITHUB_REPO=seunome/onyxtv-channels"
fi

echo ""
echo "✓ Concluído em $(date '+%H:%M:%S')"
