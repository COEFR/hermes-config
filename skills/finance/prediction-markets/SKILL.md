---
name: prediction-markets
description: "Use when armando trackers de Polymarket en Actions."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [polymarket, prediction-markets, smart-money, github-actions, discord]
    related_skills: [trading-signals, channel-watcher-bots]
---

# Prediction markets (Polymarket) — datos, smart money y trackers

Un tracker de Polymarket es un vigilante de operaciones: lee trades públicos, filtra por tamaño o por wallet y avisa. La parte frágil no es el filtro, es la **fuente de datos** y el **estado entre corridas**.

## Regla 0 — probar la fuente antes de desplegar: las APIs de Polymarket cambian y piden auth
El repo de turno puede traer una URL muerta y verse perfecto en el código. Verificar con un `curl` y **mirar el cuerpo**, no el tiempo de respuesta:
- `https://clob.polymarket.com/trades` → **401** (hoy exige autenticación).
- `https://data-api.polymarket.com/trades?limit=N` → **pública**, sin key. Campos útiles: `proxyWallet`, `side` (BUY/SELL), `outcome` (Yes/No), `size`, `price`, `timestamp` (epoch), `conditionId`, `title`, `slug`. El monto en USD es `size × price`.
- `https://gamma-api.polymarket.com` para metadata de mercados.
- **El endpoint de trades cachea ~2 min**: dos fetches separados 35 s devuelven exactamente los mismos 100 trades (mismo `timestamp` máximo). Un poller de 30 s no ve nada nuevo; la frecuencia real de los avisos la pone la caché, no el `check_interval`.

## Regla 0.1 — en Actions, sin estado persistido el tracker queda mudo o repite
Un tracker que siembra (`first_run`) al arrancar y pierde su set de vistos en cada corrida **nunca alerta** si corre en jobs de pocos minutos: siembra, y cuando la API se refresca el job ya terminó. Guardar el estado en un JSON del repo (`seen.json`), cargarlo al inicio (si existe, **no** sembrar), escribirlo después de cada vuelta y **commitearlo al final del workflow**. Sin ese commit el dedupe se olvida y el canal se llena de repetidas.

## Qué repos sirven en Actions y cuáles no (verificado leyendo el código)
| repo | qué es | ¿Actions? |
|---|---|---|
| `al1enjesus/polymarket-whales` | Python puro, 4 dependencias, alertas Telegram/Discord | **sí**, con estado en el repo |
| `pselamy/polymarket-insider-tracker` | Postgres + Redis + Alembic + scoring ML + polling cada 5 s | **no**: es un servicio permanente, no un job |
| `thelastbodhisattva/GottaTrackEmAll` | backend + frontend + docker-compose | no: es una app web |
| copy-trading (`duola`, OctoBot) | pide clave privada del usuario | **descartado por seguridad** |
| `warproxxx/poly-maker` | market making continuo | no: necesita estar siempre vivo |
| `pmxt-dev/pmxt`, `Polymarket/py-clob-client` | librerías/cliente CLOB | son insumo, no tracker |
No proponer el insider-tracker «con servicios» de Postgres/Redis en un job de 5 min: levantar la base, migrar y correr cada vez se come la ventana y el estado se pierde igual.

## Receta: adaptar un tracker de terceros a GitHub Actions
1. **Repo propio (no fork), y público o privado según la frecuencia**: un fork público expone lo que el config traiga, así que se clona y se crea un repo propio. Con las credenciales en **Secret** y los ids de canal en **Variable** (nada en el código), el repo **público** da minutos ilimitados y costo cero; el privado en plan Free da 2.000 min/mes y un poller de 5 min con ventana de 4-5 min son ~77.000 min/mes → sobrefacturación de cientos de USD. Antes de pasarlo a público, `grep -rn "ghp_\|xox\|discord.com/api/webhooks" .` para confirmar que no quedó ningún token en el código ni en el historial.
2. **Probar el fetch a mano** (`python3 -c "import main; print(len(main.fetch_recent_trades('x', 100)))"`). Si devuelve 401/0, arreglar la fuente antes de tocar el workflow.
3. **Normalizar los campos a lo que el código espera** (`market`/`conditionId`, `side`, `size`, `price`, `timestamp`, `id` estable para el dedupe). Al reemplazar una función entera, comprobar que **no se llevó puestas las vecinas** (`trade_unique_id`, `parse_trade_usd_size`, `format_side`): el `NameError` aparece recién en la corrida real.
4. **Estado en `seen.json`** + escritura atómica (`tmp.replace(...)`) + commit al final.
5. **Aviso con la wallet** (`0x6a74…ae4b`): el valor del canal es poder seguirla; sin la wallet el aviso es una curiosidad.
6. **Entrega**: si el repo solo manda por webhook y el bot no tiene *Manage Webhooks* (crear webhook devuelve **403**), parchear el emisor para usar la Bot API con `DISCORD_BOT_TOKEN` + id de canal; el chequeo de «discord habilitado» del código original mira el webhook, así que hay que ampliarlo a «o hay token + canal».
7. **Workflow**: `schedule` cada 5 min + `workflow_dispatch`, `timeout-minutes` holgado, `code=0; timeout 260 python3 main.py || code=$?` y **124 tratado como éxito** (bajo `bash -e`, que es el shell de `run:`, `timeout …; code=$?` aborta el paso y deja la corrida en rojo aunque el corte fuera previsto). Sin acciones de terceros si la cuenta lo restringe: `git clone https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git repo` y el Python del runner.
8. **`permissions: contents: write`** en el YAML: sin eso el token del runner es de solo lectura y el paso de guardar falla con `remote: Write access to repository not granted` **después de haber alertado** — la corrida queda verde en apariencia, el estado no se guarda y la siguiente repite los avisos.
9. **Verificar releyendo**: `GET /channels/{id}/messages` (que el mensaje esté, con `embeds: 0` y `flags & 4` si se quiere sin vista previa), el commit «vistos …» que escribe el propio runner, y `/actions/runs/{id}/jobs` para el paso que falló. Un POST 200 no prueba entrega.

## Canales por repo
Una categoría (`POST /guilds/{id}/channels` con `type: 4`) y un canal de texto por repo (`type: 0`, `parent_id` de la categoría) — el bot con *Manage Channels* los crea solo. El **id del canal no es secreto** (va como variable del repo o constante de respaldo); el **token sí** (secret o config de un repo privado).

## Aviso completo: link a la predicción, link al perfil y gráfico del mercado
Un aviso sirve si se puede seguir en dos clics. Formato estándar de esta cuenta:
- **Predicción**: `https://polymarket.com/event/<eventSlug>` (el trade trae `eventSlug` y `slug`; si falta el primero, `slug` abre el mercado igual).
- **Perfil**: `https://polymarket.com/profile/<proxyWallet>` — dirección **completa**: la abreviatura (`0x6a74…ae4b`) es solo para mostrar, con ella no hay link.
- **Gráfico**: `https://clob.polymarket.com/prices-history?market=<asset>&interval=1d&fidelity=60` es **pública** (200, `{history:[{t,p}]}`) aunque `/trades` del mismo host pida auth; `data-api.polymarket.com/prices-history` no existe (404). Dibujar con Pillow (~900×420, fondo oscuro, línea de probabilidad, marca del precio de la apuesta) y adjuntarlo en el mismo mensaje.
- Para que esto funcione, el dict normalizado tiene que conservar `eventSlug`, `slug`, `proxyWallet`, `asset` (token) y `title`; si el tracker solo guardaba el monto y el lado, el gráfico y los links no se pueden armar después.
- en **Discord**: `flags: 4` en el `payload_json` y el PNG como `files[0]` en multipart; si el emisor manda JSON cuando hay imagen, el adjunto se pierde. En **Telegram**: los links van como `<a href>` con `parse_mode=HTML` y `disable_web_page_preview`, y la imagen va en mensaje aparte.
- Receta con el código (dibujo, multipart y verificación releyendo el canal) en `references/alertas-con-links-y-grafico.md`.

## Pitfalls
- **Estrellas no es funcionamiento**: `polymarket-whales` tenía la fuente muerta (401), el filtro de siembra dejaba el canal mudo y el commit de estado daba 403 por falta de permisos. Los tres fallos convivían con 64★ y un README que se veía bien.
- **No llamar «insider» a un tamaño grande**: sin datos de edad o historial de la wallet, un trade de $1.000 es una ballena, no un insider. Para un detector propio, marcar wallets nuevas con pocas operaciones y tamaño grande, y decir en el mensaje que es una heurística.
- **Nunca pedir clave privada**: los repos de copy-trading la piden; un tracker de solo lectura usa direcciones públicas. Si el pedido es «copiar», la respuesta es seguimiento y aviso, no ejecución.
- **El filtro por monto se elige con la distribución delante**: contar cuántos de los últimos 100 trades superan cada umbral (medido: ~3 pasan $500, ~5 pasan $100) — con un umbral alto el canal queda vacío y se lee como roto.
- **La wallet con 500 operaciones en un día no es un insider, es un bot**: descartar las que superan el tope de historial (market makers y MM automatizados) **antes** de puntuar. Y si el conteo se corta en el tope, no derivar la edad de la operación más vieja: una wallet «de 0,3 días» con 500 operaciones es un profesional con historial largo, no una cuenta nueva.
- **Canal selectivo = canal mudo**: si el umbral queda alto por precisión, acompañarlo con un **resumen diario** (workflow aparte a la hora local elegida, que lee los contadores que deja el ciclo) y ofrecer bajar el umbral con la distribución delante. Medido: con $500 el canal pasó horas sin un mensaje; con $300 salió un aviso de 4/6 en minutos, y el resumen reportó «300 trades revisados · 5 candidatos».
- **`git add -A a.json b.json c.jsonl` no guarda NADA si uno no existe**: git aborta el add entero con «pathspec did not match» y, si el paso lleva `|| true`, la corrida queda verde. Los archivos opcionales (contadores, el log de alertas antes del primer aviso) son justo los que faltan → el resumen lee ceros y parece que el ciclo no corrió. En un repo dedicado usar `git add -A` a secas y `.gitignore` para lo que no va (`charts/`, `__pycache__/`).
- **Antes de reescribir un repo que se auto-commitea, fijar la identidad de git**: sin `user.name`/`user.email` en el repo, `git rebase --continue` muere con «empty ident name» y deja el rebase a medias. Configurarla una vez, y resolver los conflictos de los archivos de estado con `git checkout --theirs <archivo>`: la versión del runner es la que manda. Cuando el push se rechaza porque el bot commiteó primero, el bucle que funciona es `fetch` → `rebase --autostash` → `push`, con 2-3 reintentos.
- **Un `--dry-run` con el token cargado SÍ manda mensajes**: el modo seco evita el envío solo si el emisor no encuentra credenciales; con el `.env` en el entorno, la corrida «de prueba» publicó cinco alertas reales en el canal. Para probar formato, vaciar `DISCORD_BOT_TOKEN` (o apuntar a un canal de pruebas) y contar los mensajes del canal antes y después.
