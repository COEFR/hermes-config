---
name: hermes-local-ops
description: "Use when operando ESTE equipo (modelo, gateway, proyectos)."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, entorno, modelo, gateway, proyectos, ops]
    related_skills: [hermes-tool-availability, hermes-agent-state, hermes-import-from-backup, hermes-agent]
---

# Este equipo — entorno, modelo, gateway, proyectos

Datos y reglas de ESTA instalación (perfil `default`, usuario Linux `ubuntu`). Los procedimientos de cada tema viven en skills hermanas — no duplicar acá:

| Tema | Skill |
|---|---|
| Una tool falta o no se habilita | **`hermes-tool-availability`** |
| Escribir memoria, límites, historial, `state.db` | **`hermes-agent-state`** |
| Importar respaldos de otra máquina | **`hermes-import-from-backup`** |
| Todo lo demás de Hermes (features, config, superficies) | **`hermes-agent`** + docs `llms.txt` |

## Entorno
- `HERMES_HOME=/home/ubuntu/.hermes`, perfil **default**, usuario Linux `ubuntu`.
- Única credencial: `DEEPSEEK_API_KEY` → modelo **`deepseek-flash` / provider `deepseek`**.
- `config.yaml` **nunca** se edita a mano: usar `hermes config set KEY VAL`. Secretos solo en `.env`.
- Este equipo **no es el VPS viejo**: no tiene nginx, ni `/var/www`, ni los scripts de automatización (ver la skill de importación).
- Respaldos de config previos en `~/.hermes/cache/scratch/config.yaml.bak.*`; respaldos de memoria en `~/.hermes/cache/scratch/memories_*`.

## Modelo
- Ver: `hermes config get model`. Cambiar: `hermes config set model.default <m>` + `model.provider <p>`, y **borrar `model.base_url`** si venía de otro proveedor (un `base_url` de OpenRouter con credencial de DeepSeek hace fallar con HTTP 400 toda sesión nueva).
- **Dylan pide NO cambiar el modelo sin preguntarle** (tampoco límites que afectan el costo, como los topes de memoria).
- Al lanzar una verificación desde CLI, pasar `-m/--provider` explícitos: un `model.default` equivocado produce un HTTP 400 que se confunde con un fallo de toolsets.

## Gateway
- Desde 2026-09-20 corre como **unidad systemd de usuario**: `~/.config/systemd/user/hermes-gateway.service` (`enabled`, `Restart=always`, 5 s) y `loginctl show-user ubuntu -p Linger` → `yes`. Sobrevive al cierre de sesión SSH y a reinicios. Comprobar con `systemctl --user status hermes-gateway`.
- **Nunca lanzarlo a mano (`hermes gateway`) desde una sesión SSH.** Queda atado al `systemd --user` de esa sesión: al caer la conexión (p. ej. `sshd [...] Read error from remote host: No route to host`), systemd hace tear-down del usuario, mata el gateway con SIGKILL y el chat queda mudo. Rastro: `lifecycle_ledger: Previous gateway life ... exited UNCLEANLY` + `systemctl --user` mostrando que el usuario cerró sesión, **sin** registro de OOM en `dmesg`. Si hay que lanzarlo a mano, usar la unidad o `systemd-run --user`.
- **Vigilante externo** (cubre lo que systemd NO cubre: proceso vivo pero Telegram desconectado o loop trabado): `~/.hermes/scripts/gateway-watchdog.py`, por cron del sistema cada 3 min, log en `~/.hermes/logs/watchdog.log`. Sondea unidad activa + latido `~/.hermes/state/gateway.heartbeat` (<180 s) + racha de fallos de Telegram; si falla, reinicia la unidad y **avisa por Telegram con la Bot API directa** (canal independiente del gateway caído). Anti-rebote: 1 reinicio cada 10 min.
- Prueba e2e de la red de seguridad: `~/.hermes/scripts/gateway-selftest.py` (SIGKILL → systemd lo levanta en ~5 s; parada intencional → la levanta el vigilante). Resultado en `~/.hermes/logs/gateway-selftest.log`. Lanzarla con temporizador (`systemd-run --user --on-active=120 …`), nunca dentro del turno: tumbar el gateway mata el turno en curso y la respuesta no sale.
- Tras volver de una caída la plataforma **descarta los mensajes recibidos mientras estaba caída** (`drop_pending_on_cold_boot: true`): lo que el usuario escribió en esa ventana se perdió — hay que pedirle que lo repita, no inventar que llegó.
- Si corre manual: `hermes gateway install` lo deja como servicio (corta el chat unos segundos → hacerlo al final de un turno y avisando).
- Relee la config en cada turno (caché por mtime del archivo), así que no hace falta reiniciarlo para aplicar toolsets; pero una conversación ya iniciada conserva su schema viejo de tools.
- Logs: `~/.hermes/logs/` (`agent.log`, `errors.log`, `gateway.log`) · `hermes logs [--follow]` · diagnóstico `hermes doctor`.

## Discord (conectado 2026-09-20)
Credenciales en `.env`: `DISCORD_BOT_TOKEN`, `DISCORD_ALLOWED_USERS` (solo el dueño del server), `DISCORD_HOME_CHANNEL` + `_NAME` y `DISCORD_SIGNALS_CHANNEL` (canal de alertas, usado por `~/.hermes/data/trading/signals.py`).
- **Dos trampas al habilitar una plataforma nueva**: (1) `config.yaml → platform_toolsets.<plataforma>` suele venir con un nombre inválido (p. ej. `discord: ['hermes-discord']`); si no se corrige con `hermes tools enable --platform discord <toolsets>`, la plataforma conecta pero **sin ninguna herramienta**; (2) la librería del adaptador puede no estar instalada (`discord.py` → `~/.hermes/bin/uv pip install --python ~/.hermes/hermes-agent/venv/bin/python "discord.py>=2.3,<3"`). Verificar siempre con `venv/bin/python -c "import discord"` **antes** de reiniciar.
- **Reiniciar el gateway desde dentro del gateway está bloqueado** (con razón: SIGTERM mata al que reinicia). La vía sancionada es `systemctl --user reload hermes-gateway` = `kill -USR1`, que en Hermes es un **reinicio en banda que difiere el stop hasta que terminan los turnos**. Agendarlo con temporizador (`systemd-run --user --on-active=60 --collect /bin/bash ~/.hermes/scripts/apply-gateway-changes.sh`, que deja el resultado en `~/.hermes/logs/apply-gateway.log`), nunca dentro del turno.
- Verificación de entrega a Discord sin depender del gateway: mandar por la Bot API y **leer el canal de vuelta** (`GET /channels/{id}/messages`) para confirmar que el mensaje existe.
- **Auditar el servidor sin tools de Discord**: los toolsets `discord`/`discord_admin` existen como builtins pero **no están en `platform_toolsets.discord`**, así que la única vía es la Bot API por `terminal` (token `DISCORD_BOT_TOKEN` de `.env`), y siempre **solo GET**. Script listo: `~/.hermes/cache/scratch/discord_audit.py` (bot, guild, roles con bits de permisos, canales con overwrites, automod/onboarding/invites/bans/miembros).
- Datos del server (2026-09-20): guild `1551311080104398969` "El servidor de Kevdy", dueño/al único usuario permitido = `coefr` (596806397660889106); el rol del bot ("Hermes") trae solo Ver canal/Enviar/Adjuntar/Enlaces/Reacciones/Manage Channels — **sin Administrador**, por eso `GET /guilds/{id}/members` da 50001 (falta el intent GUILD_MEMBERS) y automod/invites/bans dan 403. `features: []` = **Community desactivado**.
- **Ruido de trazas en Discord/Telegram**: el global `display.tool_progress: all` de `config.yaml` hace que cada llamada de tool salga publicada en el canal. Ojo con el resolvedor (`gateway/display_config.py`): el valor **global pisa los defaults por plataforma**, así que con el global en `all` **Telegram también muestra todo**, aunque su tier diga `off`. Para silenciar solo una plataforma: `hermes config set display.platforms.discord.tool_progress off` (la CLI avisa "not a recognized config key" pero **sí lo escribe**, como booleano `False`, que el normalizador convierte en `off`; el gateway lee el YAML crudo). Verificar con `venv/bin/python -c "import yaml; from gateway.display_config import resolve_tool_progress; ..."` y no reiniciando el gateway: relee la config en cada turno. Aplica desde el turno siguiente. `interim_assistant_messages` y `long_running_notifications` quedan aparte (se conservan los avisos de tareas largas). Respaldo: `cache/scratch/config.yaml.bak.*`.
- **Qué puede hacer el bot por la Bot API** (medido con `~/.hermes/cache/scratch/discord_probe.py`, que sondea cada capacidad con una operación no-op): `MANAGE_CHANNELS` ✅ crear/editar/borrar canales y categorías, nombre, tema, `position`, `rate_limit_per_user`, archivar. **403 en `MANAGE_ROLES`** (no puede poner overwrites → no puede dejar canales en solo-lectura, ni crear/asignar roles) y **403 en `MANAGE_GUILD`** (no puede activar Community, ni verificación, ni AutoMod, ni onboarding, ni pantalla de bienvenida, ni convertir un canal en canal de anuncios). Sin `GUILD_MEMBERS` (`GET /guilds/{id}/members` → 50001) no puede listar miembros.
- **Truco de solo-lectura sin `MANAGE_ROLES`**: poner `rate_limit_per_user: 21600` (6 h, el máximo) en los canales de avisos. El bot **está exento porque tiene Manage Channels** — verificado: dos publicaciones seguidas en un canal con slowmode 6 h dieron HTTP 200 (y se borraron después). Los humanos quedan limitados a un mensaje cada 6 h.
- **Overwrites de permisos: el método es `PUT`, no `PATCH`** (`PUT /channels/{id}/permissions/{overwrite_id}`); con `PATCH` Discord devuelve **405 Method Not Allowed**, que se confunde fácil con un problema de permisos.
- **Rate limit real**: llamadas en ráfaga a `GET /guilds/{id}/channels` devuelven **429 con `retry_after` ~20 s** (y el JSON de error NO es una lista: iterarlo revienta con "string indices must be integers"). Pausar ~0.7 s entre escrituras, dormir según `retry_after` al reintentar y tratar cualquier respuesta que no sea `list` como error.
- Scripts de armado (idempotentes, se pueden re-correr): `~/.hermes/cache/scratch/discord_build.py` (categorías, canales, temas, orden, slowmode), `discord_content.py` (textos de reglas/bienvenida/anuncios/guía y su verificación releyendo el canal), `discord_final.py` (árbol final del server), `discord_quitar_comunidad.py` (borra la categoría 💬 COMUNIDAD y reescribe los textos que la mencionaban).
- **Estructura final que Dylan quiere** (2026-09-20): `📋 INFORMACIÓN` (#reglas, #anuncios, #bienvenida) · `📡 SEÑALES` (los 4 canales del bot) · `🤖 HERMES` (#hermes) · `🔊 VOZ` (#sala-general, #juegos). **Pidió explícitamente eliminar «lo de comunidad»**: no hay categoría 💬 COMUNIDAD ni #general/#off-topic, y **no hay que activar la función Community de Discord**. El único canal de conversación es **#hermes** → no volver a correr `discord_build.py` tal cual sin sacar de `CATEGORIAS`/`ORDEN` la entrada de COMUNIDAD (la recrearía).

## Proyectos del usuario
- Convención: `~/.hermes/data/<proyecto>/` con el código/copias + `NOTAS.md` con el detalle técnico. Proyectos: `dolarbolivia`, `edgar`, `facebook`, `zeroscript`, `aivtuber`, `trading`.
- **Leer la `NOTAS.md` del proyecto antes de trabajar en él**; los detalles de proyecto no van a memoria.
