# Cazar insiders (wallets con info privilegiada) leyendo el lanzamiento

Cuándo: el usuario pide **insiders / info privilegiada** en vez de traders copiables. Cambia el
entregable: a un insider **no se le copia la entrada** (entra antes por definición); lo que sirve es
saber **cuándo suelta** → el veredicto es **VIGILAR 🚨** (avisar el dump), nunca «SEGUIR ⭐». Encaja con
un tracker que solo avisa: no se opera con esto, se mira.

## De dónde sale la evidencia (y el error de ventana)

- El `pairAddress` de DexScreener es el pool de **PumpSwap**: su tx más vieja es la **graduación**. Leer
  ese pool da «primeros compradores post-graduación», no el lanzamiento.
- **Token fresco** (sin migrar): el lanzamiento está en las **primeras tx del mint** — paginar sus
  firmas hasta la más vieja (`before` **dentro** del dict de opciones) y leer las primeras N. Historial
  corto: pocas páginas alcanzan.
- **Token ya graduado: el mint NO sirve.** Sus primeras tx indexadas ya son de PumpSwap (`pAMMBay6…`,
  `BuyExactQuoteIn`) porque las compras de la curva no listan el mint como cuenta → paginar el mint da
  un tramo del medio y un «slot de creación» falso (medido: 40 páginas / 39.852 firmas para aterrizar
  en una tx de ~20 h antes y ya post-graduación). La ventana del lanzamiento está en la **cuenta de la
  curva** = PDA del programa de pump.fun (`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`, seeds
  `[b"bonding-curve", mint]`), y derivarla pide `solders`/`solana-py`. Atajo sin librería:
  `PA.buscar_coin(mint)` trae `bonding_curve` cuando el token sigue en las listas del día, **pero ese
  campo no es la cuenta donde se operó** (medido: su historial son **4 tx** y la primera es
  `MigrateV2`: es la cuenta de la migración). Sin el PDA real, la vía práctica mientras el token es
  joven son las **primeras tx del mint**; si ya está graduado, medir el resultado **por token**
  (dos puntas del historial del mint) en vez de perseguir la curva.
- **Monto de la compra**: algunas tx viejas traen el balance del comprador con
  `uiTokenAmount.uiAmount: null` y `amount: "0"` → leer el monto de las **instrucciones**
  (`BuyExactQuoteIn` de PumpSwap o el `buy` de la curva), no de `pre/postTokenBalances`.
- Un mint **recién creado** puede devolver **0 firmas** (lag del indexador): reintentar, no es «sin
  datos».
- Medido: la ventana de arranque trae ~2× más compradores que las últimas tx (92 contra 45 wallets).
- La creación del token y los buys del bundle caen en **tx separadas del mismo bloque**: leer el bloque,
  no la tx de creación.

## Señales, cómo se miden

| Señal | Medición | Por qué importa |
|---|---|---|
| Entró en el arranque | segundos entre la tx más vieja del mint y su compra (≤120-180 s) | información de primera mano |
| Recibió sin pagar | Δ token > 0 con \|Δ SOL\| < 0,01 SOL, **filtrado por tamaño** | allocation sin riesgo |
| Vínculo con el dev | el `creator` del token (RugCheck) entre los fondeadores de la wallet | acceso directo al supply |
| Win rate ≥90 % con ≥10 cerradas | auditoría profunda (`auditar_wallet`) | firma clásica del bundle |

**Filtrar por tamaño o el informe se llena de polvo**: en un token aparecieron **210 receptores
«gratis»** y casi todos eran migajas de spam que nunca operaron; exigir **≥0,05 % del supply**
(`token.supply` de RugCheck) deja solo al que se llevó un pedazo real. Sin ese filtro la lista de
candidatas pasa de decenas a cientos de wallets irrelevantes.

## Puntaje de señal (0-10) y etiqueta

`2 × (% del supply recibido gratis) + 2 × (nº de tokens donde entró en el arranque) + 2 si ≥40 % de
posiciones sin compra + 1,5 si wr ≥90 % con ≥10 cerradas + 2 si el creador la fondeó` (tope 10).
La etiqueta final sale de `clasificar_wallets.etiquetar()` (INSIDER por ≥40 % sin compra, o ≥25 % con
wr ≥90 %).

## No asumir que «entrar temprano» = ganar

Los que entran en el arranque **pagando** y aparecen en las primeras posiciones de la lista acumulan
**3 posiciones cerradas, 0 % de aciertos y entre −30 y −59 SOL** cada uno. La señal de info
privilegiada **no** implica rentabilidad: llevarse supply gratis (bundle) es otra cosa que comprar
primero y comerse el dump. Reportar **señal y resultado por separado**, y no prometer «insider
rentable».

## Herramienta y salida

`buscar_insiders.py` (mismo directorio del proyecto; reusa `buscar_10._sigs_del_pool`,
`auditor_wallets.auditar_wallet` y `clasificar_wallets.etiquetar`) deja `insiders.json` con `wallet,
señal, etiqueta, arranques, gratis, gratis_pct, cerradas, pnl, win_rate, hold, sin_compra, vinculo_dev,
fondeo`. Flags: `--tokens --por-pool --arranque --auditar --tx --creadores`. Correr en **background con
aviso**; `--creadores` suma una llamada a RugCheck por token (necesaria para el vínculo con el dev).

`insider_token.py <mint>` es el detector **por token** (no por wallet): compras del slot de creación
(≥3 = bundle), % del supply comprado en el bloque cero y clúster de fondeo del bloque cero → veredicto
BUNDLE / sin bundle. Es el que se engancha al radar para que **cada token alertado traiga el veredicto
«¿bundle?» automático** (saber si el lanzamiento está cargado antes de mirar el gráfico).
