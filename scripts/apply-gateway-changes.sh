#!/bin/bash
# Aplica los cambios que necesitan reiniciar el gateway (hoy: conectar Discord).
#
# Mecanismo: `systemctl --user reload hermes-gateway` usa el ExecReload de la unidad
# (`kill -USR1 $MAINPID`). En Hermes, SIGUSR1 es un **reinicio en banda**: difiere el stop()
# hasta que terminan los turnos en curso, así que no corta una respuesta a mitad de camino.
# Se agenda como unidad transitoria de systemd (fuera del cgroup del gateway) para que el
# temporizador sobreviva al propio reinicio.
#
# Uso:  systemd-run --user --on-active=60 --unit=<nombre> --collect /bin/bash <este script>
set -u
LOG="$HOME/.hermes/logs/apply-gateway.log"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
{
  echo "=== $(date '+%F %T') aplicando cambios del gateway ==="
  echo "antes: $(systemctl --user is-active hermes-gateway)"
  systemctl --user reload hermes-gateway
  for i in $(seq 1 30); do
    sleep 2
    estado=$(systemctl --user is-active hermes-gateway)
    pid=$(systemctl --user show hermes-gateway -p MainPID --value)
    if [ "$estado" = "active" ] && [ -n "$pid" ] && [ "$pid" != "0" ]; then
      sleep 6
      echo "despues: activo, pid=$pid"
      break
    fi
  done
  echo "--- plataformas conectadas segun el log del gateway:"
  grep -aiE "\[(Telegram|Discord)\].*(Connected|Conectado|polling mode)|adapter: \[Discord\]" \
    "$HOME/.hermes/logs/gateway.log" | tail -6
  echo "--- errores recientes relacionados a discord:"
  grep -aiE "discord" "$HOME/.hermes/logs/errors.log" | tail -5 || echo "(ninguno)"
} >> "$LOG" 2>&1
