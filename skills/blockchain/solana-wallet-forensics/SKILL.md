---
name: solana-wallet-forensics
description: "Use when auditando o rastreando wallets on-chain."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [solana, wallets, forense, insider, clustering, copy-trading]
    related_skills: [memecoins-pumpfun, trading-signals]
---

# Forense y auditoría de wallets on-chain (Solana)

Cuándo: el usuario pasa una dirección y quiere saber **de dónde vino la plata, qué operó, y cuáles
wallets de esa red sirven de verdad**. Implementación de referencia en `~/.hermes/data/memecoins/`:
`wallet_forense.py` (una wallet + su red, ventana corta), `forense_profunda.py` (historial completo:
**una sola pasada** de `getTransaction` + caché en disco, para wallets de 1.000+ tx),
`auditor_wallets.py` (auditoría masiva), `clasificar_wallets.py` (etiquetas), `wallet_tracker.py`
(seguimiento), `red_wallets.py` / `buscar_10.py` / `evaluar_wallet.py` (descubrir candidatas entre los
**compradores reales del pool** y puntuarlas 0-10), `cazar_calls.py` (ráfagas de compra coordinada =
calls de grupos de alpha: `--tokens --pool-tx --ventana --min-wallets --min-sol --min-calls`).
**Extender esos scripts, no reescribirlos.**
Solo datos públicos: RPC (público o la capa gratis de **Helius**) + RugCheck + DexScreener, sin tokens
de LLM.

No toda dirección que te pasan es un trader: cómo reconocer y reportar wallets **receptoras, farm o
fee-recipients de bots** (y por qué la pasada corta las etiqueta «SIN DATOS»):
`references/wallets-de-automatizacion.md`.

## Procedimiento: una wallet que te pasan

0. **Medir antes de bajar** (≈5 llamadas): `getAccountInfo` (¿existe la cuenta?), `getBalance`,
   `getTokenAccountsByOwner` (cuántas cuentas de token y cuántas con saldo > 0) y el **paginado
   completo** de `getSignaturesForAddress` (tamaño real del historial + fecha de la firma más vieja).
   Con eso se elige la profundidad, se evita gastar 20 minutos de RPC en una wallet que no opera y se
   detecta al toque la que no es un trader.
1. **Firmas** del histórico (`getSignaturesForAddress`, `--tx N`) → `getTransaction(jsonParsed)`.
2. **Flujos de SOL**: delta `postBalances − preBalances` por cuenta; excluir programas y cuentas de
   infraestructura (curva/pool/fee); ignorar `|Δ| < 0.01 SOL` (las wallets reciben polvo constante).
3. **Tokens operados**: `meta.pre/postTokenBalances` + Δ SOL del índice de la wallet → token sube y
   SOL baja = **compra**; token baja y SOL sube = **venta**; token se mueve y SOL no = polvo/
   transferencia (descartar). Sin esto, los airdrops se cuentan como "compras".
4. **Posiciones cerradas** por mint: PnL realizado = SOL vendido − SOL comprado. Tenencias actuales
   con `getTokenAccountsByOwner` para saber si sigue dentro.
5. **La red**: quién la fondeó, a quién le mandó la plata y las **hermanas** (fondeadas por el mismo
   padre). Descartar hubs antes de agrupar.
6. **Clasificar cada miembro** de la red (no solo la consultada) y cerrar el informe con una sección
   de **SEGUIR / VIGILAR / EVITAR** en una línea por wallet.

## Forense profunda cuando la wallet mueve 1.000+ tx

`wallet_forense.py` baja cada tx **dos veces** (flujos + tokens): con historiales largos se pasa de 7
min y muere por timeout. Para esos casos usar **`forense_profunda.py`** (una sola pasada + caché
`cache_tx_<prefijo>.json`): releer el caché es gratis, así que se reanaliza o se cambian umbrales sin
volver a tocar el RPC. El RPC público rinde **0,5-1 tx/s** con los crons corriendo encima (1.200 tx ≈
20-25 min) → background con aviso, nunca foreground.

- **Paginado**: `before` va **dentro del mismo dict** que `limit`
  (`[dir, {"limit":1000,"before":sig}]`). Con dos dicts separados el RPC falla en silencio y parece
  que la wallet tiene solo 1.000 tx (medido: tenía 10.000+).
- **Nunca cerrar el informe sin cubrir todas las claves**: un `return` temprano de la función de
  métricas (el caso «0 posiciones cerradas») que no incluya las claves que usa el generador de texto
  revienta con `KeyError` **después** de la parte cara. Escribir el JSON **antes** de imprimir el
  texto, y probar el caso sin posiciones con una corrida real.

## Patrón «wallet de granja»: cuando «SIN DATOS» significa «no es un trader»

Señales que aparecen juntas (ninguna sola alcanza): `getAccountInfo` = **null** (0 lamports, la cuenta
no existe), **delta de lamports exacto = 0** en todo el historial, **nunca es `keys[0]`** (el fee
siempre lo paga un bot), **30-45% de tx fallidas con `InsufficientFundsForRent`**, y **200-300 cuentas
de token con 100+ saldos** que recibe regaladas y **nunca vende**. Es una wallet de automatización /
granja: no compra ni vende con su plata. Veredicto: **no sirve para copiar, no se carga al tracker**
(no es un caso de «ampliar la ventana»).

Lo útil de esa red son los que la mueven: el **distribuidor** que le manda tokens y crea las cuentas
A-TA pagando los fees, y las wallets **consolidadoras** (mismo perfil, 200+ cuentas de token) que
reciben lo suyo. Verificado en una: las únicas tx que la wallet **firma** son depósitos al depósito de
**Relay** (`99vQwtBwYtrqqD9YSXbdum3KBdxPAVxYTaQ3cfnJSrN2`, `Instruction: DepositToken`) → la
mercancía sale de Solana por el puente.

## Nunca reportar el PnL crudo cuando la cobertura tiene huecos

Si faltan las compras, cada venta queda como «cobró sin haber comprado» y el PnL reconstruido se
**infla**: medido en la misma wallet **+153 SOL crudo** contra **−3,8 SOL y win rate 28 %** mirando
sólo las posiciones con **compra Y venta vistas**. Reglas: (1) calcular el PnL y el win rate aparte
para las «completas», (2) reportar las «sólo venta» como costo desconocido, no como ganancia,
(3) decir cuántas completas hay: con 18 no hay veredicto, es un indicio.

## Trampa nº 1 del RPC: las transacciones v1 y las cuentas cargadas

Pedir `getTransaction` con `maxSupportedTransactionVersion: 0` cuando la red ya trae tx **v1** no
da error de red: el nodo devuelve un error **por transacción** o `null` según el host, y el historial
de una wallet activa **parece vacío**. Medido sobre la misma docena de tx: con 0 → **1 de 14** con
datos; con **1 → 14 de 14**. Usar siempre una constante (`MAX_VERSION = 1`) en cada llamada.

En las tx versionadas parte de las cuentas vienen de lookup tables (`meta.loadedAddresses`): la lista
de cuentas **no** es `message.accountKeys`, hay que concatenar estáticas + `writable` + `readonly` o
los índices se desalinean con `pre/postBalances` y el delta leído es de **otra cuenta**. Un helper
único (`cuentas_tx`) usado por todos los scripts evita el error repetido.

Síntoma a recordar: «cobertura bajísima» (195 de 1.172 tx) y «muchísimas tx sin datos» suele ser
esto, no el rate limit. Antes de culpar al host, probar subir la versión.

## Trampa nº 2 del RPC: el `commitment` de las tx RECIÉN confirmadas

Leer una transacción en el mismo instante en que el WebSocket la avisa devuelve **`null`** si la consulta va con
el commitment por defecto (`finalized`): el aviso de `logsSubscribe` llega cuando la tx está **confirmada**, y en
`finalized` el nodo todavía no la tiene (unos 13-30 s después sí). El síntoma engaña porque **no hay error**:
HTTP 200 con `result: null`, la firma es real y el aviso llegó, así que desde afuera se lee como «esa wallet no
compró» o «la transacción no existe». Medido consultando la misma firma dos veces con un segundo de diferencia:
`finalized: False | confirmed: True` en 4 de 4. Regla: **`"commitment": "confirmed"` en toda lectura de una tx
fresca** (el default queda sólo para el historial viejo). Cuidado con el 429: pedir la misma firma dos veces
seguidas ya dispara el rate limit del plan gratis → un solo pedido con el commitment correcto y, si falla, **un
reintento con una pausa corta**, nunca un bucle de reintentos inmediatos.

## RPC: host por método, y Helius para no pelear con los límites

| Host | `getSignaturesForAddress limit=1000` | `getTransaction` bajo carga |
|---|---|---|
| Helius (key gratis en `.env`) | 1.000 firmas | sin límite práctico, acepta v1 |
| `api.mainnet-beta.solana.com` | **1.000 firmas** | rápido, pero **429** tras miles de llamadas |
| `rpc.solanatracker.io/public` | **112 firmas** | aguanta (~0,26 s/tx) |
| `solana-rpc.publicnode.com` | 565 firmas | sirve, con límite |
| `solana.api.onfinality.io/public` | 429 | 429 |

Sin key, elegir el orden de hosts **según el método** (firmas → oficial; `getTransaction` →
solanatracker): paginar contra un host que corta la lista hace que una wallet de 9.000 tx parezca
tener 112. Con la capa gratis de Helius (1M créditos/mes, `getTransaction` = 10 créditos, sin tarjeta)
desaparecen el 429, el corte de historial y la falta de cobertura: una wallet de 9.000 tx cuesta ~9 %
del cupo mensual. **Antes de dar un informe por «incompleto», ofrecer la key al usuario.**

**Presupuestar sí, pero LEER el cupo real antes de declararlo agotado.** El modelo de 10 créditos por
tx es una **cota superior**: la estimación desde el conteo de tx **sobreestima ~10×**. Medido con el
usuario: después de una jornada completa de caza (dos rondas de descubrimiento, caza de anillos,
auditoría de una lista pública y varias auditorías profundas de 1.000+ tx) el tablero de Helius marcaba
**76.985 de 1.000.000 (7,7 %)** mientras la estimación interna decía 92-96 %. Con ese error se estuvo a
punto de decirle que hacía falta plan pago y de frenar una corrida que sobraba (923 k créditos libres).
**Regla: antes de afirmar «ya no alcanza» o de proponer plan pago, pedir el número real** — el usuario
lo lee en `dashboard.helius.dev` → «Credit usage» (trae también los días restantes del ciclo).

**El sondeo del tracker es el gasto que sí importa: contarlo antes de cargar wallets.** 10 créditos por
`getSignaturesForAddress` por wallet y por pasada → **5 wallets a `*/3` min ≈ 50 créditos/pasada ≈
24.000/día ≈ 720.000/mes = 72 % del plan gratis**. Al cargar N wallets, calcular N×10×pasadas/día,
decirle el número al usuario y proponer la frecuencia (bajar a `*/10` ≈ 216.000/mes) **antes** de
dejarlo corriendo; tocar el crontab requiere su OK.

**Y ese tope crece solo: al registro de wallets lo alimenta la detección, no el usuario.** Medido: con el registro en
852 wallets, la patrulla (`*/3`, 3 firmas por wallet) costaba **~2,5 M de créditos/día** — más que todos los demás
componentes juntos — sin que ningún contador lo marcara, porque nadie eligió «852»: lo hicieron crecer la cosecha y
las cohortes. La patrulla se acota por **selección**, no por «todas las conocidas»: sólo las wallets copiables y las
de los grupos 🟢/🟠 (los 🔴/🟡 se siguen midiendo por la cosecha), cada `*/6` y con menos firmas. Regla: cada vez que
el registro crezca, recalcular N×10×pasadas/día — el gasto de la patrulla es **proporcional al registro**, no una
constante que ya se presupuestó.

**El cupo es UNO solo para todos los procesos: sumar los componentes antes de agregar otro.** Medido con
los tres corriendo (vigilante en vivo ≤12 k/día + detector de ráfagas del radar ~21 k/día + tracker
~24 k/día) el conjunto da **~57 k/día ≈ 1,7 M/mes**, por encima del 1 M gratis — y cada script con su
propio tope diario no lo ve, porque cada tope se mide solo a sí mismo. Al proponer un componente nuevo,
presentar la tabla de los tres, la **palanca** (bajar la frecuencia del tracker) y el plan pago como
alternativa; el usuario decide con el número real de su tablero.

**Instrumentar cada componente con su propio contador, y medirlo ANTES de recortarle nada a nadie.**
Medido en una jornada con todo encendido: **247 k créditos en el día, de los cuales 241 k (98 %) eran
del detector de ráfagas del radar** (8 candidatos × 40 tx por pasada) y sólo ~5 k del vigilante — el
que se comía el cupo no era, ni de lejos, el sistema «nuevo». Sin contadores por componente se recorta
al que no gasta (o al que el usuario sí quiere) y el gasto no baja. Regla: cada script anota los
créditos que consume en su propio JSON, un `consumo.py` los suma por día y por ciclo, y **cualquier
recorte se propone con esa tabla delante** — nunca por intuición de cuál «debe» ser el caro.

**Varias keys de Helius: se suman y se rotan solas.** Guardar cada una en `.env` como
`HELIUS_API_KEY`, `HELIUS_API_KEY_2`, … y hacer que `rpc()` **rote el orden de los hosts por llamada**
(no poner una primera y la otra de respaldo: así la segunda queda sin usar y el cupo «extra» no
existe). N keys = N × 1 M/mes y N × 10 req/s, así que cuando el usuario pida más volumen o más ritmo,
la respuesta accionable es **pedirle otra cuenta gratis**, no reducir los sistemas. Y decirle dos cosas
del plan gratis: **los créditos NO se acumulan entre ciclos** (se reinician en la fecha de renovación:
usarlos es mejor que perderlos) y el tablero (`dashboard.helius.dev` → Credit usage) trae los días
restantes.

**Y si el usuario pide NO limitar el gasto, no reintroducir topes.** Pidió «no limites el Helius»: en ese modo
los topes quedan sin efecto y se mantienen solo los frenos **lógicos** (no reevaluar el mismo token antes de
~5 min, no repetir el aviso del mismo token antes de ~15 min). Decirle el **ritmo medido** y cuándo se agotaría
el plan gratis (~2-4 días a 200-400 k/día) y ofrecer el plan pago — pero **no volver a proponer topes, ni a
frenar una corrida, por cuenta propia**. Lo mismo vale para el **consumo de un detector**: bajarle los
umbrales o los candidatos por pasada «para cuidar el cupo» es recortarle las señales al usuario, y eso ya lo
rechazó explícitamente («no bajes el consumo de las calls»). Si hay que liberar créditos, proponer de dónde
sacarlos **con la tabla de consumo delante** y esperar su OK; si pide **maximizar**, subir todo y decirle el
ritmo y los días que dura (los créditos que no se usan se pierden al renovar el ciclo).

Los nodos gratis devuelven **`null` para las tx viejas** (y `null` no es excepción: hay que probar los
otros hosts antes de descartar). Con throttling la cobertura cae fuerte (1.172 tx → 195 leídas), así
que el descargador va en **dos pasadas** (rápida + reintento), guarda el caché **cada 200 tx** y tiene
un modo `--desde-cache` para analizar lo parcial sin tocar el RPC.

## Buscar wallets en la RED de una wallet es casi siempre un callejón

Al sacar las contrapartes de los flujos hay que **filtrar primero qué es una wallet**: cuentas cuyo
owner no es el System Program (vaults de pools en wSOL, PDAs, cuentas de token), inexistentes o con
<0,02 SOL **no son wallets de personas**. Medido sobre una wallet de 3.000 tx: de **633 contrapartes
con SOL sólo 10 eran wallets reales** (el 94% infraestructura). Entre esas 10, las que "ganan" eran el
patrón trampa (win rate 100% con 5-15 posiciones y 60-85% sin compra = bundle, no trader) y la mejor
sacó 7/10: otro bot de 6 s. Conclusión operativa: para descubrir wallets útiles usar **compradores
reales del pool** de tokens que corrieron, no las conexiones de una wallet dada.

**Firma de clúster barata y contundente**: wallets con el mismo **prefijo y sufijo de vanidad**
(ej. `A6zD……Y3a` en tres, dos de ellas pagando los fees) = set generado por el mismo operador.
Un prefijo de 4 caracteres compartido ya es 1 en ~11M por azar.

## Descubrir candidatas: ronda propia primero, listas públicas sólo como semilla

**Preferencia explícita del usuario: las wallets las tiene que encontrar el motor propio.** Pidió
«sácalas vos, no uses listas públicas» y rechazó una tanda entera que venía de datasets de GMGN/KolScan
—incluso ya re-auditada con el motor—. Las listas públicas valen como **semilla de candidatas** (traen
cientos ya clasificadas), nunca como entregable final: lo que se propone sale de la ronda propia
(radar → compradores del pool → arranque → red) y, si una wallet viene de una lista, **declararlo en la
ficha**. Si pregunta «¿estas las encontraste vos?», contestar **wallet por wallet con el origen** (ronda
propia / dataset X): mezclar fuentes sin decirlo se lee como haberle ocultado de dónde salieron.

**Separar «listas» de «técnicas» en lo que se trae de afuera.** Si el pedido es «buscá lo mejor en
GitHub/Reddit», hay dos entregables distintos y el usuario puede querer el otro: las **listas**
(datasets etiquetados) se filtran y se re-auditan; las **técnicas** valen por el **umbral medible + la
fuente** y se guardan como dossier del proyecto (`TECNICAS_INSIDERS.md`) **más un script que las
aplique**. Devolver sólo el listado cuando pidió método se lee como no haber entendido el pedido: al
buscar, cubrir también papers/taxonomías/skills de terceros con umbrales explícitos, no sólo repos de
wallets.

Antes de gastar una ronda de descubrimiento desde cero, **además** se pueden mirar datasets públicos de
wallets etiquetadas (GitHub): una ronda propia de compradores de pool rinde 0-2 candidatas y una lista
ya etiquetada trae cientos clasificadas por GMGN/KolScan. Pero la lista sola **no es entregable**:
medido sobre las 20 mejores «smart money» de un dataset, **17 o pierden o ganan por 2-3 golpes** (una
con 369.000 USD de ganancia histórica estaba en −37 SOL al re-auditarla), y el archivo puede tener
meses. Fuentes concretas, campos del dataset,
herramientas de terceros y las ideas que vale copiarles: `references/fuentes-de-candidatas.md`.

Embudo, en este orden y sin saltear el paso 3:
1. **Filtrar con las métricas del dataset**: ganancia 30 d > 0, win rate ≥50 %, ≥30 operaciones y hold
   ≥120 **segundos**. La unidad es la trampa: `avg_holding_period_*` de GMGN viene en **segundos**, y
   leerlo como minutos da un filtro absurdo (la mediana del tramo rentable daría «102.070 min» = 71
   días) que deja pasar cualquier cosa.
2. **Chequeo de vida con RPC** (2-3 llamadas por wallet: `getBalance`, último `blockTime` de
   `getSignaturesForAddress`, cuentas de token con saldo). Una etiqueta de hace meses no vale nada si
   la wallet está muerta: medido sobre 104 que pasaban el filtro, **74 seguían activas** (movieron en
   los últimos 14 días) y **24 tenían ≥20 SOL**.
3. **Re-auditar con el motor propio** antes de recomendar: el PnL del dataset es de GMGN/KolScan y de
   la fecha del archivo, no verificado por nosotros — y GMGN mismo advierte que sus etiquetas de smart
   money atraen copiadores (carnada). Etiqueta vieja ≠ edge hoy; sin el 0-10 propio (con
   `pnl_sin_top3_sol`) no se propone nada.

## La ventana corta MIENTE: puntuar siempre con el historial profundo

Dos veces en la misma jornada un candidato "bueno" se dio vuelta al ampliar la ventana: una wallet
con 350 tx daba **9/10 (+0,67 SOL, t 0,15)** y con 850 tx quedó en **5,5/10 (−35,3 SOL, ROI −10,2 %,
t −2,46, 114 cerradas)**. Regla: **no proponer una wallet con <1.000 tx leídas**, y nunca con <30
posiciones cerradas. Antes de darla por buena, re-evaluar con 2.000-3.000 tx (cuesta ~10-20 minutos y
~2-3 % del cupo de Helius por wallet).

`auditor_wallets.auditar_wallet` sirve para el **primer filtro** (hasta 1.000 tx), pero **pide
`limit: max_tx` directo y el RPC rechaza límites >1.000**: con `--tx 2000` devuelve `None` y la wallet
aparece como «sin posiciones cerradas». Para profundizar hay que usar la tubería paginada de
`forense_profunda.py` (`evaluar_wallet.py` ya lo hace y guarda caché).

La ventana corta mueve la nota **en las dos direcciones**, así que no es una estimación conservadora:
es ruido. En la misma camada, una wallet que en la pasada barata sacaba **5,5/10** subió a **9,0/10**
al mirarla en serio (46 cerradas, +38,9 SOL, t 0,81). Corolario: si la corrida lee **menos tx que las
pedidas**, esa wallet tiene **menos historial que el pedido** — la muestra ya es completa y el `t` que
salga es el definitivo; no hay «faltan datos» que ampliar.

## Trabajo pedido: cazar la wallet «10/10»

Dylan pasa una dirección y espera (1) la auditoría honesta, (2) que además **busque wallets
conectadas / compradores reales** hasta dar con una que pase **todos** los filtros, y (3) **nada al
tracker por debajo de 8/10** — y aun con 8+ se le **propone antes de cargarla** (confirmar la lectura
de `wallets.json`). Criterios del 0-10 en `red_wallets.puntaje_10`: gana (+2), ROI >0 (+1,5), ≥30
cerradas (+1,5), win rate 45-80 % (+1; >85 % con muestra chica es bundle, no virtud), PnL no
concentrado (+1), t ≥1,645 (+1), ≤20 % sin compra (+1), hold ≥2 min (+1, «copiable»).

Flujo: `red_wallets.py <dir>` (red de esa wallet, descartando pools/PDAs), `buscar_10.py`
(**compradores reales del pool** de tokens que corrieron, el método que sí encuentra humanos),
`evaluar_wallet.py <dir> --tx 2000` (nota con historial profundo paginado; `--desde-cache`).
Universo de tokens: **el del radar** (score ≥70 del log del cron) con volumen 24 h ≥50k y liquidez
≥10k, y el pool sale de DexScreener (`pairAddress`, sirve para tokens viejos). La lista cruda de
pump.fun trae **stablecoins y activos tokenizados** (USDF, USDP, DOTF…): sus «compradores» son bots de
arbitraje, no traders de memecoins.

**Qué ventana se lee — no confundir arranque con post-graduación**: el `pairAddress` de DexScreener es
el pool de **PumpSwap**, así que su tx más vieja es la **graduación**: leerlo da «primeros compradores
después de migrar», no el lanzamiento. El arranque real (compras en la curva + reparto del bundle) hay
que leerlo **en la cuenta de la curva de pump.fun**, no en el mint: en un token ya graduado las primeras
tx del mint que devuelve el nodo **ya son de PumpSwap** (las compras de la curva no listan el mint como
cuenta), así que leer el mint da un tramo del medio y un «slot de creación» falso; en un token **fresco**
(sin migrar) el mint sí alcanza. Con `--ventana viejas` (paginar hasta la más vieja) se duplica el
hallazgo de compradores frente a leer las últimas (92 contra 45 en la misma corrida), pero el perfil no
cambia: el que entra en el arranque **pagando su plata** suele perder (tres seguidos con 3 posiciones
cerradas, 0 % de aciertos y −30 a −59 SOL cada uno). Para cazar **insiders** de verdad (entradas en el
lanzamiento, allocations gratis filtradas por tamaño, vínculo con el creador):
`references/insider-y-lanzamiento.md`.

**Embudo en dos etapas** (así se puntúa sin mentir): 1ª pasada barata `--auditar N --tx 150` para
tirar la basura, y 2ª pasada `--profundizar K --tx-profundo 1200` sobre las K mejores — **esa es la
nota que vale**. Con 30 tokens × 60 tx de pool salen ~25 compradores (~15 min de RPC) y las 8 profundas
~25 min más; costo ~15 % del cupo mensual de Helius. Expectativa realista: **de ~25 compradores, entre
0 y 2 llegan a 8+ en la pasada profunda**. El criterio que más bloquea el 10 es **`t ≥ 1,645`**: una
wallet con 46 cerradas y +38,9 SOL se quedó en **9,0/10** = «gana, pero no está probado», no «casi
perfecta». Cuando falte sólo eso, mirar el detalle de sus trades (cuánto pesa su mejor operación)
antes de decidir si es muestra chica o ventaja inexistente.

## Nunca puntuar wallets sin mirar la muestra y el win rate

Con 5-15 posiciones cerradas **cualquier** ROI es ruido: ROI 22.215% en 5 trades no es un edge. Un
win rate >85% con muestra chica es bandera roja (bundle/insider), no virtud. Y «gana plata» sin mirar
`t_stat`, concentración y `% sin compra` no alcanza: wallets con +4 SOL y t = −2,98 pasaron el filtro
de PnL y no el de significancia.

**Suerte de cola ≠ ventaja**: el PnL neto solo deja pasar loterías. Medir siempre el PnL **quitando los
3 mejores trades** (campo `pnl_sin_top3_sol` de `forense_profunda.metricas`): si al sacarlos queda
**negativo**, la ganancia son 2-3 golpes y no hay ventaja repetible. Medido: una wallet con **+38,94 SOL
y t 0,81** caía a **−3,59 SOL** sin sus 3 mejores (sus 5 mejores sumaban +65 SOL sobre un neto de +39),
y la de mayor PnL de otra ronda (+137 SOL) tenía **64 % en un solo trade** → 7/10, no 10/10. El puntaje
exige ahora **las dos cosas** para dar el punto de «resultado repartido»: `concentracion_pnl < 50 %`
**y** `pnl_sin_top3_sol > 0`.

**Y lo mismo aplica a la LISTA, no sólo a la ficha: un ranking por PnL de copia acumulado premia suerte.**
Pedido típico: «dame las wallets más jugosas». Un podio ordenado por PnL de copia sale encabezado por wallets
con **0-1 % de aciertos y mediana por debajo de 1x**: su ganancia es **una** operación afortunada entre decenas
o cientos, así que copiarlas es comprar un billete con el número de otro. Antes de entregar el podio, correr el
**filtro de repetibilidad** (aciertos ≥30 %, mediana ≥1,1x, ≥15 operaciones) y **decir cuántas quedan** — puede
ser **cero**: medido sobre 1.601 wallets puntuadas (425 con PnL positivo), el filtro no devolvió **ninguna**, ni
aflojado a 20 %/1,0x. Que el conjunto pierda (mediana global 0,5-1,0x) es el resultado, y vale más dicho que
tapado por un podio ordenado al revés; reportar ese hallazgo **primero** y después el listado completo con sus
campos (aciertos, mediana, operaciones, si la muestra es confiable) para que el usuario elija con **sus**
umbrales. Ojo con la unidad al filtrar: el campo de aciertos del estado viene en **fracción**, no en por ciento
(`0,0014` es 0,14 %, no 1,4 %) — leerlo al revés hace pasar por buenas a todas. Y si el usuario dice que los
datos son viejos, **tener razón no alcanza: releer el estado actual y mostrar el conteo nuevo** (auditadas,
con ganancia, cuántas repiten) en vez de defender la lista anterior.

## Dónde está el insider de verdad (y dónde no) — medido 2026-10-07

Cinco rutas probadas sobre tokens que despegaron, sin listas públicas:

| Ruta | Resultado |
|---|---|
| Compras en el slot de creación (bundle) | **no hay**: una sola compra de arranque (dev buy 0,2-0,5 SOL = <1 %) |
| Receptores sin pagar | **miles** por token (FOMO 741 · WSOS 562 · OURA 482 · TDF 461) y son **cáscaras**: 0 operaciones, 0,002-0,01 SOL |
| Cruce «recibió gratis → vendió en el pico» | **vacío**: los que reciben no venden y los que venden habían comprado |
| Creadores | wallets **frescas y desechables** (`creatorTokens: 0`, sin historial) |
| Distribuidores (el que reparte) | **la huella**: un remitente por token repartiendo a 300-380 wallets, con **7,381 SOL idénticos** entre lanzadores distintos = un solo operador |

**Dónde SÍ aparece un insider verificable**: en el **clúster que el creador fondea** — leer las tx del
creador, quedarse con las wallets a las que **le manda SOL** ≥0,5 SOL, auditarlas y filtrar por
`pct_sin_compra ≥ 40 %` + PnL positivo. Medido: de 7 wallets fondeadas por devs, **todas las otras 6
fueron cáscaras**.

### ⚠️ Falso positivo que no hay que repetir (corregido con el usuario presente)

Se reportó como «insider verificado» a `5Dx8dhAAmA1BqP5Us7gu6vh5YgwLeWJENmJY4GBuwyLA` (+81,75 SOL, 0
compras). **Era falso**: la dirección es una cuenta **del programa de fees de pump.fun**
(`6EF8rrecthR5Dkzo…`), con 0,0014 SOL y **99 de 100 tx fallidas**; el parser le atribuyó movimientos que
no eran suyos. Lo cazó el usuario mirando el explorador. **Regla dura antes de auditar, etiquetar,
trackear o listar una dirección: `getAccountInfo` y exigir
`owner == 11111111111111111111111111111111` (System Program)** — si no, es cuenta de programa/PDA/cuenta
de token y **no se reporta como wallet**. Ya implementado como `es_wallet()` en
`verificar_cluster_devs.py`. Con el filtro aplicado, esa ruta quedó en **0 insiders verificados**; las 3
que sí se sostienen (`4suu2qBGieLQ…`, `AG4q7iP4aVAQ…`, `DSk4pb9ZKXp8…`) salieron del escáner de RED
(`red_wallets.py`), que ya filtraba por dueño. **Antes de entregar una lista de direcciones, correr ese
chequeo sobre cada una y decirlo en el informe.**

**Trampa de método**: auditar wallets enteras buscando «su ganancia en ESE token» falla cuando el
trade quedó fuera de la ventana (el wallet hizo miles de tx después). Para el resultado en un token
concreto conviene leer **el historial del propio token** (sus tx viejas para la entrada, las nuevas
para las salidas), no la wallet.

## Técnicas para cazar insiders (dossier completo en el proyecto)

Dossier con fuentes y umbrales: `~/.hermes/data/memecoins/TECNICAS_INSIDERS.md`. Lo esencial:

1. **Compras en el slot de creación** — la señal más limpia: **≥3 compras en el mismo slot que la
   creación del mint = bundle**, porque nadie de afuera puede transaccionar ahí. 1 sola puede ser el
   dev buy normal.
2. **Supply acaparado en el bloque cero** — traducir el SOL gastado a % del supply: <5 % normal ·
   5-15 % bloque insider · 15-25 % un actor mueve el precio · **>25 % los insiders son dueños**.
   Referencia: 10 SOL en el bloque cero ≈ 26,6 % del supply de un token de pump.fun.
3. **Clustering por fondeo** — wallets del mismo token fondeadas desde **la misma wallet**
   (`MIN_CLUSTER_SIZE = 3`, fondeo ≥0,001 SOL, ventana corta). Heurística de bubble map: *mismo
   ancestro de fondeo + correlación temporal + saldos parecidos + poca actividad independiente*.
   Ojo: reutilizar wallets, romper el timing y diluir con actividad real **rompen** el clúster.
   Las otras claves de agrupación que faltan, por costo: **el pagador de la comisión** (`accountKeys[0]` de la tx:
   si varias wallets compran pagando con el mismo pagador son la misma mano — ya viene en la tx que se lee para las
   compras, así que se guarda `pagador` por compra sin gastar una llamada extra); **fondeo a 2 saltos** (el fondeador
   real manda a intermediarios: en el salto 1 cada wallet tiene un padre distinto, en el 2 todas apuntan a la misma
   → trazar 2 saltos antes de decir «no hay familia»); y el **grafo de transferencias** (los vínculos del bubble map
   son transferencias entre wallets —cualquier token—, no compras simultáneas: agrupa por relación; excluir
   pools/exchanges/contratos antes de agrupar y **no vincular los «supernodos»**, que sobre-fusionan). Y
   **bundle ≠ clúster**: compras en el **mismo slot** = un operador repartiendo; repartidas en minutos = un grupo de
   personas — usar el slot para separarlas, en vez de etiquetar «granja» a ojo.
4. **Anillos persistentes (co-firing)** — wallets que vuelven a aparecer juntas como primeros
   compradores en **≥2-3 lanzamientos**: se detecta con **union-find sobre el grafo de co-ocurrencia**
   (arXiv 2607.02795 encontró 1.012 anillos de 2-12 wallets). No necesita datos nuevos: acumular sets
   de primeros compradores por token y contar intersecciones. **Es la vía que quedó implementada**
   (`cohortes.py`: `--cosechar N` arma el set de primeros compradores por lanzamiento — ~20 tx del pool,
   compradores con ≥0,1 SOL, token de ≤4 h). Tasa esperada, calcularla antes de prometer plazos:
   **~164 lanzamientos por cohorte**; con 1.920 cosechados/día salen ~12/día, con 300/día **ninguno en
   semanas** («no aparece ningún cohorte» con 40 lanzamientos es la división, no un bug). Medido con el
   umbral de **2 coincidencias**: **3 cohortes en 51 lanzamientos** (~1 cada 17) — mucho más frecuentes que
   el anillo del paper, porque 2 wallets que repiten 2× es un umbral laxo. Igual no prometer valor
   predictivo hasta medirlo con el registro: los cohortes encontrados son **dúos en 2-3 lanzamientos del
   mismo universo cosechado**, no las multitudes de los grupos públicos.

   **La re-cosecha multiplica el grafo: la compra sigue después de la primera lectura.** Volver a leer a
   los ~30 min los lanzamientos de ≤2 h y **sumar** los compradores nuevos (marcar `ultima_lectura`)
   duplicó los compradores por lanzamiento (`Andrew 8→17`, `ANYPAD 2→13`) y llevó los cohortes de **0 a 3
   en una sola pasada**. Leer el lanzamiento una vez y archivarlo deja el grafo a la mitad.

   **Pero la re-cosecha es el mayor gasto del sistema, y no se ve desde el contador de ningún script.** Medido:
   releer ~90 tokens por pasada, 4 pasadas por hora, estima **~1,8 M de créditos por día** — más que todos los
demás componentes juntos, porque el contador por componente no la separa de la cosecha de tokens nuevos. El ahorro
grande está en **acotar cuántos tokens viejos se re-leen por pasada** (~20, los más recientes), no en bajar la
cosecha de lanzamientos nuevos ni en frenar el detector: antes de recortar señales, medir el gasto por **tipo de
trabajo** dentro del componente (nuevo vs re-leído).

   **La patrulla mira las WALLETS del cohorte, no el universo de tokens.** Corregido midiendo: la versión
   que buscaba a los cohortes *dentro* de la lista de tokens vivos dio **0 avisos con 4 de 6 wallets del
   cohorte operando en ese mismo momento** (compran tokens que no están en tu lista). Se siguen las firmas
   de las wallets conocidas y la compra se detecta del lado de la wallet (token que sube + SOL que baja,
   `maxSupportedTransactionVersion: 1`, excluyendo wSOL/USDC/USDT y las que no sacan ≥0,01 SOL). Primera
   pasada de una wallet = **línea base** (anotar firmas sin avisar), como en cualquier tracker.

   **El aviso sale por entrada COORDINADA, no por cada compra.** Avisar cada compra de wallets activas es
   un río (**8 avisos en una pasada, ~160/hora** medido): las compras van a un buffer (6 h) y se avisa sólo
   cuando **≥2 wallets del MISMO cohorte** compraron el mismo token dentro de la ventana (~60 min), con
   dedupe por `mint + conjunto de wallets`. El resto queda registrado sin avisar.

   **Perfil del cohorte: personas vs granja de bots — con el chequeo de fondeo BIEN hecho.** Wallets
   **frescas** (sin historial) o con **fondeo compartido** = granja; wallets con historia financiadas por
   separado = grupo de personas. Pero el fondeo compartido se lee de las tx **MÁS VIEJAS** de cada wallet
   (el fondeo de origen): mirar las últimas n tx devuelve **pools y bots** como «fondeador compartido» —
   falso positivo que ya marcó como granja a un dúo que no lo era. Exigir además que el pagador **haya
   mandado** SOL (una pool lo recibe, no lo manda). Si el historial es más largo de lo que se paginó,
   responder **«sin determinar»** en vez de inventar un fondeador leyendo un tramo del medio; y **cachear
   el perfil por wallet** (~7 días) para que una granja marcada no vuelva a «grupo de personas» cuando el
   chequeo falla por red. Las granjas **no se avisan** (son máquinas): se registran y se listan aparte.

   **El grupo se clasifica por su REGISTRO y el tier decide qué avisa y en qué canal.** Tiers 🟢 seguir / 🟠 lotería
   / 🟡 observar / 🔴 descartar con cortes numéricos (mediana, % de ≥1,5x y, sobre todo, **el FDV que compran**:
el que compra tokens grandes no tiene de dónde subir), recalculados solos cada rato — un grupo con 1-2 entradas
   todavía no tiene veredicto. Un canal por nivel y **cupo de avisos por hora POR canal** (con tope global el ruido
   de un nivel se come los avisos del otro). Cortes, reparto medido y receta de canales:
   `references/grupos-coordinados.md`. **Sin nivel no se adivina el canal**: un grupo todavía no clasificado avisa en
   el canal general, nunca en un canal de nivel «por defecto» (quedar en el general es ruido; caer en el canal
   equivocado es información falsa). **Los grupos NUEVOS se anuncian** al general en cuanto se detectan (nombre,
   tamaño y quién entra primero) llevando un registro de firmas de wallets ya vistas, para no re-anunciar los
   treinta que ya existen. El puntaje de estos avisos sale de `CD.puntuar` como cualquier call — un
   `0/10` fijo se lee como sistema roto.

   **El ruteo y el puntaje se deciden por WALLET, no por grupo.** Medido: las wallets verdaderamente copiables
   quedaban **dentro** del grupo grande que va a lotería, así que sus entradas —justo las mejores— salían por el
   canal de descarte. Se puntúa cada wallet por su **PnL de copia** (suma de `múltiplo − 1` suponiendo 1 unidad por
   entrada, contando también las que cazaron un múltiplo grande), **no por la mediana del grupo**: las cazadoras de
   monstruos tienen mediana mala y PnL de copia excelente, que es lo que le sirve a quien decide por aviso. Con ese
   filtro, medido: **233 wallets → 13 copiables**; y su entrada va al canal de seguir **aunque su grupo sea 🟠**
   (cupo por canal, doble para ese canal, copiables primero en la lista). Corolario para el diagnóstico «no llega
   nada al canal de seguir»: la causa puede ser el **grupo** del que cuelgan las buenas, no el corte de
   clasificación. **Y el 0-10 se reparte por percentil del día**, no por suma con tope: la suma se satura (todo
   10/10 o todo 0) y deja de ordenar entre días.

   ⚠️ **En una cosecha, el freno suele ser la OFERTA de candidatos, no el cupo ni la frecuencia.** Medido:
   `--cosechar 20` cada 15 min avanzaba **1 token por pasada** (~4/día) porque sólo leía la lista
   `tokens_jovenes.json` del radar, ya cosechada entera. Arreglo: si a esa lista le faltan candidatos, la
   cosecha **arma la suya** con las listas de pump.fun (`pump_nuevos` / `pump_live` / `pump_movidos`)
   filtrando edad ≤4 h, mcap ≥5k y par vivo en DexScreener. Antes de subir cupo o frecuencia «para ir más
   rápido», contar cuántos candidatos **nuevos** entran por pasada.
5. **Bundle de una sola tx** — una transacción con **≥2 dueños distintos** del mismo mint que suben
   (reparto a varios wallets, un solo pagador).
6. **Agregados del proveedor** (GMGN vía Noesis: `insider_count`, `bundler_count`, `sniper_count`,
   `top_bundler_trader_percentage`, `top_entrapment_trader_percentage`) sirven de **prefiltro**: son
   agregados, **no prueba wallet por wallet**.

**Anti-patrones y límites (no vender humo)**: el patrón “15 wallets frescas fondeadas de un master con
25-40 % del supply” **no se encontró** al trazarlo en 323 lanzamientos; la “smart money” pública puede
ser **carnada** para copiadores; muchas ganancias vienen de estrategias irreplicables (HFT, acceso al
dev). Tasa base: **98,6 %** de los tokens de pump.fun colapsaron y sólo **1,4 %** mantuvo ≥1.000 USD de
de liquidez. Y un cohorte de **12 clústeres** orquestó ~**82 %** de los drenajes → cazar clústeres rinde.

**Medir por TOKEN, no auditando wallets enteras.** Para saber si una wallet ganó en un token concreto
**no** sirve auditar su historial: `auditar_wallet` lee las N tx **más recientes** y el trade del token
cae fuera de esa ventana en cuanto la wallet hizo miles de movimientos después → el campo del token
vuelve vacío y el informe dice «0 insiders» con cientos de candidatos delante (medido: 6 candidatos por
token en 4 tokens, 0 hallazgos, aun teniendo 562 receptores de lanzamiento en un token de 234 M de
mcap). La vía que evita el problema es **leer el propio historial del token en sus dos puntas**: tx más
viejas del mint = quién recibió/entró en el lanzamiento; tx más nuevas (las del despegue) = quién
**vendió** (Δtoken < 0 y ΔSOL > 0) y cuánto SOL cobró; **el cruce de los dos sets es la prueba**
(recibió gratis y cobró en el pico). Implementado en `insiders_cruce.py`
(`--tokens --viejas --nuevas --min-sol`): el mecanismo es sólido pero hay que **validar la corrida
hasta el final** antes de presentar los cruces como hallazgo — no anunciar «encontré el insider» con
el resultado a mitad de camino.

**Calibración de las rutas de insider (medido, para no volver a gastar cupo en ellas)**: en 16
lanzamientos hubo **1.961 receptores «gratis»**, **1 solo anillo de 2 wallets** y **0 bundles de tx
única** → las wallets son **frescas por lanzamiento** (no hay anillos que reutilizar), y los receptores
gratis son **cáscaras**: los 12 más grandes auditados dieron **0 posiciones cerradas y 0,002-0,01 SOL**
de saldo. La ruta «airdrop → insider» sólo rinde si se filtra por tamaño (≥0,05 % del supply) **y** se
mide el resultado por token.

**Implementación y quiebres de datos**: `insider_token.py <mint>` mide las compras del slot de creación,
el % del supply (supply crudo de RugCheck ÷ 10^decimals — sin esa conversión todo da 0 %), el clúster de
fondeo del bloque cero y emite el veredicto BUNDLE / sin bundle. Antes de confiar en él para todo token:
(1) en graduados hay que leer la **cuenta de la curva**, no el mint (ver «Qué ventana se lee»), y
(2) algunas tx viejas devuelven el balance del comprador con `uiTokenAmount.uiAmount: null` y
`amount: "0"` → el monto de la compra se saca de las **instrucciones** (`BuyExactQuoteIn` de
`pAMMBay6…` o el `buy` de la curva), no de `pre/postTokenBalances`, o el detector concluye «sin
compras». Un mint **recién creado** puede devolver 0 firmas (lag del indexador): reintentar, no es «sin
datos». Dossier con fuentes y umbrales: `~/.hermes/data/memecoins/TECNICAS_INSIDERS.md`.

## Grupos de alpha pagos: la «call» se ve como RÁFAGA, no en una wallet

Los grupos que pasan tokens antes que el público (Pastel Alpha —fundada por **@CookerFlips**, cuya wallet
`8deJ9xeUvXSJ…` ya está en nuestro listado—, HoH Alpha, Shocked, Digiworld, Potion, Prosperity DAO…)
producen un patrón detectable sin conocer las wallets de antemano: **≥3 wallets distintas comprando el
mismo token dentro de ~90 s y con tamaño real = ráfaga = call**. Implementado y medido en
`cazar_calls.py`: corre el universo de tokens que corrieron, lee el pool (~400 tx), marca las ventanas
con ≥`--min-wallets` compradores distintos poniendo ≥`--min-sol` cada uno, y cruza entre tokens. Es la
técnica «cluster conviction» que usan SolChad / CabalScanner / ricomaps / KOL Explorer, y es **la vía
correcta** para «wallets que compran sabiendo que va a subir» (el airdrop y el clúster de fondeo no dan
eso).

**Resultado medido — no hay núcleo de wallets; la unidad de señal es el TOKEN.** Corrida de 28 tokens:
**42 ráfagas, 162 wallets implicadas y 0 wallets en ≥2 ráfagas**. Traducido: las ráfagas existen (la call
es real y detectable) pero **ninguna wallet se repite** entre calls. La explicación es el tamaño del
grupo: Pastel/HoH son **multitudes** — cientos de miembros, cada uno con su wallet, y rotan por
lanzamiento — no un puñado de direcciones fijas. Operativamente: **no prometer «encontré las wallets del
grupo»** (esa ruta midió 0) ni seguir wallets para esto; lo que se construye es la **alerta a nivel
token**: cuando el pool muestra la ráfaga, el aviso sale con «⚡ CALL DETECTADA: N wallets · X SOL · Y s»
+ el análisis del token ya hecho, y el usuario decide. **Ya está montado** (no reconstruirlo): `calls_detector.py` enganchado a `pump_analizador.vigilar()` y `embed_de()`, con tope propio de gasto (`presupuesto_calls.json`, 30.000 créditos/día, ~410 por chequeo de 40 tx del pool), ventana 150 s y ≥0,3 SOL por wallet; layout del aviso, señales que lo acompañan y candados en `references/calls-y-avisos.md`.

**Dos reglas de diseño del detector, aprendidas midiendo:**
1. **Chequear cada token UNA sola vez pierde la mayoría de las calls.** Si el chequeo de ráfaga corre solo
   cuando el radar analiza el token, la call que sale 10-30 min después se pierde para siempre — y no se
   arregla bajando umbrales (bajarlos solo mete ruido). Hay que **re-chequear los tokens de ≤2 h de vida en
   cada pasada**, guardando en el estado lo necesario para reconstruir esa lista (edad de creación, mcap,
   símbolo), y subir el tope diario de créditos —el gasto va por chequeo, no por token único.
2. **El mismo slot es la señal más dura**: ≥3 compras en el **mismo slot** (~400 ms) no se explican por
   coincidencia → el aviso sube a **🚨 BUNDLE**; y contar cuántas de las carteras de la ráfaga son **nuevas**
   (sin historial) frente a **ya conocidas** distingue bundle de call de gente real. Medido: en las ráfagas
   reales las carteras salen **ni nuevas ni conocidas** (carteras con historia) → confirma que la unidad de
   señal es el **evento del token**, no la wallet. **Modo actual: `--solo-rafagas`** — en el canal del radar solo van las calls; los avisos token-por-token y el parte diario quedaron apagados a pedido del usuario (cómo medir y reajustar ese volumen: skill `memecoins-pumpfun`). Timing honesto: con el radar cada 10 min la ráfaga
se ve hasta 10 min tarde → sirve para *enterarse* y para descartar, no para ganarle la entrada al grupo
(los miembros compran cuando sale la call). Bajarlo a segundos **está validado y montado**: el WebSocket del plan gratis de Helius
(`wss://mainnet.helius-rpc.com/?api-key=…`, handshake 101) entrega los trades del token **al instante** con
`logsSubscribe mentions:[mint]`, y `vigilante_calls.py` (servicio + keepalive por cron con
`arrancar_vigilante.sh`) avisa la ráfaga **en segundos** con los mismos candados y el mismo layout; el
detector del radar queda como red de fondo. **El mismo WebSocket sirve a nivel WALLET** y es lo que da el aviso
instantáneo: una suscripción `mentions: [wallet]` por cada wallet copiable (`vigilante_copiable.py`) entrega la
compra **0,7-0,9 s** después del bloque — contra los **~4 min de mediana** del sondeo por patrulla (medido), que
es lo que el usuario percibía como «las calls llegan tarde». **La demora de la entrega es una métrica de primera
línea de este sistema: se mide (ts de la compra en el buffer vs ts del aviso), se informa y se baja.** Receta,
costos medidos y las trampas (la suscripción al pool que
nunca dispara, el firehose del programa, el bucle de evaluación que quema el cupo):
`references/calls-y-avisos.md`.

**Medir cómo les fue a las calls es lo que calibra el filtro (no los umbrales a ojo).** La fuente de **todo el historial** es el **registro de emisión del propio bot** (acá `calls_historial.json`), que trae el mcap del momento del aviso en cada fila: ésa es la **línea base** que el usuario fija («se mide desde que el bot mandó el contrato») y la única que no se queda corta. **Barrer el canal cubre sólo la ventana reciente** —medido: **165 avisos** contra **1.021** del registro— y da a entender que el historial empieza cuando uno empezó a mirar el canal; el usuario lo detecta y lo reclama. La lectura del canal (`GET /channels/{id}/messages?limit=100`; **más de 100 = HTTP 400**) sirve para lo que el registro no trae: las **wallets y el SOL** del `content` y el **mint del PIE del embed** (`footer.text`), comparado con el mcap actual de DexScreener → el ratio de la call. **El mint no se saca del mensaje siguiente**
(el de la dirección pelada): si a una call le falta, el pareo se corre y le atribuís el resultado de otro token
— así se reportó un falso ganador de 3,2x sobre uno que hizo **0,01x**.

**Y el veredicto sale de la SERIE de precios desde el aviso, no de una foto.** Leer una call a los 20 min dio
«2,5x» en la que después cerró en **−99 %**: una lectura suelta miente en las dos direcciones. Se mide el **pico
posterior al aviso** (máximo de la serie), **cuándo** llegó y dónde quedó. Medido sobre 8 calls: **sólo 1 dio
ventana de ganancia** — la de **19 wallets y 55 SOL** (+145 % a los **39 min**, después −99 %) —, el **pico
promedio fue 0,65x** (el mejor momento típico ya estaba por debajo del precio del aviso) y el pico llega
**rápido** (mediana ~105 min). Con la muestra completa (~100 calls con seguimiento propio) la mediana del **pico**
es **~1,0x**, **15 % supera 1,5x**, **10 % dobla** y **4 % triplica** — la lectura de 8 calls era muestra chica,
igual de engañosa hacia el pesimismo. Y el «final» (mediana 0,48x) castiga al que ya se fue: **decir siempre con
qué métrica se está midiendo** (tabla y comandos: `references/calls-y-avisos.md`). Lectura operativa: **el predictor es la fuerza de la ráfaga, no el mcap**, y el
valor del puntaje es señalar **cuál da ventana para salir** — no «comprar y aguantar» (ninguna quedó en verde al
final). **Modo calidad a pedido («busco calidad en vez de cantidad»): el puntaje no alcanza, hay una puerta de
salida.** Medido sobre las calls con seguimiento: la mediana termina en **0,48x** y la mitad cierra en
≤0,6x; la única que hizo **3,18x** tenía edad 58 min, mcap $279k, liquidez $46k, 8 wallets y 11,5 SOL,
mientras los tramos de **edad <30 min (0 de 14)**, **mcap $10-50k (3 de 3)**, **liquidez <$30k** y
**3-5 wallets / 1-5 SOL (0 de 25)** se fueron todos al piso. Mínimos que aplica el aviso: **≥25 min de
vida, ≥$50k de mcap, ≥$30k de liquidez real** (en la curva, el SOL que se puede sacar), **≥5 wallets y
≥5 SOL**; y se descarta lo que ya cayó >50% de su máximo o subió >400% en 1 h. Clave del diseño: **las
rechazadas se registran igual y se miden en silencio**, así el filtro se recalibra con datos en vez de
quedar como dogma (y si el tramo rechazado rinde, se baja el listón con evidencia). Registro automático de cada call + muestreo cada 5 min +
informe de calibración («medí el resultado de las calls», «¿cuáles salieron bien?»):
`references/calls-y-avisos.md` — contestar con esa tabla, no con la impresión del momento.

**De dónde sale el pico (cada fuente mide un tramo distinto).** Usar las **velas del pool** (GeckoTerminal, sin
key: 30 llamadas/min, 2 por contrato → ~12 contratos por pasada, espaciadas y con manejo del 429), **nunca** el
`ath_market_cap` de pump.fun, que devuelve basura (1,99e+23). Y decirlo en el informe: **el tramo de la curva
antes de graduarse no está en las velas del pool**, así que el pico medido puede quedar por debajo del real
(medido: un token con pico de curva 3,3 M mostraba 25 k leyendo el pool).

**«¿Por qué salen tan pocas calls?»: revisar en este orden, no adivinar.** (1) servicio vivo por **PID**
(`ps -p $(cat vigilante.pid)`); (2) **excepciones en el log de cada componente** — un bug en el bloque de
ráfagas del radar deja de mandar calls sin ruido visible y desde afuera se lee como «mercado flojo»;
(3) **evaluaciones vs avisos** en el log del vigilante (muchas evaluaciones y 0 avisos = el problema está en la
**lectura** de la ráfaga, no en el mercado); (4) **de qué lado de la ráfaga se lee** — el **arranque** trae las
compras y la **cola** trae puras ventas en un token que ya bajó (leer el arranque: primeras tx de la ventana);
(5) que la **lista de jóvenes** esté poblada y el tope de suscripciones la cubra entera; (6) recién entonces
mirar umbrales. Y decir la verdad del mercado: buena parte de las «ráfagas» de tokens jóvenes son **polvo**
(0,002-0,03 SOL por wallet = bots de volumen, ignorados a propósito) y las fuertes son **unas pocas por día**.
Detalle y mediciones: `references/calls-y-avisos.md`.

## Etiquetas: criterios, no adjetivos

| Etiqueta | Criterio | Para qué sirve |
|---|---|---|
| 🚨 INSIDER | ≥40% de posiciones cerradas **sin compra previa** (vendió tokens que nunca compró), o ≥25% con win rate ≥90% | Alarma: avisa cuándo los que recibieron supply regalado sueltan |
| ⭐ CANDIDATA | Compró con su propia plata, PnL positivo, hold humano (≥2 min) | Candidata a seguir (muestra chica = a verificar) |
| 🤖 BOT/MEV | Hold mediano <2 min con ≥3 operaciones | No copiable: cuando reacciones, ya vendió |
| 📤 PASARELA | Muchos fondeadores/destinatarios y casi sin tokens | La wallet que opera está en otro lado |
| 📉 PIERDE | Compró de verdad y perdió | Lista negra |
| ❓ SIN DATOS | 0 posiciones cerradas en la ventana revisada | No es veredicto: ampliar la ventana |

Umbrales completos con fuentes y las trampas que reporta la comunidad: `references/umbrales-y-fuentes.md`.

## Qué se puede afirmar y qué no (honestidad del informe)

- **<30 posiciones cerradas = no hay veredicto.** Un win rate sobre 2 operaciones no dice nada; y para
  distinguir un edge chico (55% vs 50%) hacen falta ~380 operaciones. Con ventanas de 25-70 tx la
  mayoría de las wallets sale «❓ SIN DATOS»: **decirlo**, no rellenar con un puntaje inventado.
- **Certificar requiere profundidad**: cuando pidan el veredicto serio, hay que ir a 300+ tx por
  wallet (tarda minutos por wallet; avisar el costo antes de lanzarlo).
- El PnL propio es **reconstruido** desde la cadena: no incluye priority fees/tips ni la ventana
  completa de historial → el real es algo peor. Ponerlo en el pie del informe.
- Las listas de PnL de GMGN/Cielo/Axiom no se pueden leer sin key: **nunca** presentar su PnL como
  propio.
- Un clúster es **pista, no prueba**: nombrar el mecanismo dominante y qué evidencia lo rompería.
- **Que un grupo compre junto NO garantiza que el token suba.** El «efecto» crudo de las cohortes está inflado por
  contaminación: al excluir las compras del propio grupo y emparejar por calidad del lanzamiento, el paper
  fundacional (mismo método que usamos) queda en **+16,1 % de compradores** y **SOL indistinguible de cero**, y en
  **7 %** de los lanzamientos nadie los sigue. Reglas al medir el sistema: **excluir las compras del grupo** del
  resultado y comparar los avisos contra un **control emparejado** (tokens frescos al azar de la misma hora, edad y
  mcap) — sin control no se distingue ventaja de ruido del mercado. Detalle y puntaje por wallet:
  `references/grupos-coordinados.md`.

## Trampas que arruinan el resultado

1. **RugCheck no expone las direcciones de los insiders**: `/tokens/{mint}/insiders` y `/holders`
   responden 404, y `topHolders[].insider` viene en `false` incluso en tokens con `insiderNetworks`
   detectadas. La etiqueta insider hay que sacarla **de la cadena** (posiciones cobradas sin compra),
   no de la API. Del mismo reporte, qué sirve y qué engaña: **`score_normalised` es un score de RIESGO
   (más bajo = más sano)**, no de calidad — usarlo al revés premia los tokens peligrosos; sí son útiles
   `rugged` (descarte directo), `graphInsidersDetected` (red de insiders conectada) y `topHolders[].pct`
   sumado **sin** los `knownAccounts` (AMM/LOCKER/CREATOR/POOL). Y el **historial del creador no existe
   por API**: `creatorTokens` viene en `None` y los endpoints de lanzamientos por dev responden 404/530
   (no gastar cupo reintentándolos) → llevar un registro **propio** que se llena con cada token
   analizado y usarlo para marcar al lanzador serial cuando tenga historial.
2. **Descubrir wallets por "top holders" da insiders.** Medido: de 9 candidatas por holders, 0 servían
   (3 con 100% de posiciones sin compra, 2 con −60/−71 SOL, 4 sin datos). Lo que **sí** funciona: leer
   las transacciones del **pool** del token y extraer de ahí los **compradores** (12 tx del pool → 2
   compradores reales). La discovery por holders solo sirve para mapear quién tiene supply, no quién opera.
3. **Los CEX, bridges, pools y airdrops son stop-nodes**: de un hot wallet de exchange salen miles de
   wallets sin relación. Agrupar por ellos sobre-fusiona todo. Aplicar el chequeo de hub (1.000 firmas
   en la primera página de `getSignaturesForAddress` = veteranía/infra) **antes** de usar una wallet
   como padre del clúster o como candidata a seguir.
4. **El truco de Bitcoin NO aplica en Solana**: en un lanzamiento cientos de cuentas sin relación
   compran en el mismo segundo, así que las señales débiles se disparan juntas. Exigir **≥2 señales
   que fallen por mecanismos independientes** (co-firma > autoridad > pagador de fees > fondeo
   repetido > ritmo de operación > timing).
5. **Bundle Jito**: un solo pagador de fees = señal fuerte; varios pagadores = solo pista. En un
   sandwich la víctima comparte bundle con el atacante → marcar a la víctima como atacante es el error
   clásico.
6. **Leer el bloque de creación, no la transacción de creación**: los buys del bundle están en tx
   separadas del mismo bloque; y la curva/pool hay que **excluirla** al buscar destinatarios.
7. **Fondeo fresco = sin track record**: si el historial arranca con el fondeo (o el fondeo es de hace
   horas/días), no hay nada que evaluar. Y fondeo desde el dev/LP/deployer del token = insider.
8. **El `header` del mensaje viene en `None`** en el `getTransaction(jsonParsed)` del RPC público: no
   hay `numRequiredSignatures`, así que `keys[:n]` con `n=0` da **0 firmantes siempre** (un conteo
   falso que se ve creíble). El firmante se lee del flag **por cuenta**: `accountKeys[].signer`
   (`writable` aparte). Con `signer: False, writable: True` la wallet está **mencionada**, no actúa.
9. **El paginado de firmas: `before` va DENTRO del mismo dict de opciones** —
   `[addr, {"limit": 1000, "before": sig}]`. Mandarlo como dict separado (`[addr, {limit}, {before}]`)
   devuelve error de RPC, `rpc()` devuelve `None` y el bucle corta: parece que la wallet tiene «1.000
   tx / un día de vida» cuando puede tener 10.000 en 13 días, y la antigüedad y el ritmo del informe
   salen mal. Cruzar siempre el total con la **fecha de la firma más vieja** antes de afirmar nada.
10. **`getAccountInfo` = null + saldo 0 es el triage más rápido que existe**: la cuenta del sistema no
    existe (o quedó en 0 lamports), así que esa wallet **nunca pudo pagar un fee ni comprar nada**. Si
    además su Δ SOL es (0, 0) en la muestra, no hay PnL que reconstruir: no gastes el RPC en calcularlo.
11. **0 flujos de SOL en todo el historial ≠ «sin datos»**: es una wallet **receptora/automatizada**
    (le mandan tokens, los fees los paga un bot). El clasificador la va a etiquetar «❓ SIN DATOS»:
    corregir eso a mano en el informe («no es un trader»), no repetir la etiqueta automática.
12. **Las direcciones consecutivas en la lista de cuentas NO son una wallet farm**: los programas de
    Solana suelen exigir las cuentas **ordenadas por pubkey**, así que un lote ascendente
    (7SH7uA, 7SHH18, 7SbdXz…) sale de la ordenación, no de una generación secuencial. Para decir
    «clúster/farm» por vecindad de direcciones, exigir una segunda señal (mismo pagador de fees,
    misma cuota de supply, fondeo común).

## Verificación al editar estos scripts

- **Después de cada `patch`, mirar el resultado del `patch` — y después compilar Y correr la función tocada.**
  El `patch` devuelve `False` en vez de lanzar excepción cuando el ancla no matchea: el cambio «ya hecho» puede no
  existir y el script sigue con la lógica vieja (medido: un filtro de reporte que nunca se aplicó y se reportó
  como listo, con la tabla sin filtrar delante). El emparejamiento difuso del patch
  puede comerse una línea vecina: ya desapareció la definición de una **lista** y la de una **función**
  (`def conocidas():` se fue en un insert y quedó su cuerpo colgando → `NameError` a mitad del trabajo).
  Al insertar algo **antes** de otra definición, incluir esa línea `def` en `old_string` o volver a
  agregarla al final del bloque nuevo. Validar con una corrida real: este error es de runtime, no lo ve
  `py_compile`.
- **Al quitar o reescribir un bloque, grep el bloque por cada nombre que sacaste.** Una línea de log que usaba
  `mcap`/`curva` quedó colgando cuando esas definiciones se fueron con el bloque viejo → `NameError` en **cada**
  pasada, que mataba el bloque entero del radar: el sistema parecía andar (analizaba y silenciaba) pero **dejó de
  mandar calls durante horas**, y desde afuera se vio como «el mercado está flojo». `py_compile` no lo ve (es de
  runtime) y el `except` del bucle lo esconde: después de un cambio así, **correr la pasada real y leer el log
  buscando la excepción**, no sólo el resultado.
- **Un tope que agregás a una función no está en vigor hasta que revisás el LLAMADOR.** Si el que llama pasa el
  parámetro explícito (`max_avisos=8`), el default nuevo no se aplica y el tope «puesto» no frena nada (medido:
  el tope de avisos del detector de grupos nunca se cumplía). Grep el nombre del parámetro en todo el proyecto
  antes de dar el tope por activo, y confirmarlo con una corrida real donde el log muestre el salteo.
- **Nunca dejar un `[:N]` fijo sobre una colección que crece.** La patrulla de grupos recorría `wallets[:40]`: con 209
  wallets **170 quedaron sin chequear nunca** y sus entradas no avisaban — sin error, sin log, invisible desde afuera
  (apareció al contestar «no llega nada»). Recorrer la colección entera, o rankear y loguear cuántas quedaron afuera:
  un slice es un tope escondido.
- **Un aviso que no sale no deja rastro: el log tiene que decir POR QUÉ no salió.** Un `UnboundLocalError` (bloque
  insertado antes de la variable que usaba) mataba la pasada completa **antes** de avisar, y desde afuera se veía igual
  que «no hubo señales»: la salida del cron se descarta y nadie la lee. Cerrar cada pasada con una línea explícita
  (`sin avisos: N candidatos · motivo: <canal|criterio>`) y, tras tocar el camino de los avisos, correr la pasada a
  mano y **leer el canal destino** — que el código esté puesto no prueba entrega.
- **Un archivo de estado con marcadores de conflicto de git deja la tarea muerta en CADA pasada.** Un rebase
  mal resuelto sobre un `.json` de estado commitea `<<<<<<< HEAD` … `>>>>>>>` y el parser revienta con
  `Expecting value: line 1 column 1 (char 0)` en todas las corridas (medido: **750 fallos del mismo cron**, el
  último en el día en curso) mientras el resto del sistema se ve sano y el chat no muestra nada. Diagnóstico en
  una línea: `grep -B8 JSONDecodeError logs/cron.log` nombra el archivo. Arreglos: reparar uniendo las **dos**
  versiones del conflicto (parsear línea por línea, quedarse con los objetos válidos y deduplicar, así no se
  pierde ninguna mitad) y **endurecer el cargador** para que un estado ilegible registre el error y arranque
  vacío en vez de morir en cada ciclo. En git: `grep -rl '<<<<<<<'` antes de dar un rebase por bueno, y nunca
  `git reset --hard` con commits propios sin subir (se borran; hay que sacarlos del reflog).
- **Dos intérpretes**: `python3` (3.11) y `/usr/bin/python3` (el del cron, 3.14). Compilar con los dos;
  un f-string con `\` dentro de las llaves compila en 3.14 y revienta en 3.11.
- **Un embed nuevo se verifica LEYENDO el mensaje, y la prueba se borra.** Los motivos del aviso viajan en un
  **campo** del embed, no en la descripción: leer la descripción y «no encontrar» el cambio no prueba nada (medido:
  el lector comparó el lugar equivocado y por poco da por fallido un cambio que sí funcionaba). Mandar el aviso de
  prueba con un **grupo real** al canal, leer el mensaje por API, confirmar el campo y **borrar** los de prueba: el
  200 del POST no prueba el contenido del aviso.
- **El estado que comparten dos jobs del cron se escribe con temporal POR PROCESO, no con `<archivo>.tmp` fijo.**
  La patrulla (`*/3`) y la cosecha (`*/15`) escribieron a la vez: una renombró el `.tmp` y la otra murió con
  `FileNotFoundError` **a mitad de pasada**, así que todo lo que venía después de esa escritura no corrió (medido:
  los grupos se reconstruyeron y la clasificación nunca se ejecutó → quedaron **sin nivel** y sus avisos sin canal).
  `<archivo>.<pid>.tmp` + reintentos, clasificación aislada **por ítem** en try/except (uno que falla no deja
  vacíos a los demás) y, al reconstruir un registro, **arrastrar los campos derivados** (nivel/nombre) del armado
  anterior. Verificar el estado **derivado** después de la pasada («¿todos los registros tienen su nivel?»), no
  sólo que el archivo cambió. Y el temporal por PID **tampoco alcanza para el ciclo leer→agregar→escribir**: dos jobs
  que lo hacen a la vez **pierden filas** —medido: una call que el log daba por registrada **no existía en el
  archivo**—. El ciclo completo va bajo un **bloqueo entre procesos** (`fcntl.flock` sobre un `<archivo>.lock`), no
  sólo la escritura; sin eso el registro se ve completo y le faltan justo las entradas escritas en paralelo.
- **Un servicio (o su keepalive) arrancado desde el cron no está vivo porque haya escrito su PID.** Medido: el
  lanzador usaba un `python3` **sin** las dependencias, el hijo moría al instante con `ModuleNotFoundError` y el
  vigilante informaba «corriendo» durante horas con el PID viejo. Regla: arrancarlo con el intérprete que **tiene
  las dependencias** (el `python` del venv cuando el módulo vive ahí), chequear `import <dep>` con ESE intérprete
  antes de lanzar, y **re-chequear que el proceso siga vivo unos segundos después** — si ya murió, no guardar el
  PID y reportar el error. Para «¿está corriendo?» leer el PID del archivo, nunca un `pgrep -f <script>` (el
  propio shell se matchea).
- Corridas largas (una wallet × 300 tx, una red de 10 wallets) van en **background con aviso**, y el
  informe se entrega al terminar: no bloquear el turno esperando el RPC. Medido: ~0,5 s por
  `getTransaction` en el RPC público → **1.000 tx ≈ 10 min** (y encima la red de la wallet); en primer
  plano el timeout **mata el proceso a mitad de camino y se pierde todo lo bajado**. El informe se
  arma después, releyendo el JSON/caché.
- **Una sola pasada de `getTransaction` por firma.** `wallet_forense.informe()` la baja dos veces
  (flujos y después tokens): con historiales de 1.000+ tx eso solo ya excede el timeout. Para esos
  casos, `forense_profunda.py` (pasada única + caché `cache_tx_<prefijo>.json`) — y el caché deja
  recalcular con otros umbrales sin volver a tocar el RPC.
- **Un solo job pesado de RPC por vez** (y recordar que el cron corre `*/3` y `*/5` sobre el mismo
  RPC): en paralelo la latencia pasa de 0,5 s a >2 s por llamada y las dos corridas se estiran. Para
  mirar otra cosa mientras corre una, usar el caché ya bajado.
- **«Llega tarde» casi siempre es la PASADA que no entra en su intervalo, no el reloj.** Cronometrar la
  pasada entera (`time` al mismo comando del cron) y compararla con la frecuencia de su línea: si tarda más
  que el intervalo, las corridas se **enciman**, cada aviso sale después del disparo siguiente y el retraso es
  **estructural** — subir la frecuencia lo empeora. Medido: la pasada de vigilancia de cohortes tardaba **más de
  5 minutos** contra un cron de 6. Antes de tocar nada, **medir las piezas por separado** (una llamada de cada
  tipo): eso separa «el token tarda» de «son 40 transacciones en fila».
- **Dentro de una pasada, paralelizar los FETCHES es la palanca grande** (`ThreadPoolExecutor` + `ex.map`; lo
  lento es la red, no la CPU) — y no contradice el punto anterior, que es sobre dos pasadas pesadas a la vez.
  Medido en la misma función: `_preparar_token` de 8 tokens = **8,9 s en paralelo** contra **más de 300 s** en
  serie. El bucle interno también: `compras_de` hacía **una llamada por transacción** (hasta 40, ~0,3 s cada
  una). Dejar en **serie** lo que no se puede paralelizar: el orden de los avisos y **el envío a Discord** (el
  rate-limit del canal es por proceso). La escritura compartida ya va bajo `fcntl.flock`, y eso es lo que vuelve
  segura la lectura en paralelo.
- **Los timeouts de red hardcodeados son un sumidero invisible**: un `timeout=20` sobre una lista de 3-5
  candidatas de imagen suma **60-100 s por aviso** cuando el host está bloqueado (los gateways IPFS que bloquean
  IPs de datacenter se quedan colgados hasta agotarlo, en vez de fallar rápido). Bajarlos a **4 s**: los que
  responden tardan menos de 2 s. Y al cerrar, **cronometrar la MISMA pieza** para probar la mejora, sin
  confundir el núcleo con el total: el script entero puede seguir lento por un tramo posterior (el envío del
  aviso reanaliza el token y sube la imagen) — decir qué quedó medido y qué falta, no dar el total por resuelto.
- **Un helper que devuelve tupla y no se desempaqueta deja el chequeo vacío en silencio.**
  `insider_token.sigs_mas_viejas(addr, n)` devuelve `(firmas, páginas, total)`: al iterar la tupla (no
  una lista) el bucle no recorre nada y el resultado sale «sin datos» en **todas** las wallets, que se
  lee como «no hay fondeo» cuando el parser nunca leyó una firma. Desempaquetar y **loguear cuántos
  elementos se leyeron**; un vacío silencioso no es un dato.
- **El User-Agent por defecto de urllib da 403 en DexScreener** (igual que en Discord): con `urllib`
  pelado los pares vuelven vacíos y hasta tokens de millones de mcap se leen como muertos. Usar el
  helper del proyecto (`dexscreener(mint)`, que manda UA propio) y no interpretar el vacío como «token
  sin par».

## Entrega (preferencias de este usuario)

- **El objetivo es AVISOS, no copy-trading** (aclarado por Dylan): quiere que le avisen **qué compran**
  las wallets con info privilegiada para **analizarlo él** y decidir. Corolario: **el hold corto NO
  descalifica** — «hold ≥2 min / copiable» es criterio para copy-trading, no para avisos. Un sniper que
  compra en el arranque y vende en 1 min **sirve** como fuente de señal (su compra es el aviso). Lo que
  se exige es entrada temprana + historial verificable. **No descartar wallets rápidas cuando el pedido
  es «avisame qué compra»** — pasó y hubo que recargarlas al tracker después de haberlas descartado.
- **Solo Discord** para estos flujos: nada de Telegram.
- **Canales: probar creándolo con la API del bot** (`POST /guilds/{id}/channels`) antes de decir que no
  se puede — con `MANAGE_CHANNELS` alcanza. Si devuelve 403, lo crea el usuario y el ID va a `.env`.
  Sin canal propio los avisos caen por **cadena de fallback en un canal que el usuario no mira**: fijar
  el ID explícito y **verificar leyendo el canal**, nunca con el 200 del POST.
- **Organizar el server es un pedido recurrente («organizá y mejorá los canales»), y se hace por API**:
  una **categoría por sistema** (señales cripto / memecoins / grupos on-chain / informes / voz), nombre
  del canal **con el emoji adelante** y **una descripción (`topic`) por canal** — es `PATCH /channels/{id}`
  con `name`, `parent_id`, `position` y `topic`, y una categoría nueva es `POST /guilds/{id}/channels` con
  `type: 4`. **Renombrar y mover no rompe nada mientras los scripts usen IDs** (`DISCORD_*` del `.env`),
  pero después hay que **verificar el mapeo**: leer los canales del guild y comprobar que cada ID apunta
  al canal que uno cree — un ID corrido manda las alertas a un canal que el usuario no mira, **en
  silencio**. Dejar además un **mensaje-mapa** en el canal de bienvenida (estructura, qué es cada canal,
  cómo leer un aviso) y dar por buena la reorganización sólo después de un **aviso de prueba real** al
  canal renombrado (comprobar el color del embed y borrarlo).
- **El color del embed es el código de nivel del aviso**: en los avisos de grupo, 🏆 dorado = fue al canal
  de las mejores · 🟢 verde = grupo que seguimos · 🟠 naranja = lotería · 🟣 violeta = el resto. Color y
  canal tienen que coincidir: guardar el flag al **rutear** el aviso y leerlo en el formateador, no
  re-deducir el nivel después (si no, un aviso del canal de calidad sale pintado como lotería).
- **Texto del aviso: los que ENTRARON no son el tamaño del grupo.** Un aviso decía «100 wallets» cuando
  habían entrado 4 (100 era el tamaño del grupo): escribir «**N wallets** del grupo (**M** en total)
  entraron», con el tamaño sólo como contexto — el usuario lo reporta como bug apenas lo ve.
- El resultado debe traer **las wallets útiles de la red**, no solo el análisis: etiquetadas, con el
  motivo y con qué hacer con cada una (SEGUIR ⭐ / VIGILAR 🚨 / EVITAR).
- La etiqueta va **en el nombre de la wallet dentro del tracker** (`🚨INSIDER`, `⭐CANDIDATA pnl+12.4SOL wr64%`)
  para que el aviso se lea solo, con la imagen del token y color por tipo.
- **El canal del radar va SOLO con las ⚡ CALL** (preferencia explícita del usuario: se quejó del
  volumen). El radar corre `--vigilar --solo-rafagas`: sigue analizando por dentro (ese análisis es lo
  que alimenta al detector de ráfagas) pero **no publica tokens normales**, y el parte diario quedó
  **comentado** en el crontab (no borrado; reactivarlo es quitar el `#`, y tocar el cron requiere OK).
  **Antes de proponer cualquier umbral, medir la distribución del día** desde el estado del radar
  (`alertas_state.json` → `vistos`: puntaje y marca de alertado por token). Medido: **125 avisos en un
  día con 87 % entre 70-79** → umbral 80 deja 16/día y 85 deja 3. Proponer «subamos el umbral» sin esa
  tabla no le deja elegir. Y **silenciar no abarata el cupo**: el chequeo de ráfaga sigue costando ~260
  créditos por token joven.
- Cargar al tracker solo las **útiles y en número chico** (≈8): el canal se vuelve ruido si se vuelca
  la red entera. Una wallet **sin operaciones propias** no aporta cero: aporta ruido (avisos de
  movimientos que no controla) → queda fuera por defecto.
- **Antes de recomendar qué trackear, medir tres cosas**: saldo en SOL, último movimiento y **si la
  wallet firma sus tx** (`accountKeys[].signer`). Una wallet viva pero **sin saldo ni tokens** no es
  candidata a copiar: sirve como **detector de dump** (avisar cuándo le den la próxima tanda y empiece
  a vender) y hay que presentarla así. Medido: 6 wallets con +6 a +36 SOL, 100 % de aciertos y 67-85 %
  de posiciones sin compra estaban las 6 **vaciadas** (0 SOL, 0 tokens) y aun así moviéndose minutos
  antes — perfil bundle, no trader.
- **Cada recomendación va con la advertencia de copiabilidad**: si es un bot de 6 s o 1 min, el aviso
  llega **después** de que operó; se sigue «para enterarse», no para copiar. Decirlo explícito evita
  que el usuario crea que puede imitar la entrada.
- **Verificar por lectura que no se cargó lo que el usuario pidió dejar fuera** (`wallets.json`): si
dijo «no la pongas en el tracker hasta que encontremos algo bueno», confirmarlo en la respuesta con
esa lectura.
- **Cuando pida «la lista con nombres»**: una ficha por wallet con **apodo** corto y memorable
  (emoji + nombre: 🔬 EL ESTADÍSTICO, 🏦 LA SOLVENTE, 🚨 EL VENTAJERO), la **dirección completa en línea
  propia** (para copiar), los **números clave**, el **origen** (ronda propia o dataset) y **para qué
  sirve** + su **contra**. Agrupadas por uso (avisos / detectores de dump / PnL de un solo golpe), y la
  misma lista escrita en un `.txt` del proyecto que se manda como adjunto (`MEDIA:<ruta>`), no sólo en
  el chat.
- **El aviso tiene que gritar, no informar**: lo que se ve en la notificación del celular es el **`content` (texto ARRIBA del embed)**, así que los números de la call van ahí (`⚡⚡⚡ **CALL 4.5/10 ⚠️ MEDIA** ⚡⚡⚡ · 19 wallets · 20 s · 55.21 SOL · $SIMBOLO`), no solo dentro del embed. Sumado a: encabezado grande (`# ⚡⚡ … ⚡⚡`), color y `author` propios, las 3 métricas como primeros campos inline, y el **`timestamp` del momento del DATO** (el inicio de la ráfaga) para que Discord diga «hace 2 minutos».
- **Y tiene que entrar en una pantalla.** Pidió «resumir las calls y dejar lo realmente importante»: el aviso lleva
  sólo quién entró (con su puntaje y la muestra), cuánta plata, el token en 3-4 datos (mcap, edad, liquidez, holders)
  y el porqué en una línea por motivo. Links, contexto de mercado, flags de RugCheck y el resto van al **registro**,
  no a la notificación: lo que no cambia la decisión no se manda. Ser compacto y completo no se pelean — se resuelve
  mandando lo demás al archivo.
- **El puntaje va adelante y con el porqué a la vista**: título `⚡ <nota>/10 · <etiqueta> — <token>` y campo `🧮 POR QUÉ <nota>/10` con **una línea por motivo** (`› +4,0 fuerza · 19 wallets distintas…`). El usuario pidió explícitamente «puntualas y explicá el porqué»: un número sin desglose no le sirve para decidir, y un aviso sin puntaje lo obliga a hacer el análisis que el motor ya hizo.
- **Cuando el aviso lleva dos números, etiquetar cada uno donde aparece** (el usuario reportó «hay 2 puntuaciones en la señal»): la **fuerza de la call** (0-10) y la **calidad del token** (0-100) conviven en el mismo mensaje y sin rótulo se leen como un puntaje repetido y contradictorio. Rótulo en el texto, el título y la descripción (`CALL 8.0/10 · 🪙 token 43/100`) y **sin repetir el valor en el nombre del campo** del desglose.
- **El contrato del aviso va en un mensaje APARTE, solo con la dirección** (texto plano, sin etiqueta ni bloque
  de código): el usuario reportó «no me deja copiar los contratos» — los bloques de código dentro del embed no
  se copian en todos los clientes. Un `content` que sea **únicamente** el mint hace que el «copiar texto» del
  celular devuelva la dirección exacta. Son 2 mensajes (2 notificaciones) por call y se acepta a cambio de
  copiar de un toque; el campo del embed con los links queda como refuerzo. Receta y verificación en
  `references/calls-y-avisos.md`.
- **Un bot de terceros (Rick) NO es integrable**: Discord prohíbe que un bot use los comandos de otra aplicación
  (y los bots ignoran mensajes de bots), así que su leaderboard no se alimenta ni se consulta desde acá. No
  prometerlo: se **replica su métrica** (FDV del aviso → pico) en tabla propia y el puente es manual — un comando
  nuestro escupe los contratos y **los pega un humano**. **Y se le pasan sólo las calls RECIENTES** (últimos
  ~30 min, con la orden de pegar ya mismo): su métrica arranca en el primer scan —el momento del pegado— así que
  con calls viejas su línea base arranca corrida y no cuenta lo que el token ya subió. Comandos de autoservicio: el usuario **prefiere slash nativos sobre prefijos**, y se
  pueden sin segundo gateway — el plugin de Hermes publica el comando como `/besti` (Discord admite una sola sesión
  por token de bot). El prefijo + cron cada minuto queda sólo como respaldo (y es lo que sirve **ya**, sin esperar
  la publicación). Receta en
  `references/calls-y-avisos.md`; mecánica del plugin y política de sync en la skill `hermes-slash-commands`.
- **El 429 de Discord no se evita con un contador de ritmo en memoria**: cada corrida del cron es un proceso
  **nuevo**, así que el contador arranca en cero y entre todos los scripts igual se pasa el límite del canal
  (medido: avisos perdidos con un tope «de 20/minuto» ya puesto, porque cada proceso lo aplicaba sólo a sí
  mismo). El contador va en un **archivo** (minuto + canal), se consulta **antes** de cada POST y el aviso
  salteado **igual se registra** en el estado, para no perder la medición. Dejar margen: Discord corta cerca de
  30 mensajes/min por canal → tope ~15. Esto deja de ser teórico justo cuando el usuario pide **maximizar**
  umbrales: ahí el volumen se multiplica y sin freno compartido se pierden avisos en silencio. **Y un cupo por hora sin intervalo mínimo deja el canal mudo**: se agota en los primeros minutos de la hora y no vuelve a hablar hasta la siguiente, y el usuario lo reporta como «no me llega nada» — el cupo no estaba mal, faltaba el goteo. El freno va como **goteo: cupo por hora + mínimo entre avisos** (p. ej. 10/hora con 90 s entre uno y otro), aplicado **por canal** y no global; y el aviso salteado **se registra igual** (si no, la medición se sesga hacia las horas flojas).
- **Diseñar el aviso para la señal que importa, no para cada evento**: con umbrales bajos, avisar cada compra
  suelta de una wallet vigilada produce un río (~160/hora medido) y el canal deja de leerse. La señal es la
  **entrada coordinada** (≥2 wallets del mismo grupo en el mismo token dentro de una ventana) y las granjas de
  bots se saltean.
- **Corridas largas: ETA por adelantado y ofrecer acortar.** Una ronda de descubrimiento dura ~40 min;
sin ETA el usuario pregunta «¿cómo vas?» cada pocos minutos. Contestar con el avance real (X/N), la
ETA y una salida: «salteo las últimas 5 y te doy la tabla en 12 min» — y recordarle que el aviso llega
solo al terminar (background con notificación), para que no tenga que vigilar.
- **El cron corre en la hora LOCAL del host (UTC-4 acá), no en UTC**: un parte para las 08:00 locales
  se agenda `0 8 * * *`; pensarlo como "12:00 UTC" lo desfasa 4 horas. Calcular la hora objetivo en la
  zona del host antes de escribir la línea, y **esperar una corrida real** para darla por buena.
  Corolario que ya costó un falso diagnóstico: los **logs del proyecto están en UTC** mientras el reloj
  local está en UTC-4, así que un log cuya última línea dice `12:25` con el reloj en 08:30 está
  **fresco**. Antes de declarar un sistema «caído por silencio», correr `date` y comparar zonas; y si el
  log parece detenido, ejecutar el comando del cron a mano (con su mismo intérprete y su mismo
  redireccionamiento) para ver si escribe — eso separa «no corre» de «no me estoy confundiendo de hora».
- Cuando pida «verificá que todos los sistemas anden» (calls + cohortes + bot RSI): seguir el recorrido
  por componente de `references/verificacion-de-sistemas.md` — incluye las marcas de log de cada script,
  la lectura del canal por API y las trampas de hora y de `pgrep` que hacen reportar un falso «caído».
- **Tocar el crontab requiere OK explícito del usuario**: proponer la línea, decir qué cambia y esperar
  confirmación. Si ya la negó una vez, no reintentar cada turno.
- Al guardar una corrida, escribir el JSON de resultado en el directorio del proyecto
  (`wallets_clasificadas.json`, `auditoria_wallets.json`) para poder releerla sin repetir el RPC.
- Español, emojis para ordenar, y cierre con **«Conclusión»** resumiendo lo esencial.
