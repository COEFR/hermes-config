# De dónde salen las candidatas: listas públicas y herramientas de terceros

El descubrimiento propio (compradores reales del pool) rinde **0-2 candidatas por ronda**. Antes de
gastar cupo en otra ronda, revisar si el trabajo ya está hecho: hay datasets públicos con cientos de
wallets ya etiquetadas. Lo que ninguna lista trae es el **veredicto**: eso lo pone el motor propio
(0-10 con `pnl_sin_top3_sol` + chequeo de vida + historial profundo).

## Dataset reutilizable: `nirholas/kol-quest` (agrega GMGN + KolScan)

- Open source, sin key. Archivo:
  `https://raw.githubusercontent.com/nirholas/kol-quest/main/site/data/solwallets.json` (~11 MB).
- Estructura: `interceptorRaw.walletsBySmartMoney` (164), `walletsByKOL` (410), `walletsByTopDev` (197),
  `walletsBySniper` (49), `walletsByFreshWallet` (592), `kol.wallets` (290), más `walletsAll`,
  `tokensAll` y `meta` con la **fecha de captura** (mirarla antes de creerle nada: la copia vista era de
  meses atrás).
- Campos por wallet: `wallet_address`, `realized_profit_1d|7d|30d`, `winrate_1d|7d|30d`,
  `avg_holding_period_1d|7d|30d` (**en segundos**), `txs_*`, `buy`/`sell`, `last_active` (unix),
  `twitter_username`.
- Perfil que trae: entre las rentables 30 d, la mayoría tiene holds de **horas o días** (mediana ~28 h)
  → convicción/swing, un juego distinto al pump.fun de 1 minuto. Sirve para seguir convicción y para
  detectar dumps, no para copiar scalping.

### Embudo medido (574 wallets únicas)

1. Filtro con el dataset (prof30d > 0, wr30d ≥ 50 %, ≥30 ops, hold ≥ 120 s) → **104**.
2. Vida con RPC (último movimiento en 14 días) → **74 activas**, **40 con ≥1 SOL**, **24 con ≥20 SOL**.
3. Auditoría propia (0-10) de las mejores vivas → **es el paso que decide**; sin él no se recomienda.

Script del proyecto que hace 1-3: `~/.hermes/data/memecoins/verificar_publicas.py`
(`--vida` = cribado barato; `--auditar N --tx 400` = pasada propia). Salidas: `candidatas_publicas.json`,
`publicas_vivas.json`, `publicas_verificadas.json`. Ojo con el cupo: la pasada profunda de N wallets ≈
N × tx × 10 créditos de Helius.

## Herramientas de terceros que valen (y qué copiarles)

| Fuente | Qué es | Qué tomar |
|---|---|---|
| `AtlasOnchain/Atlas` | mapea flujo de capital en Solana sobre **Helius** | la pregunta clave: la wallet fue **origen** (llegó primera) o **propagación** (ya la copiaron)? Un aviso vale mucho más si nadie entró antes |
| `GuardME/wallet-tracker` | wrapper de la OpenAPI de GMGN + JSON-RPC | **co-entrada**: exigir comprador temprano en **≥2 tokens ganadores**, no en uno; puntuar por **comportamiento** (6 dimensiones) en vez de PnL crudo |
| `ImMike/crypto-wallet-address-labels` | datasets de etiquetas (CEX, programas, scam) por cadena | automatizar el filtro de stop-nodes hoy hardcodeado |
| `yegor104/pumpfun-tracker` | tracker en vivo con PnL por wallet | continuidad curva → AMM (no perder el hilo al graduar) |
| `haccer/pumpfun-research` | utilidades Python + Helius para pump.fun | contraste de métricas propias |
| `buddies2705/awesome-memecoin-trading` | índice de 250+ herramientas | mapa para buscar alternativas sin key |
| GMGN (blog/UI), kolscan.io, Cielo, Nansen | tracking de smart money/KOL, gratis en web | avisos y listas; ninguna API sin key |

## Lo que dice la comunidad (vale como advertencia, no como dato)

- GMGN mismo avisa de **exit liquidity baiting**: hay wallets marcadas como "inteligentes" para que el
  rebaño las copie y les vendan encima.
- Lo normal entre los que ganan son estrategias **no replicables**: HFT/scalping, acceso a dev/bundle,
  moonshots — coincide con lo medido: los que más ganan son bots de 1 minuto.
- La conclusión repetida en foros no es "seguí a la wallet grande" sino **quién fue primero** y
  **cuántos independientes coincidieron** en el mismo token.
