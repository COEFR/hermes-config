---
name: crypto-trading-bots
description: "Use when un bot que OPERA en un exchange, no solo avisa."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [trading, freqtrade, hyperliquid, binance, backtest, perpetuos, api-wallet]
    related_skills: [trading-signals, hyperliquid, hermes-local-ops]
---

# Bot que OPERA (no que avisa) — freqtrade, backtest y wallets de agente

Cuándo: el usuario quiere un bot que **mande órdenes**. Proyecto aparte del de señales: `~/.hermes/data/crypto-ops/`
(`venv/` con freqtrade, `config*.json`, `user_data/strategies/`, `user_data/logs/`, `NOTAS.md`).
**Leer la `NOTAS.md` antes de tocar nada.** Lo que NO va acá: alertas, seguimiento de señales y su entrega por chat
→ eso es `trading-signals`.

## Regla 0 — separar el bot que avisa del que opera, y reportar cada uno en su idioma
El usuario trata los dos proyectos como cosas distintas y pidió no mezclarlos: nada de copy-trading, ni del bot de
señales ni de los proyectos de análisis dentro del de operación.
- **Bot de señales** → se reporta en **% por alerta, alertas/mes y aciertos**. Nunca capital, equity ni drawdown:
  presentarle esa traducción como si el bot operara lo frena en seco.
- **Bot de operación** → acá sí: **órdenes, posiciones, capital, caída máxima y etapa** (paper/testnet/real).
Equivocar el idioma hace que rechace el reporte completo, aunque los números estén bien.

## Regla 1 — la temporalidad pesa más que la estrategia (y es lo primero que se prueba)
Cinco estrategias escritas desde cero (divergencias de RSI; reversión con RSI + Bollinger; cruce de medias con ADX;
ruptura Donchian; compresión de volatilidad), 2 años de BTC/ETH/SOL:
- en **15m las cinco pierden** (de −2,5% a −16,3%);
- en **4h tres ganan** (la mejor, ruptura Donchian: **+2,90% con 3,97% de caída máxima**, 58 operaciones).
El mecanismo es la comisión, no la lógica: la misma estrategia pasó de **1.022 a 58 operaciones**, y a 0,09% de ida
y vuelta mil operaciones se llevan el capital entero. La fórmula del umbral por comisión está en `trading-signals`
— no duplicarla acá, sólo aplicarla.
Consecuencias operativas:
- Antes de escribir una estrategia nueva, **correr la que ya existe en la TF más larga**. Cambiar el marco temporal
  rindió más que cambiar la idea.
- **Nunca reportar una estrategia sin su temporalidad al lado.**
- Un acierto del 29% con resultado positivo es normal y bueno en momentum (sus ganadoras son más grandes que sus
  perdedoras); un 45% en 15m puede seguir siendo pérdida.
- Las que operan mucho y pierden mucho son la trampa clásica: **más señales no es más ganancia**.
- **Ampliar la lista de pares es la misma trampa por otro camino.** La misma ruptura Donchian pasó de **+2,90% con
  3 pares a −21,08% con 39** (58 → 508 operaciones, caída máxima de 3,97% a 27,36%). El mecanismo es el tope de
  posiciones simultáneas (`max_open_trades`): las altcoins rompen rango a cada rato, así que son las primeras en
  dar señal y **ocupan los lugares** que necesitarían BTC/ETH/SOL — y las que más fallan entran primero. Cuando el
  usuario pida vigilar más pares, **correr las dos versiones y traer el número** en vez de ampliar la lista por
  intuición.

## Regla 2 — nada se cree sin ventana fuera de muestra
Los parámetros se eligieron mirando una ventana, así que esa ventana no sirve para validar. Antes de decir
«funciona», medirlo en un tramo que el ajuste no vio (procedimiento y arnés: `trading-signals`). **Las muestras
chicas que ganan son la alarma, no el hallazgo**: 12 operaciones con +0,96% no dicen nada.

## Regla 3 — credenciales: wallet de agente, nunca la clave de la cuenta
- En Hyperliquid la vía correcta es **«Authorize API Wallet»** (wallet de agente): **firma órdenes y NO puede
  retirar fondos**. Si esa clave se filtra, el daño máximo son malas operaciones, nunca el vaciado.
- **Para consultar saldo y posiciones se usa la DIRECCIÓN PÚBLICA DE LA CUENTA, no la del agente.** La interfaz lo
dice textualmente («The account's public address must be used for info requests»). Pasar la del agente devuelve
una cuenta vacía que parece «no existe» y manda a diagnosticar donde no está el problema.
- Guardar en `~/.hermes/.env` (`HYPERLIQUID_ACCOUNT_ADDRESS`, `HYPERLIQUID_PRIVATE_KEY`), `chmod 600`, y
  **verificar enmascarado** — nunca imprimir el valor ni repetirlo en el chat.
- **Si el usuario pega una clave en el chat**: guardarla, pedirle que borre el mensaje, y decirle que la próxima la
escriba él mismo en el `.env` y avise. Pero **averiguar QUÉ clave es antes de alarmar**: el formato no distingue
una clave de agente de una de cuenta — lo que distingue es de dónde salió (la de agente la genera la interfaz con
un botón «Create API Key» / el panel «API») y **cuánto hay en juego** (consultar el saldo de la cuenta contra la
API antes de hablar de fondos). Alarmar de más obliga a retractarse al turno siguiente y desgasta la credibilidad;
la alarma correcta es la que se mide.
- Nunca pedir la clave por el chat: pedir que la escriba él en `~/.hermes/.env`.
- **Antes de decir «ya podés operar», verificar la cuenta contra la API**: saldo de perpetuos, saldo de spot, y
  **que el agente esté autorizado sobre ESA cuenta** (`extraAgents`). Sin esa autorización Hyperliquid rechaza
  toda orden aunque haya fondos, y el agente autorizado en una cuenta no sirve para otra. Los cuatro sondeos, el
  significado de cada respuesta y la trampa de los *vaults* están en
  `references/cuenta-y-agente-hyperliquid.md`.
- **No confundir «la API contesta» con «es la cuenta correcta»**: cuando hay varias direcciones en juego (agente,
  cuenta, otra cuenta del usuario), preguntar cuál ve en la pantalla principal y confirmar con saldo y movimientos
  antes de apuntar el bot. Es el único paso donde se frena y se pregunta en vez de avanzar.

## Regla 4 — escalera de puesta en marcha: paper → testnet → real con capital chico
1. **Paper** (dinero ficticio, sin claves ni fondos): se arranca acá, y es donde se descubre si el backtest miente
   en vivo.
2. **Testnet** (la misma clave apuntada a la red de prueba): órdenes de verdad, dinero falso.
3. **Real** con **capital chico** ($50-100), y recién si las dos anteriores pasaron.
**Antes de prometer la etapa real, comparar el saldo contra el MÍNIMO POR ORDEN del exchange.** Hyperliquid exige
~$10 por orden y freqtrade le suma el margen (calculó 11,17): con 5,89 USDC **no entra ninguna orden**, por más
que se baje el `stake_amount` a 2 — es un piso del exchange, no una configuración del bot. Cuando eso pasa, la
respuesta correcta a «corré una operación» es **el número que falta** (~$25-30 para dos posiciones), no seguir
intentando variantes. Diagnóstico y firma en el log: `references/cuenta-y-agente-hyperliquid.md`.
Al reportar: decir **en qué etapa está** y **cuál es el requisito que depende del usuario** — y no prometer real
antes de tiempo. Con TF largos, avisar la **expectativa de silencio**: ~1 operación cada 12 días no es un bot roto.

## Regla 5 — las estrategias se escriben acá; los repos son ideas, no código a copiar
Nada de copy-trading ni de pegar la estrategia de un repositorio ajeno. Buscar repos sirve para **sacar ideas y,
sobre todo, leer qué descartaron y por qué**. El usuario pide **muchas estrategias** para analizarlas él: entregar
varias miradas distintas del mismo mercado (dos de reversión, dos de tendencia, una de volatilidad) en lugar de una
sola apuesta.

## Procedimiento
1. Leer la `NOTAS.md`; confirmar `venv` con freqtrade y que los datos estén bajados.
2. **Datos primero, y verificando que sean los completos** (la trampa de la descarga que sólo extiende está en
   `references/freqtrade-operativo.md`).
3. Escribir la estrategia: `can_short=True` si opera cortos, stop y objetivo por ATR (no un % fijo), y protecciones
   (cooldown por par, tope de caída, guardia de stops).
4. **Backtest en la TF larga primero**, después comparar temporalidades; con `--strategy-list` se corren varias de
   una pasada y sale la tabla comparativa.
5. Validar fuera de muestra y **reportar el resultado tal como salió**, incluso si todas pierden.
6. Recién entonces paper trading, y verificar que esté corriendo de verdad (`state='RUNNING'` + latido + `Dry run is enabled` en el log).

## Reportar (preferencias del usuario)
Español, emojis para ordenar las ideas, cierre con **«Conclusión»**. **Veredicto llano primero** («¿es rentable o
no?») y después el detalle. Siempre: qué se hizo, cómo se verificó y qué queda pendiente, avisando en el mismo
mensaje cuando algo no se pudo verificar o cuando me equivoqué — reacciona bien a la corrección honesta y
retractarse a tiempo vale más que sostener.
**Los resultados negativos van primero y sin maquillar**: «las cinco pierden, y este es el número» es el
entregable, no un fracaso que haya que adornar.
**No pedirle permiso para cada paso**: cuando eligió el proyecto y dijo «vos sos el cerebro», la secuencia se
ejecuta y se trae el resultado; se consulta sólo cuando la decisión cambia de rumbo o cuesta plata.

## Archivos
- `references/freqtrade-operativo.md` — comandos, configuración, las trampas de freqtrade (descarga de datos que
  sólo extiende, `--timeframe` en `trade`, órdenes a mercado, `api_server`, base de datos del paper, arrancar /
  verificar / matar el bot por PID, **forzar una entrada y leer el saldo real por la API REST**, dependencias de
  `hyperopt`) y lo ya medido, para no repetirlo.
- `references/cuenta-y-agente-hyperliquid.md` — verificar una cuenta nueva y su wallet de agente antes de operar:
  los cuatro sondeos al `/info`, la trampa de los *vaults* de copy-trading, cómo distinguir «dirección
  equivocada» de «todavía no llegó el depósito», y el **mínimo por orden** que deja un saldo chico sin poder
  operar.
