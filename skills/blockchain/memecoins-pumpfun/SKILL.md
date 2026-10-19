---
name: memecoins-pumpfun
description: "Use when analizando memecoins de pump.fun o wallets SOL."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [memecoins, pumpfun, solana, rugcheck, wallets, anti-rug]
    related_skills: [trading-signals, blocked-page-recovery]
---

# Memecoins de pump.fun — analizar contexto y seguir wallets (sin API keys)

Implementación de referencia: `~/.hermes/data/memecoins/` (`pump_analizador.py`, `wallet_tracker.py`,
`NOTAS.md`). Extender esos scripts, no reescribirlos. Todo con stdlib + APIs públicas, cero tokens de LLM.

## Fuentes que funcionan sin key (medido)

| Fuente | Endpoint | Qué da |
|---|---|---|
| pump.fun | `https://frontend-api-v3.pump.fun/coins?limit=N&sort=created_timestamp\|market_cap\|ath_market_cap\|reply_count\|last_trade_timestamp&order=DESC&includeNsfw=true` | mcap, `real_sol_reserves` (curva), creador, social, comentarios, edad, `complete`, `transfer_fee_bps`, `token_program`, `boost_mode` |
| pump.fun | `/coins/currently-live?limit=N` | los que están operando ahora |
| RugCheck | `https://api.rugcheck.xyz/v1/tokens/{mint}/report` | authorities, `topHolders`, `knownAccounts`, `insiderNetworks`, `creatorTokens`, `lockers`, `rugged`, score, `totalHolders` |
| DexScreener | `https://api.dexscreener.com/latest/dex/tokens/{mint}` | liquidez, volumen 24h, compras/ventas, cambios, `pairCreatedAt`, `boosts` |
| GoPlus | `https://api.gopluslabs.io/api/v1/solana/token_security?contract_addresses={mint}` | flags extra (honeypot, taxes) |
| RPC | `https://api.mainnet-beta.solana.com` | `getSignaturesForAddress` + `getTransaction` (jsonParsed) |

**No sirven** (medido 2026-10): `frontend-api.pump.fun` (530), `frontend-api-v2.pump.fun` (403),
`/coins/{mint}` y `/coins/{mint}/trades` (404 en v3 — usar las listas y filtrar); para RPC:
publicnode (rate limit), drpc (plan pago), ankr (key), onfinality (rate limit).

## Alerta roja medida: lanzamiento de REPARTO MASIVO (no comunidad)

Firma on-chain (medida 2026-10-07 sobre tokens del radar que despegaron): una wallet **nueva** con
**~7,381 SOL exactos** y ~1.400 tx que **crea cuentas de token y reparte a 300-380 wallets** en las
primeras horas. Tres lanzadores distintos tenían el **mismo saldo exacto** (7,381 SOL) repartiendo a
372 / 354 / 339 wallets: es **un solo operador con servicio de lanzamiento** (wallet nueva por token).

Por qué es alerta roja: el reparto va a **cáscaras** (0 operaciones, 0,002-0,01 SOL) — no hay demanda
orgánica detrás. Los tokens con esa firma son los que colapsan. Chequeo rápido: si el creador es una
wallet sin historial de trading y repartió tokens a cientos de wallets, **marcar y descartar**; y si
varias wallets lanzadoras comparten el **mismo saldo exacto**, es el mismo operador (no son proyectos
distintos).

Complemento: los **creadores** de estos lanzamientos son wallets **frescas y desechables** (RugCheck
`creatorTokens: 0` en todos) — no tienen track record, así que no sirven para puntuar al dev.

## Trampas que cambian el resultado

1. **Los top holders de RugCheck incluyen la curva de pump.fun** (94-100% del supply en un token nuevo).
   Sin descontarla, **todo** token recién lanzado parece un rug con "top 10 al 100%". Excluir por
   `knownAccounts` los `type` AMM / LOCKER / CREATOR / POOL / BURN / FEE (los nombres también traen
   "Pump Fun", "Pool", "Curve"). Medir al dev aparte con `creatorBalance / token.supply`.
2. **Un token sin volumen es una trampa para el puntaje**: una memecoin graduada hace meses, con
   buena liquidez y miles de comentarios, puede sacar 90/100 mientras su volumen de 24 h es 43 USD
   (no hay a quién venderle). Regla dura: **volumen 24 h < 500 USD = descalificante**; <5k = amarillo.
3. **El dato de mercado miente si el token no está en la lista de pump.fun**: el stub queda con
   mcap 0 y edad nula. Tomar mcap de `ds.marketCap`/`fdv` y la edad de `ds.pairCreatedAt`.
4. **Discord devuelve HTTP 403 al User-Agent por defecto de urllib.** Mandar `User-Agent` propio
   ("hermes-.../1.0"); sin eso la entrega falla en silencio y parece un problema de permisos.
   Para verificar el envío de verdad, releer el canal (`GET /channels/{id}/messages`) — el 200 del
   POST no prueba que el mensaje quedó donde el usuario lo ve.
5. **Al agregar una wallet nueva, la primera pasada debe ser línea base** (anotar firmas sin avisar):
   si no, manda 10 avisos de historial viejo y el canal se vuelve ruido.
6. **El filtro de polvo es obligatorio**: las wallets reciben micro-transferencias constantes
   (5,84e-06 de un token, 0 SOL). Sin exigir `|delta SOL| >= 0.01` en los no-swap, el tracker
   escupe decenas de "recibe X" sin valor.
7. **`sorted()` sobre tuplas `(dict, clave)` explota** cuando hay empate (compara dicts): ordenar
   con `key=lambda kv: (-kv[0]["veces"], ...)`.
8. **El símbolo de un mint sacado de DexScreener**: si el mint es el `quoteToken` del par hay que
   devolver el símbolo del quote, no el del base (si no, cualquier token sale con el nombre de SOL).

## Números oficiales y medidos (usar estos, no los de blogs)

- **Graduación: ~85 SOL recaudados** (`real_sol_reserves/1e9`), equivale a ~69k USD. `complete=true`
  en el API = ya migró a PumpSwap.
- **Fees (pump.fun/docs/fees)**: crear 0 SOL · graduar 0,015 SOL · **curva 1,25% por lado**
  (creator 0,30 + protocol 0,95 + LP 0) → **ida y vuelta ≈ 2,5%**; con eso un +2,5% apenas empata.
  Post-graduación baja por tramos de mcap (1,25% → 0,325%). Los blogs que dicen "1%" están viejos.
- **Tasa base a comunicar siempre**: ~76% de los tokens nuevos de Solana son rug (arXiv 2603.24625),
  4,55% de los tokens de pump.fun sobrevive 90 días (CoinGecko), 0,412% de las wallets materializó
  +10.000 USD (Dune), 6,16% de traders fue rentable a 90 días (DWF/FOMO).

## Veredicto: reglas, no opiniones

Puntaje 0-100 que arranca en 50; **cualquier bandera roja fuerza NO**. Se muestran siempre las tres
listas (descalificantes / a vigilar / a favor) y el costo de operación, porque el usuario decide con
umbrales, no con un adjetivo. Rojos: mint/freeze authority activa, `rugged`, top10 >35%, dev >20%,
volumen 24 h <500 USD, liquidez <5k (en graduados), transfer hook, baneado, <3 min de vida.
Verdes: authorities revocadas, top10 <20%, dev bajo, liquidez >25k, volumen sano, comentarios,
graduado hace poco.

## Seguir wallets: lo que se puede prometer y lo que no

- Sirve para **enterarse** (polling cada 2-5 min), no para copiar: para copiar hace falta bajar de
  minutos a milisegundos (websocket/Helius, de pago) y aun así el original te ve.
- Clasificación de una tx con `meta.preTokenBalances`/`postTokenBalances` + delta de SOL del índice de
  la wallet: token sube + SOL baja = **compra**; token baja + SOL sube = **venta**; sin SOL = polvo.
  Verificado sobre swaps reales (6 ventas / 7 compras en 12 tx).
- **`--descubrir` lista wallets que aparecen como holders grandes en varios tokens que corrieron.**
  Eso NO es rentabilidad: presentarlo como "candidatas sin verificar" y pedir que se mire el PnL
  (GMGN, Cielo) antes de seguirlas. Un clúster repartido aparece con **porcentajes idénticos** entre
  wallets (medido: 6 wallets con 0,9878660849676077% en el mismo token).
- Lo más valioso de la señal no es la etiqueta "smart money" (histórica) sino el **momento de entrada**
  (primeros bloques) y el tamaño relativo.

## Imagen del token para las alertas (cadena medida)

Los gateways IPFS públicos **bloquean IPs de datacenter**: `ipfs.io`, `dweb.link`, `w3s.link` y
`nftstorage.link` responden **403**; sirven `gateway.pinata.cloud`, `ipfs.filebase.io` y
`4everland.io` (200 con la misma imagen). Orden que funciona:

1. `info.imageUrl` del par de DexScreener (CDN propia, sin bloqueo)
2. `image_uri` del token en pump.fun, por los gateways que responden
3. **`https://images.pump.fun/coin-image/<mint>?variant=600x600`** — CDN por mint, sirve para casi
   cualquier token de pump.fun

La CDN de pump.fun devuelve una **imagen genérica** cuando el token no tiene arte: guardar su md5
(`0f11c2db…` para coin-image, `abc95adb…` para la tarjeta `pump.fun/api/og/coin/<mint>`) y descartarla,
si no se manda un dibujo que no es el memecoin. La tarjeta og **también** es genérica cuando falta el
arte (dos mints distintos devolvieron el mismo md5).

## Embeds de Discord (estética + imagen)

- Un aviso por token, con **barra de color por veredicto** (verde/ámbar/rojo), campos con mcap,
  curva, edad, holders, liquidez y compras/ventas, y la imagen del token como adjunto.
- **Trampa que descarta la imagen en silencio**: el `payload_json` se arma con el embed, así que hay
  que reemplazar la URL de la imagen por `attachment://<nombre real del archivo>` **antes** de
  serializar el payload. Si se hace después, Discord no encuentra el adjunto y publica el embed sin
  foto (el mensaje sale igual). Verificar leyendo el mensaje: el campo `embeds[].image.url` tiene que
  venir resuelto como `cdn.discordapp.com/attachments/...`.
- Los adjuntos se suben con multipart y el `Content-Type` **detectado por bytes** (PNG/JPEG/WEBP/GIF),
  no asumido.

## Compatibilidad de intérprete (mordida real)

En este equipo `python3` es **3.11** y `/usr/bin/python3` (el del cron) es **3.14**. Un f-string con
`\` dentro de las llaves —permitido desde 3.12— compila en 3.14 y **revienta en 3.11**. Compilar y
correr con **los dos** intérpretes antes de dar un script por bueno (`python3 -m py_compile` y
`/usr/bin/python3 -m py_compile`), porque el cron usa el segundo.

## Cron de este proyecto: dónde corre cada cosa (leer antes de tocar el crontab)

**En este equipo el ciclo Argos NO corre en el VPS**: corre en GitHub Actions (`argos.yml` ejecuta
`argos_run.py`, que decide por reloj; `comandos.yml` atiende los comandos de texto; el estado vive en el
repo privado `COEFR/argos-datos`). Los dispara cron-job.org cada 5 min, porque el schedule de GitHub es
impuntual. El crontab del VPS **solo** mantiene: `ath_server.py`, `arrancar_vigia.sh` (WebSocket en vivo,
no puede vivir en Actions), la guardia de memoria, el watchdog del gateway y los jobs de otros proyectos
(DólarBolivia, trading).

No volver a agregar al cron local `cohortes.py`, `registro_calls.py`, `canal_wallets.py`, `control_test.py`,
`consumo.py`, `comando_discord.py` ni `tabla_calls.py`: duplican el ciclo de Actions, gastan doble RPC y
pueden duplicar avisos (cada lado lleva su propio estado). Ese duplicado, nunca apagado tras la migración
del 10-13 oct 2026, es lo que llenó la RAM y tumbó el gateway. Al migrar algo a Actions, borrar las líneas
del crontab en la misma sesión, no "después".

Si alguna vez se vuelve a correr en el VPS, todo job pesado (`cohortes.py`, `registro_calls.py`,
`canal_wallets.py`, `ath_server.py`, `control_test.py`, `consumo.py`) va envuelto así, **con un lock
distinto por job**:

```
/usr/bin/flock -n /tmp/hermes-<job>.lock /usr/bin/timeout 900 \
  /usr/bin/prlimit --as=1572864000 -- /usr/bin/python3 <script> <args> >> logs/cron.log 2>&1
```

Por qué es obligatorio (incidente 14-18 oct 2026): sin `flock` ni `timeout`, cron lanzaba una copia
nueva antes de que terminara la anterior (varios jobs tardan más que su intervalo). Llegaron a **84
procesos, load 42, swap 100%** y el kernel empezó a matar: **al gateway y no a los jobs**, porque el
gateway corría con `oom_score_adj=+200` y los jobs en `0`. Resultado: el bot quedaba conectado a
Telegram pero sin poder responder. `cron.log` acumuló **407 "Killed"** en 5 días.

- **Protección del gateway** (ya aplicada): drop-in
  `~/.config/systemd/user/hermes-gateway.service.d/oom.conf` con `OOMScoreAdjust=-500`. El unit solo
toma efecto en el próximo arranque: aplicarlo en vivo con
  `echo -500 | sudo tee /proc/$(systemctl --user show -p MainPID --value hermes-gateway)/oom_score_adj`.
- **Guardia de memoria** (ya instalada): `~/.hermes/scripts/guardia_memoria.py` cada 3 min desde cron.
  Avisa por Telegram con `MemAvailable < 600 MB` (enfriamiento 20 min) y corta los jobs más viejos con
  `< 350 MB`. Nunca toca procesos de Hermes/gateway. Log: `~/.hermes/logs/guardia_memoria.log`.
- **Verificar una línea de cron de verdad**: esperar el tick y comprobar el proceso envuelto + que
  `/proc/<pid>/limits` muestre `Max address space 1572864000`, y que una segunda copia manual del mismo
  job salga con exit 1. No alcanza con ver la línea en `crontab -l`.
- **Probar la guardia sin matar trabajo real**: usar un script falso en `/tmp/cohortes.py` y los
  overrides `GUARDIA_UMBRAL_MATA_MB` / `GUARDIA_MARGEN_MB` con `--no-avisar`; con el umbral forzado
  también mata jobs reales en curso (se recuperan en el siguiente tick, pero se pierde ese ciclo).
- `timeout` acá es uutils 0.8.0: `timeout <seg> cmd` funciona igual (exit 124 al cortar).

## Al entregar

- Decir el **costo real** (2,5% ida y vuelta en la curva) junto al veredicto: sin eso el análisis no
  sirve para decidir.
- Separar "verificado" de "inferido": las wallets candidatas son propuestas, no recomendaciones.
- El agente **no puede crear canales** en Discord ni en Telegram: el canal dedicado lo crea el usuario
  y el ID va a `.env` (`DISCORD_WALLETS_CHANNEL` / `TELEGRAM_WALLETS_CHANNEL`); mientras tanto, los
  guiones caen a los canales existentes por cadena de fallback.
- Verificar la entrega **leyendo el canal**, y verificar el cron esperando una corrida real (no
  confiar en que "la línea quedó en el crontab").
