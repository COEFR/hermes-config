# Qué ya existe y qué dice la evidencia (investigado 2026-09-20)

## Bots open source con el mismo enfoque

| Proyecto | Qué hace | Lección para nosotros |
|---|---|---|
| `SpiralDevelopment/RSI-divergence-detector` (GitHub) | Detecta divergencias de RSI multi-par por temporalidad y postea alcistas/bajistas + sobrecompra/sobreventa a Telegram | Es el mismo producto que `signals.py`; la diferencia es que nosotros medimos antes de construir y etiquetamos cada alerta con su histórico |
| `aashir-athar/MiND-Shot` (GitHub) | BTC/ETH serverless en GitHub Actions; 5 estrategias de reversión a la media **con gate `ADX(14) < 25`**, 4h, long y short, elegidas de un barrido de 1.620 configuraciones y validadas fuera de muestra; 326 trades, 72.7% de aciertos | Confirma el hallazgo propio: el gate útil para una señal contra-tendencia es **ADX bajo (rango)**, no ADX alto. Y valida el patrón "barrer configuraciones → validar fuera de muestra → publicar solo si supera el baseline" |
| `hschickdevs/Telegram-Crypto-Alerts` (GitHub) | El bot de alertas por Telegram más popular: precio + indicadores (RSI, MACD, BB, MA) vía Taapi.io, con cooldown por alerta | El cooldown por alerta es práctica estándar, no invento nuestro |
| `vmartinv/crypto_alert_bot` (GitHub) | DSL para crear condiciones sobre precio e indicadores (Binance API) | Alternativa "configurable por el usuario" frente a nuestro set fijo de flags |
| Frameworks | `vectorbt`, Freqtrade, Jesse, OctoBot (hay skill de vectorbt en skills.sh) | No usados: el arnés propio en Python puro alcanza y evita dependencias |

## Evidencia publicada (y cómo coincide con lo medido acá)

- **EdgeStacker — "Does RSI actually work? We tested 6 RSI strategies"** (28 tickers, walk-forward + 100 corridas de entradas aleatorias): el RSI(14)<30 y **la divergencia alcista "busted"**; la divergencia disparó 3 veces en una década en su mejor ticker, así que "nadie tiene una muestra confiable". Regla que adoptan: *contar las operaciones antes de creer un backtest*. → **Coincide**: nuestra divergencia sola no tiene ventaja y las muestras buenas son de 12-60 señales.
- **CoinQuant — divergencia de RSI en BTC (4,5 años)**: 9 operaciones, −46.1%, 22.2% de aciertos, PF 0.31. Conclusión textual: *"la divergencia marca que el momentum se desacelera, no que la tendencia haya girado"*. → **Coincide** con nuestro "momentum desacelerando ≠ giro" y con el motivo del cooldown.
- **futuresai.io — divergencias RSI en 4h, BTC+ETH, 2024** (270 operaciones, la muestra más grande que encontramos): 52.6% de aciertos, PF 1.30, +31.2% anual. Mejoras que reportan: **+8% de win rate filtrando divergencias cerca de soportes/resistencias**, **+0.3 de Sharpe con confirmación de volumen**, y **las divergencias alcistas rindieron 1.4× mejor PF que las bajistas**. → **Coincide** el valor del volumen; **advierte** que nuestro bot es solo-short, el lado más débil en esa muestra. **Medido en este equipo con el mismo arnés (`shorts_adx.py --side long`) esa afirmación NO se replica**: los longs dan 28.6% al objetivo y −0.39% por alerta en el conjunto (vs +0.50% de los shorts), y el mejor long (4h premium: 54.5%, +1.17% por alerta, mitades +0.12%/+1.57%) queda muy por debajo del mejor short (4h premium: 58.3%, +4.30%, mitades +5.02%/+3.57%). Los longs generan más señales (15.4/mes vs 12.4) pero peor valor. **Lección**: una conclusión publicada sobre otro mercado/período/implementación no se adopta sin medirla en los datos propios — y acá el sesgo short del bot quedó respaldado, no refutado.
- **quant-signals.com — ADX en 4.236 operaciones** (varios activos): el **filtro ADX redujo la frecuencia 60-80% sin mejorar consistentemente la rentabilidad**; en BTC diario el PF cayó de 1.56 a 1.16 al añadirlo; umbral 20 mejor que 25+; "el ADX llega tarde". → **Coincide exactamente**: medimos que el ADX solo empeora y que recorta mucho la frecuencia.
- **quantifiedstrategies.com — RSI + ADX**: complementarios; para ADX conviene lookback corto (5-10) y umbrales 30-40; para RSI de reversión, lookback corto (2-3). → Sugerencia no probada acá: mantener nuestro ADX(14) en 25 y probar ADX(7).
- **fxglory — test educativo de 5 setups ADX+RSI** (1.579 operaciones): esperanza −0.3367R; los cinco negativos. → Refuerza que la combinación no es rentable por sí sola.
- **pickskill — filtro de 3 indicadores**: ADX como filtro de régimen (25/20) y nota específica de cripto: usar umbrales **RSI 80/20** en vez de 70/30 porque las tendencias en cripto son más fuertes. → No probado acá.

## Tres mejoras que la evidencia sugiere y todavía no medimos

1. **Confluencia con niveles**: exigir que la divergencia ocurra cerca de un soporte/resistencia (o del extremo de un canal de Donchian) — la única fuente con muestra grande reporta +8% de win rate.
2. **Confirmación multi-temporalidad**: que la señal de 15m esté alineada con la de 4h (aparece en dos fuentes).
3. **Umbrales RSI adaptados a cripto** (80/20 en vez de 70/30) para el filtro de extremo.

Cada una se mide con `addons.py` (mismo arnés, mismas condiciones, corte en dos mitades) antes de meterla en el bot.

## Sobre las skills del hub

- Preferir las **oficiales** (`official/...`) antes que las comunitarias: las comunitarias (`clawhub`, `skills.sh`) no están auditadas. Instalar con `hermes skills install <id> --yes` (sin `--yes` pide confirmación y sin TTY se cancela).
- Instaladas para este trabajo: `official/blockchain/hyperliquid` (datos de mercado, funding y revisión de operaciones de perpetuos → útil para el lado short) y `official/finance/stocks` (cotizaciones e histórico vía Yahoo, cripto incluido).
