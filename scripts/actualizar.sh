#!/usr/bin/env bash
# Actualización incremental programada (Linux/macOS). Equivalente de scripts/actualizar.ps1.
#   scripts/actualizar.sh [fuente ...]        # sin argumentos: todas las fuentes
# Cron sugerido (lunes 07:30):
#   30 7 * * 1  /ruta/al/proyecto/scripts/actualizar.sh
# Códigos de salida: 0 OK, 1 error que cortó la corrida, 2 terminó con errores (ver log),
# 75 había otra corrida en curso (el bloqueo vive en Postgres, no hace falta flock).
set -u
cd "$(dirname "$0")/.."
mkdir -p logs
log="logs/actualizar_$(date +%Y%m%d_%H%M%S).log"
args=(run --no-sync benchmark-bancos actualizar --log-file "$log")
[ $# -gt 0 ] && args+=(--fuentes "$@")
uv "${args[@]}" >/dev/null 2>&1
codigo=$?
find logs -name 'actualizar_*.log' -mtime +90 -delete
exit $codigo
