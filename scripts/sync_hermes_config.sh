#!/usr/bin/env bash
# Respaldo completo del agente en COEFR/hermes-config (privado): memoria, skills COMPLETAS
# (con imágenes y fuentes), scripts propios, configuración, cron de Hermes y crontab del sistema.
# NO sube .env (secretos): deja la lista de claves en .env.example para reponerlas al restaurar.
# Corre desde el cron cada 6 horas.
set -uo pipefail

LOG=/home/ubuntu/.hermes/logs/sync_hermes_config.log
REPO=/home/ubuntu/.hermes/cache/hermes-config-repo
H=/home/ubuntu/.hermes
mkdir -p "$(dirname "$LOG")"
exec >>"$LOG" 2>&1

set -a; . "$H/.env"; set +a
if [ -z "${GITHUB_TOKEN_DOLAR:-}" ]; then echo "$(date -Is) ERROR: falta GITHUB_TOKEN_DOLAR"; exit 1; fi
URL="https://x-access-token:${GITHUB_TOKEN_DOLAR}@github.com/COEFR/hermes-config.git"

if [ ! -d "$REPO/.git" ]; then
  git clone -q "$URL" "$REPO" || { echo "$(date -Is) ERROR clonando"; exit 1; }
fi

cd "$REPO" || exit 1
git remote set-url origin "$URL"
git pull -q --rebase origin main || echo "$(date -Is) aviso: pull con problemas, sigo"

# 1) memoria (entre sesiones y perfil del usuario)
rsync -a "$H"/memories/MEMORY.md "$H"/memories/USER.md memories/ 2>/dev/null

# 2) skills COMPLETAS: con imágenes y fuentes, sin caché del hub ni bytecode
rsync -a --delete \
  --exclude='.hub/' --exclude='.git/' --exclude='__pycache__/' \
  --exclude='*.pyc' --exclude='*.lock' \
  "$H"/skills/ skills/ 2>/dev/null

# 3) scripts propios (guardia de memoria, este sincronizador, watchdog…)
rsync -a --exclude='__pycache__/' --exclude='*.pyc' "$H"/scripts/ scripts/ 2>/dev/null

# 4) configuración y cron
mkdir -p config cron
cp "$H"/config.yaml config/config.yaml 2>/dev/null
cp "$H"/cron/jobs.json cron/jobs.json 2>/dev/null
crontab -l > config/crontab.txt 2>/dev/null

# 5) secretos: copia completa del .env (el repo es privado) + la lista de claves
if [ -f "$H/.env" ]; then
  grep -oE '^[A-Z0-9_]+=' "$H/.env" | tr -d '=' | sort > .env.example
  cp "$H/.env" .env
  chmod 600 .env
fi

git add -A
if git diff --cached --quiet; then
  echo "$(date -Is) sin cambios"
  git remote set-url origin https://github.com/COEFR/hermes-config.git
  exit 0
fi

CAMBIOS=$(git diff --cached --stat | tail -1)
git -c user.name="Hermes Agent" -c user.email="hermes@coefr.dev" commit -q -m "respaldo $(date -u '+%F %H:%M UTC')"
for i in 1 2 3; do
  if git push -q origin main; then echo "$(date -Is) subido: $CAMBIOS"; break; fi
  git pull -q --rebase origin main || true
  sleep 4
done
git remote set-url origin https://github.com/COEFR/hermes-config.git
