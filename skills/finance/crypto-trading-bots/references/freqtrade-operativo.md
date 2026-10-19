# freqtrade — comandos, configuración y trampas de operación real

Receta viva del proyecto `~/.hermes/data/crypto-ops/` (`venv/bin/freqtrade`, `config.json`,
`config-backtest.json`, `user_data/strategies/`, `user_data/logs/`).

## Bajar datos (y confirmar que son los completos)

```bash
venv/bin/freqtrade download-data --config config-backtest.json --days 730 --timeframes 15m 1h --erase
venv/bin/freqtrade list-data --config config-backtest.json      # qué quedó, por par y temporalidad
```

- **Sin `--erase` (o `--prepend`) la descarga sólo EXTIENDE desde la última fecha que ya hay.** El comando termina
  en verde y avisa en una línea fácil de saltear (`Use --prepend to download data prior to <fecha>`) que trajo sólo
  la cola: se pidieron 2 años y quedaron 60 días. **Leer esa línea y confirmar el rango con `list-data`** antes de
  dar los datos por bajados.
- Los perpetuos van como `BASE/USDT:USDT` y quedan en `user_data/data/<exchange>/futures/` con sufijos por tipo:
  `-15m-futures.feather`, `-1h-funding_rate.feather`, `-1h-mark.feather`.
- **El `funding_rate` viaja junto con las velas y es la pieza que hace válido el backtest de perpetuos**: sin él,
  cualquier estrategia que mantenga posiciones horas está midiendo mal el costo de sostenerlas. Sirve para dos
  cosas: cobrar/perdonar el funding en la simulación y diseñar una señal que **no** dependa de indicadores clásicos
  (funding en extremo), que es donde hay menos competencia.
- El histórico propio del exchange puede no estar disponible por vía gratuita (los planes de datos históricos
  contestan que hace falta un plan pago) → el backtest se hace con **velas de Binance** de perpetuos USDT. Son un
  proxy del mercado, no el libro del exchange donde se va a operar: decirlo al reportar, no venderlo como idéntico.

## Configuración: las cuatro que rompen la corrida

- **Órdenes a mercado**: `entry_pricing.price_side` debe ser `"other"`. Con `"same"` freqtrade se niega porque no
  puede usar el mismo lado para el precio de referencia y para la orden.
- **El `timeframe` del config PISA al de la estrategia.** Si el config dice `15m` y la estrategia declara `4h`,
  arranca en 15m. Verificar el TF que el bot **anuncia al arrancar**, nunca el del archivo de la estrategia.
- **`freqtrade trade` NO acepta `--timeframe`** (sí `backtesting`): aborta con
  `unrecognized arguments: --timeframe 4h` y el proceso no arranca — el TF se cambia en el config.
- Si se habilita el `api_server` exige `listen_ip_address`, `listen_port`, `username`, `password`,
  `jwt_secret_key` (≥32 caracteres) y `ws_token` (≥32).
- En comparaciones entre estrategias, `--strategy-list A B C` corre todas de una pasada y devuelve la tabla
  comparativa (operaciones, resultado, acierto, caída máxima) — es la forma de ver la temporalidad y la estrategia
  juntas.

## La lista de pares no está donde parece

`download-data` y `backtesting` toman los pares **del config que se les pasa**, no de la lista que uno cree haber
editado. Si al agregar pares el resultado **no cambia** (mismo número de operaciones), es la señal de que no los
está leyendo: pasar `--pairs "BTC/USDT:USDT" "ETH/USDT:USDT" ...` explícito y **comparar el conteo de operaciones
antes y después** — es el único control de que la lista entró en la corrida.

## Forzar una operación y ver el saldo real que ve el bot (API REST)

La entrada forzada **no se hace por CLI**: se hace por la API REST, así que hay que habilitarla en el config
(`api_server.enabled: true`, con `username`/`password`) y **relanzar el bot**.

```bash
curl -s -u "$U:$P" http://127.0.0.1:8080/api/v1/ping      # {"status":"pong"}
curl -s -u "$U:$P" http://127.0.0.1:8080/api/v1/balance   # lo que ve el bot, con `is_bot_managed`
curl -s -u "$U:$P" -X POST http://127.0.0.1:8080/api/v1/forceenter \
  -H 'Content-Type: application/json' -d '{"pair":"BTC/USDC:USDC"}'
```

- **`/balance` es la verificación más fuerte de «el bot ve la plata»**: devuelve `free`/`balance` de la cuenta con
  `is_bot_managed: true`, medido por el propio bot. Vale más que leer el log.
- **Hay que declararla**: sin `force_entry_enable: true` en el config la API contesta `Force_entry not enabled.`
- Cuando la orden igual falla, **la respuesta de la API no explica el motivo: está en el log del bot** — ahí
  aparece la línea que resuelve el caso (ver «el mínimo por orden» en `cuenta-y-agente-hyperliquid.md`).

## Arrancar, verificar y matar el bot

```bash
cd ~/.hermes/data/crypto-ops && mkdir -p user_data/logs
nohup venv/bin/freqtrade trade --config config-backtest.json \
  --strategy RupturaDonchian --db-url sqlite:///user_data/trades_paper.sqlite \
  > user_data/logs/paper.log 2>&1 &
```

- **Verificar de verdad, no por «no dio error»**: en el log tienen que estar las tres cosas — `state='RUNNING'`, un
  `Bot heartbeat` y **`Dry run is enabled`**. Sin la última está operando con dinero real aunque no lo parezca: es
  lo primero que se confirma en la etapa paper.
- **Cada etapa con su propia base** (`--db-url sqlite:///user_data/trades_paper.sqlite`) para no mezclar el paper
  con las corridas de backtest.
- El log se lee recortando las líneas (`cut -c1-130`) y volcando a un archivo temporal para leerlo después: las
  líneas de freqtrade son larguísimas y ensucian el contexto.
- **Matarlo por PID, nunca por nombre**: `pkill -f "freqtrade trade"` puede matchear el intérprete que hospeda el
  gateway, así que el guardián lo bloquea. Usar
  `for pid in $(ps -eo pid,args | grep "[f]reqtrade trade" | awk '{print $1}'); do kill "$pid"; done`
  y confirmar que quedó uno solo (dos procesos del mismo bot ya causaron problemas de conexión).
- **Con TF largos la primera operación puede tardar días** (~1 cada 12 días en 4h): un bot sin operaciones no es un
  bot roto, y hay que decirlo al entregarlo para que no lo lea como falla.

## Hyperopt

```bash
UV=/home/ubuntu/.hermes/bin/uv     # `uv` no está en el PATH de los shells en segundo plano: llamarlo por ruta
$UV pip install --python venv/bin/python optuna filelock scikit-optimize scipy
venv/bin/freqtrade hyperopt --config config-backtest.json --strategy <Estrategia> \
  --hyperopt-loss SharpeHyperOptLoss --spaces buy sell --epochs 100 \
  --timerange 20241101- --pairs "BTC/USDT:USDT" "ETH/USDT:USDT" "SOL/USDT:USDT"
```

- Las dependencias **no vienen con freqtrade** y el error las nombra **de a una** (`No module named 'filelock'`,
  después `'optuna'`): instalarlas **las cuatro de una vez**, no relanzar por cada una.
- Los parámetros de una estrategia escrita a mano se eligen **a ojo** hasta que se optimizan: decirlo al reportar,
  y **validar el resultado en un tramo que la optimización no vio** antes de darlo por bueno.

## Leer el resultado del backtest (y mostrarlo cuando pide «hacé una operación»)

```bash
ls -t user_data/backtest_results/     # los resultados salen como .zip, no como .json suelto
```

- **Se guardan comprimidos** (`backtest-result-<fecha>.zip` en `user_data/backtest_results/`) y adentro llevan el
  JSON, el config y la estrategia congelados. Descomprimirlos con la librería **`zipfile` de Python** (stdlib,
  siempre disponible) en lugar de depender de un `unzip` del sistema.
- El JSON trae `strategy.<Nombre>.trades[]` con `pair`, `is_short`, `open_rate`/`close_rate`,
  `open_date`/`close_date`, `profit_ratio` y **`exit_reason`**. El campo que más enseña es `exit_reason`: cuando
  las perdedoras salen **todas del mismo tamaño** por el stop y las ganadoras son varias veces más grandes por el
  objetivo, la asimetría está funcionando y el acierto bajo deja de importar.
- **Cuando el usuario pide «hacé una operación» y todavía no hay fondos**, un «no puedo» es una respuesta
  incompleta: mostrarle la lista concreta de las últimas operaciones que la estrategia habría tomado (entrada,
  salida, resultado y motivo de cierre) más el neto del período. Se corre un backtest sobre la cola reciente
  (`--timerange <hace ~60 días>-`) y se leen los trades del `.zip`. Eso responde la pregunta de verdad: *qué haría*
  con su plata.

## Ya medido — no repetirlo

Cinco estrategias (divergencias de RSI · reversión RSI+Bollinger · cruce de medias con ADX · ruptura Donchian ·
compresión de volatilidad) sobre 2 años de BTC/ETH/SOL: **negativas las cinco en 15m** (la peor, −16,3% con 1.022
operaciones) y **tres positivas en 4h** (ruptura Donchian +2,90% con 3,97% de caída máxima y 58 operaciones;
cruce de medias +0,96% con 41,7% de acierto; compresión +0,18%). El orden de magnitud de las operaciones es lo que
decide: pasar de 1.022 a 58 operaciones con 0,09% por lado es toda la diferencia.
