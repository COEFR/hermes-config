---
name: hermes-slash-commands
description: "Use when publicando un slash command propio en el chat."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, plugins, discord, slash-commands, gateway]
    related_skills: [hermes-local-ops, hermes-tool-availability, hermes-agent]
---

# Comandos propios en el chat (`/mio`) — plugins de usuario

Tarea: que el usuario pueda escribir un comando con barra en Discord/Telegram y que lo conteste Hermes.
El camino es un **plugin de usuario**; el trabajo termina cuando el comando aparece en la **API de Discord**,
no cuando el registro interno de Hermes lo lista.

## Procedimiento

1. **Plugin de usuario** en `~/.hermes/plugins/<n>/`: `plugin.yaml` (`name`, `version`) + `__init__.py` con
   `register(ctx)` que llama a `ctx.register_command(...)`. Copiar la forma de un plugin que ya funcione en
   esa máquina (y de `website/docs/developer-guide/plugins/index.md`) en vez de inventar la firma: una
   firma inventada falla en silencio.
2. **Validar y habilitar**: `hermes plugins doctor ~/.hermes/plugins/<n>` y `hermes plugins enable <n>`.
   El comando se invoca por su **nombre exacto**; renombrarlo exige volver a publicar (el sync borra los
   que sobran).
3. **Reiniciar el gateway, agendado desde fuera del turno** — es lo que dispara la publicación: script con
   `hermes gateway restart` en el **cron del sistema** (con log propio) o `systemd-run --user --on-active=60 ...`.
   Nunca reiniciar dentro del turno: se corta la respuesta en curso. El reinicio **drena** los turnos en curso, así
   que el comando queda publicado recién cuando termina el turno que lo agendó: un chequeo inmediato devuelve
   «no está publicado» y no prueba nada — verificar después, y no prometer el comando en el mismo turno. Dejar además una **verificación
   automática** unos minutos después (que avise en el canal si el comando quedó publicado) y un reintento
   por si el primero no completó.
4. **Verificar contra la API de Discord** (token del bot): `GET /applications/@me` → app id, y
   `GET /applications/{app_id}/commands?limit=200` → **la lista real que ve el cliente**. Comparar ahí, no
   en el registro interno de Hermes.
5. **Recién ahí decir que funciona.** Al usuario: separar "publicado y verificado" de "probado por él"
   (que lo invoque y confirme).

## Contexto del canal: el handler NO lo recibe

El handler de un slash command recibe **sólo `raw_args`** — nada de canal, chat ni autor. Cuando la respuesta
depende de dónde se invocó ("traeme las últimas señales de ESTE canal"), hay que averiguarlo aparte: un
**hook de evento** del gateway sobre `agent:start` guarda el `chat_id` en un archivo, y el handler lo lee.

- Los hooks van en `~/.hermes/hooks/<n>/handler.py` y la función **tiene que llamarse `handle`**. Si se llama
  `main`, el gateway la saltea **en silencio**: en el log queda `Skipping <n>: no 'handle' function found` y el
  hook no hace nada. Renombrar la función es todo el arreglo.
- **Y tiene que ACEPTAR argumentos.** El gateway la invoca con **dos posicionales**: un `def handle():` sin
  parámetros lanza `Error in handler for 'agent:start': handle() takes 0 positional arguments but 2 were given`
  en **cada** mensaje, y el hook deja de funcionar. Firma segura: `def handle(*args, **kwargs)`, tomando de
  `args` el primer dict que traiga `chat_id`/`channel_id`. El síntoma en el chat no es un error visible sino el
  **contexto equivocado** (o vacío) en todo comando que dependa del hook, así que ante eso conviene mirar el log
  del gateway y el archivo puente antes que la lógica del comando.
- El archivo que escribe el hook es el puente; no hay API del contexto del comando para esto.
- **Comando que responde con un archivo**: devolver cadena vacía en el handler y subir el archivo por la API de
  Discord (multipart). Si además el handler devuelve texto, el archivo y el texto compiten por el mismo hueco.
- Un mismo comando puede servir a **varios canales temáticos a la vez**: si el pedido es "las últimas N de cada
  canal", agrupar por canal y emitir una sección por canal con su encabezado y el total de cada uno, en un solo
  archivo. Ojo con las filas **sin canal asignado** (vienen de la ventana previa al etiquetado): si no se
  descartan, inflan la cuenta y el usuario ve un canal de más.

## Diagnóstico cuando el comando no aparece

El adaptador publica los slash commands al **conectar**, así que hay que mirar el log del gateway alrededor
(`~/.hermes/logs/gateway.log`, línea `[Discord] Connected as ...`) y el estado del sync.

- **«This bot is private and you're not on its allowed list…» en un slash command puede ser un señuelo.** El
  motivo real está en el log del gateway (`reason='channel in DISCORD_IGNORED_CHANNELS'`): el canal desde el que
  se invoca figura en `DISCORD_IGNORED_CHANNELS`. Leer el log **antes** de seguir el consejo de pairing que trae
  el mensaje — el usuario permitido puede estar bien y aun así salir ese texto. Sacar el canal de ignorados
  (sin tocar `FREE_RESPONSE`) es el arreglo.

- `~/.hermes/gateway/discord_command_sync_state.json` guarda, por app id, `fingerprint` +
  `last_attempt_at` / `last_success_at`.
- **Un intento registrado SIN `last_success_at`** = el sync arrancó y **no completó** (puede no dejar
  ninguna línea en el log, ni de éxito ni de error). Si además la lista remota no cambió, no se publicó nada.
- El adaptador **saltea** el sync cuando el fingerprint coincide
  (`Skipping Discord slash command sync: same slash-command fingerprint already synced`). Que un comando
  nuevo provoque un intento (fingerprint distinto) prueba que **sí llegó al árbol** de comandos: si dijera
  "same fingerprint", el problema sería el registro del plugin, no la publicación.
- **El arreglo cuando el sync diferencial se cuelga es pasar la política a `bulk`.**
  `DISCORD_COMMAND_SYNC_POLICY` se lee del **scope de secretos** (`.env`, no `config.yaml`): `safe` (default)
  hace sync **diferencial** (consulta la lista, compara y muta comando por comando con ~4,5 s de pausa) y puede
  quedarse **colgado en la consulta** sin dejar ninguna línea en el log; `bulk` publica la lista completa con
  **una sola** llamada (`tree.sync()`). El cuadro que justifica el cambio: intento registrado **sin
  `last_success_at`**, lista remota **sin cambios** y **ni una línea** de sync en `gateway.log`. Con `bulk` el log
  queda `[Discord] Synced N slash command(s) via bulk tree sync` y el comando aparece en la API. Sacar respaldo
  del `.env` antes de tocarlo, reiniciar **desde afuera** y verificar la lista remota: no dar nada por publicado
  sin ese chequeo.
- Cruzar `last_attempt_at` (epoch) con el arranque del gateway en el log para no atribuirle el intento al
  reinicio equivocado.
- No perder tiempo con el **orden de imports**: `get_plugin_commands()` / `_iter_plugin_command_entries()`
  disparan el descubrimiento de forma idempotente y devuelven el comando aunque nadie haya importado
  `model_tools` antes. Si el comando está en el registro interno, el problema es la publicación.

## Salida alternativa que NO depende de Discord

Un comando por **prefijo** contestado por el propio bot (script en cron cada minuto que lee el canal, filtra
los mensajes propios y los de otros bots, y responde) funciona sin registro de aplicación ni ventana de 3 s.
Es la vía para que el usuario tenga la función **hoy** mientras se arregla el slash: ofrecerla de entrada.

## Trampas

- **Editar el plugin después de publicarlo exige OTRO reinicio.** El código del handler queda cargado en memoria
  al arrancar el gateway: subcomandos, argumentos nuevos o distinta forma de parsearlos **no se ven** hasta el
  próximo reinicio — y probar el handler desde afuera (importando el módulo) da un **falso OK**, porque ahí sí se
  lee el archivo del disco. Regla: la lógica nueva va en el **script** que el handler invoca (se valida y se usa
  ya, incluso por prefijo), el handler se toca lo mínimo, y al agregar o cambiar la firma de un comando se agenda
  el reinicio **en el mismo turno** avisando que hasta entonces sólo sirve la vía por prefijo.
- **Una sola fuente para los tres frentes.** El mismo script con flags de consola (`--mint`, `--profit`, …) sirve
  al cron, al comando por prefijo y al handler del slash; el handler sólo arma la llamada. Así una función nueva
  está disponible en el chat en el mismo turno (prefijo) sin esperar la publicación del slash, y no hay dos
  implementaciones que se desincronicen.
- **No levantar un segundo gateway propio para el comando**: Discord admite **una sesión por bot** y la nueva
  **expulsa** la del gateway, dejando el chat mudo. El comando va como plugin del gateway que ya corre.
- Un bot **no puede usar** los comandos de otra aplicación, y las apps que ignoran mensajes de bots nunca van
  a ver lo que publica el nuestro: no hay integración posible por esa vía.
- El reinicio deja el chat unos segundos sin responder: agendarlo lejos de cuando el usuario espera respuestas
  y avisarle.
