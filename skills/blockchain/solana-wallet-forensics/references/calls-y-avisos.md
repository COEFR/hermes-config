# Detector de calls (ráfagas) y layout del aviso

Implementación de referencia en el proyecto: `~/.hermes/data/memecoins/calls_detector.py` (detección, señales
que acompañan y tope de gasto) enganchado en `pump_analizador.vigilar()` (encolado + re-chequeo) y
`pump_analizador.embed_de()` (dibujo).

## Qué se detecta

De las últimas **40 tx del pool** (no del mint) se toman las **compras reales** (Δtoken > 0 y ΔSOL < 0,
descartando polvo) y se buscan ventanas con:

| Constante | Valor | Por qué |
|---|---|---|
| wallets distintas | ≥3 | 2 puede ser casualidad; 3 wallets distintas en 2,5 min no |
| ventana | 150 s | el ancho real de una call de grupo (90 s dejaba fuera las que entran escalonado) |
| tamaño por wallet | ≥0,3 SOL | filtra a los que prueban con migajas sin perder a los que entran chico |
| tx leídas del pool | 40 | ~410 créditos por chequeo (10 de firmas + 10 por tx); cubre ~10 min de actividad |
| tope diario | sin tope (el usuario pidió no limitar Helius) | con el tope puesto el detector se cortaba solo; ahora se le informa el ritmo medido |
| tokens por pasada | 8 (≤120 min, por mcap desc) | cubre más tokens por pasada; el cupo es uno solo para todos los procesos |

Se publican: `n_wallets`, `sol` (suma puesta), `segundos` (ventana), `hora` y `ts_iso` del **inicio**.

## El bug de cobertura: cada token se chequeaba UNA sola vez

La primera versión chequeaba ráfagas **solo en el momento en que el radar analizaba el token**. Si la call
salía 10-30 min después de ese análisis, **se perdía para siempre** — era la causa principal de que llegaran
pocas calls, y el arreglo no es bajar umbrales.

**Regla: mientras un token sea joven, se re-chequea en cada pasada.** En `vigilar()`, la lista de candidatos a
ráfaga se arma con (a) los tokens frescos de esta pasada **más** (b) los ya vistos con **≤2 h de vida**
(guardando `creado`, `mcap` y `simbolo` en el estado `vistos` al analizarlos; antes solo se guardaba el
puntaje y no había con qué reconstruir la lista). Sin el re-chequeo, la tasa de acierto queda limitada por la
ventana de análisis, no por el mercado.

Corolario de presupuesto: el gasto del detector es proporcional a **chequeos**, no a tokens únicos, así que al
ampliar cobertura o ventana hay que subir el tope diario y no el de tokens por pasada.

## Señales que acompañan a la ráfaga (las que la vuelven legible)

- **Compras en el MISMO SLOT**: los slots de Solana duran ~400 ms, así que dos compras en el mismo slot no se
explican por coincidencia. Se cuentan las wallets distintas que comparten slot y, con **≥3**, el aviso sube de
tono: título `🚨 BUNDLE EN EL MISMO SLOT` y línea propia en la descripción. Es la señal más dura de
coordinación y la técnica que usa la detección de sybil por co-trade.
- **Carteras NUEVAS vs CONOCIDAS**: por cada wallet de la ráfaga se mira su historial (`getSignaturesForAddress`
con `limit` chico: <20 firmas y saldo bajo = nueva) y, aparte, si está en nuestras listas puntuadas. El aviso
dice cuántas son nuevas (firma de bundle armado al vapor) y cuántas ya conocidas (call de gente real). Cuesta
~20 créditos por wallet y solo corre cuando ya hay ráfaga.
- **Volumen de la ventana**: cuántas compras hubo en la ventana además de las que pasan el filtro de tamaño
(`› en la misma ventana hubo N compras en total`). Separa «3 wallets grandes» de «una estampida».

Medición que estas señales ya dejaron: en las ráfagas reales observadas las carteras salen **ni nuevas ni
conocidas** (0 y 0), o sea **carteras con historia** → refuerza que la unidad de señal es el **evento del
token**, no la wallet. Un bundle de wallets nuevas al vapor es otra cosa (y viene con muchas en el mismo slot).

## Qué descarta un aviso y qué no: el PUNTAJE es el filtro, no un candado

**No hay candado de tamaño ni de fuerza: se avisa TODAS las calls y el puntaje 0-10 hace de filtro** (pedido
explícito del usuario: «avísame de todas, pero puntualas — si tiene 20 k de mcap que sea bajo y si es como TMNP
alto — y explicá el porqué»). Un candado que esconde señales le quita la decisión al usuario; el número con su
desglose se la devuelve. Lo único que se descarta es el token de **`edad <10 min`**: ahí el analizador está en
plena **ventana de snipers** y salía el aviso contradictorio «CALL DETECTADA» con «NO VALE LA PENA · 0/100»
debajo — en los primeros minutos no hay call accionable, hay bots. Los descartados se loguean (`ráfaga
descartada en X: … (ventana de snipers)`) para poder auditar la decisión después.

El detalle de liquidez **no se descarta, se puntúa**: **DexScreener reporta liquidez $0 en los tokens que siguen
en la curva de pump.fun**, así que «liquidez 0» no puede ser un veto (descartaría justo los tokens recién
lanzados, que es donde pasan las calls): entra como **−1,0 «sin salida»** en el puntaje, con el texto que lo
explica («si comprás, después no vas a poder vender»).

### Puntaje 0-10 de una call (con el porqué desglosado)

`calls_detector.puntuar(raf, ctx)` devuelve `(nota, motivos[], etiqueta)`. Los pesos salen de medir el resultado
de las calls (tabla en «Medir cómo les fue»), no de la intuición:

| Bloque | Regla | Puntos |
|---|---|---|
| **Fuerza** | wallets **distintas** en la ráfaga: ≥15 · 10-14 · 8-9 · 5-7 · <5 | +4 · +3,5 · +3 · +1,5 · +0,5 |
| **Volumen** | SOL total de la ráfaga: ≥50 · 25-50 · 10-25 · <10 | +3 · +2 · +1 · 0 |
| **Cuerpo del token** | mcap ≥150 k · 100-150 k · 50-100 k · **<50 k** | +2 · +1,5 · +0,5 · **−1,5** |
| **Salida** | liquidez ≥20 k o curva ≥50 % · sin salida | +1 · −1 |
| **Bundle** | ≥3 compras en el **mismo slot** | **−2** |
| **Carteras nuevas** | ≥60 % de la ráfaga sin historial | **−1,5** |
| **Carteras conocidas** | +0,75 cada una (máx +1,5) | +0,75 |
| **Edad** | token de <10 min | −1 |

Tramos: **≥8 🔥 ALTA · 6-8 ✅ MEDIA-ALTA · 4-6 ⚠️ MEDIA · <4 🚫 BAJA**. Cada motivo se publica como línea
(`› **+4,0 fuerza** · 19 wallets distintas entraron: eso es demanda real, no un par de amigos`), así el usuario
ve de dónde sale cada punto y no un número huérfano.

Backtest del puntaje contra el resultado real de las mismas 8 calls: las 7 que perdieron dieron **0,0-3,5/10
(🚫 BAJA)** y la única que ganó (2,5x) dio **10,0/10 (🔥 ALTA)**. El puntaje separa, y por eso puede reemplazar
al candado. Los pesos son de muestra chica: al ajustarlos, volver a correr ese backtest antes de tocarlos.

**La ráfaga avisa por sí misma**: si aparece, el token se publica **aunque el puntaje no llegue al umbral** (con
el bloque ⚡ y el veredicto visible igual), porque la señal es el evento, no la nota del token.

**Detección y publicación son dos pasos distintos**: cuando un aviso no aparece, el log tiene que estar en el
**punto de encolado** (`⚡ ráfaga ACEPTADA … → al canal`), no solo donde se detecta la ráfaga; sin ese log no se
distingue «no hubo ráfaga» de «la ráfaga no llegó a la lista de avisos».

## Layout del aviso

```
[content — lo único que se ve en la notificación del celular]
⚡⚡⚡ CALL 4.5/10 ⚠️ MEDIA ⚡⚡⚡ · 19 wallets entraron en 20 s con 55.21 SOL en $TMNP

[embed]
author     ⚡ Detector de ráfagas
title      ⚡ CALL <nota>/10 · 🪙 token <calidad>/100 — <nombre> · $<símbolo>   |   🚨 BUNDLE en …
desc       # ⚡⚡ CALL DETECTADA ⚡⚡                      ← encabezado grande (# = H1)
           4 wallets distintas entraron en 15 s poniendo 13.78 SOL
           › 🚨 3 de esas compras cayeron en el **mismo slot**   ← solo si las hay
           › en la misma ventana hubo 10 compras en total
           › arrancó 17:03 UTC · pool `<addr>`
           👉 ¿Qué es esto? Varios wallets distintos comprando el MISMO token en el mismo momento
              no es casualidad: es una compra coordinada (call de un grupo o un bundle).
           ────────────────
           ### FUERZA DE LA CALL: <nota>/10 <etiqueta> · CALIDAD DEL TOKEN: NN/100
color      ámbar `0xFFB300` en las calls; en el resto, por veredicto
fields     ⚡ Wallets `19` · 💸 SOL puestos `55.21` · ⏱️ Ventana `20 s`   (inline, primero)
           📋 CONTRATO  ← el mint suelto + links (refuerzo de escritorio; la vía de copiado es el mensaje aparte)
           🧮 POR QUÉ ESE PUNTAJE DE FUERZA  ← una línea por motivo (truncar a 1024 chars)
           después los 6 de mercado: mcap, curva, edad, holders, liquidez, compras/ventas
timestamp  `ts_iso` del INICIO de la ráfaga → Discord lo muestra «hace 2 minutos»
image      la del token: LISTA de candidatas probadas en orden (ver «Imagen y nombre del aviso»)
           — `attachment://` se reemplaza ANTES de serializar el payload
footer     `<mint> · solo informa, no opera`   ← de acá se lee el mint al auditar, nunca del mensaje siguiente
```

**El contrato va en un mensaje APARTE que contiene SOLO la dirección, en texto plano.** El bloque de código
dentro del embed (y el del `content`) no se puede copiar en todos los clientes: el usuario reportó «no me deja
copiar los contratos». Un mensaje cuyo `content` sea **únicamente** el mint hace que el «copiar texto» del
celular devuelva la dirección exacta, sin etiqueta ni formato que borrar después. Cuesta 2 mensajes (2
notificaciones) por call y se acepta. El campo del embed con el contrato y los links (pump.fun · Solscan ·
DexScreener) se mantiene como refuerzo para escritorio, no como la vía principal.

Verificación del arreglo sin ensuciar el canal: mandar la call de prueba **a otro canal** (p. ej. el home,
`alertar_token(ev, canal=<id>)`), releer los 2 últimos mensajes e imprimir `repr(m['content'])` — el del
contrato tiene que ser exactamente la dirección — y **borrarlos** (`DELETE /channels/{id}/messages/{msg}`).

### Aviso de grupo (Argos): compacto, 4 líneas

El usuario pidió «resumí un poco las calls y dejá lo realmente importante». Formato que quedó:

```
🕸️ GRUPO 4/100 wallets · 🪙 token 51/100 — Pelago · $PELAGO
**4 wallets** de **Red de 100 de COIN (lotería)** · **3.95 SOL** en 1 min
👤 🟢`BWBd3hj2…` +12,8 (8 ganadoras/61) · 🟢`DYXDDrZ…` +12,3 (6/20) · `48hodZjh…` -0,3 (0/3)
FDV $100k · 30 min · 100 holders · liq $40k
`<mint>`
🔗 Links · Pump.fun · Solscan · DexScreener     ← único field
```

Lo que **se queda**: quién entró con su **PnL de copia** y ganadoras cazadas · cuánta plata y en cuánto tiempo · el
 token en **4 datos** (FDV, edad, holders, liquidez) · el mint (y aparte, en texto plano). Lo que **se va**: el
 encabezado `#` gigante, el perfil del grupo, el origen, las repeticiones, los 6 campos de mercado redundantes, la
 lista de motivos del puntaje y la lista larga de miembros — todo eso vive en el registro y en `!grupos`. Regla: en el
 embed va **primero lo que decide** y el resto se corta, porque el aviso se lee en la notificación del celular. La
 primera línea dice **cuántas wallets entraron**, nunca el tamaño del grupo (bug reportado por el usuario: ver
 `references/grupos-coordinados.md`).

### Los DOS puntajes van etiquetados, sin excepción

La señal lleva **dos números de escalas distintas** —la **fuerza de la call** (0-10, nuestra) y la **calidad del
token** (0-100, el veredicto del analizador)— y sin etiqueta se leen como un mismo puntaje repetido y
contradictorio: el usuario reportó «hay 2 puntuaciones en la señal». Etiquetar los dos **en cada lugar donde
aparecen** (texto de arriba, título, descripción) y **no repetir el número en el nombre del campo** del
desglose (`🧮 POR QUÉ ESE PUNTAJE DE FUERZA`, sin el valor). Regla general: cuando dos métricas conviven en un
aviso, el que las lee tiene que poder decir cuál es cuál sin conocer el código.

### Imagen y nombre del aviso: lo que no está en pump.fun se resuelve afuera

Dos fallas silenciosas de la misma raíz (el token ya salió de las listas de pump.fun y no hay `image_uri` ni
`símbolo` propios):

- **Un solo origen de imagen no alcanza.** Con `info.imageUrl` de DexScreener vacío, la cadena caía a la imagen
de pump.fun servida por **`ipfs.io`, que da 403 desde este equipo**, y la descarga moría → el embed salía **sin
foto** (medido en 3 avisos seguidos). La imagen tiene que armarse como **lista de candidatas probadas en orden**:
`info.imageUrl` de DexScreener → la misma imagen **reescrita** por un gateway que responda
(`gateway.pinata.cloud`, `ipfs.filebase.io`, `4everland.io`) → `images.pump.fun/coin-image/<mint>?variant=600x600`
→ `pump.fun/api/og/coin/<mint>`, descartando el md5 de la imagen genérica. El descargador acepta la lista y se
queda con la primera que devuelva bytes.
- **El nombre sale del stub.** Cuando el token no está en las listas de pump.fun, el análisis cae al stub y el
aviso muestra **`$?`** y el prefijo del mint como nombre. Resolver `símbolo`/`nombre` desde **DexScreener**
(`baseToken.symbol`/`name`) cuando vengan vacíos o `"?"`. La prueba es un token que ya no está en las listas:
antes salía `?`/`6Ui5YJxy`, después `Shield Pad`/`$SHIELD`.

## Medir cómo les fue a las calls (el filtro que faltaba)

Receta: `GET /channels/{id}/messages?limit=100` (**más de 100 devuelve HTTP 400**) → por cada aviso sacar el
**mcap del embed en ese momento** («Market cap»), las **wallets y SOL** del `content`, y el **mint del PIE del
embed** (`footer.text`, formato `<mint> · solo informa, no opera`). Después `DexScreener /tokens/{mint}` → mcap
de ahora → **ratio**. La tabla sale **sin gastar RPC** (DexScreener es gratis) y sin depender de la memoria.

**El mint NUNCA se saca del «mensaje siguiente»** (el de la dirección pelada): si a una call le falta ese
mensaje, el pareo se corre una posición y se le atribuye el resultado del token equivocado. Pasó: se reportó un
ganador de **3,2x** que en realidad era **0,01x (−99 %)** — el usuario lo cazó. Empatar por `footer.text` o por
`embed.timestamp`, nunca por vecindad.

Resultado medido y **corregido** (8 calls, mismo día; wallets y SOL de la ráfaga incluidos porque son la señal
que separa):

| Call | wallets | SOL | mcap en la call | ahora | ratio |
|---|---|---|---|---|---|
| Ragebaitoor | 4 | 13,8 | 3,6 k | 3,3 k | 0,91x |
| Qual | 4 | 9,1 | 28 k | 22,2 k | 0,79x |
| SHROOM | 3 | 4,9 | 31 k | 8,3 k | 0,27x |
| xFloor02 | 7 | 8,9 | 29 k | 2,2 k | 0,08x |
| CALL (1800PhoneCex) | 3 | 4,5 | 237 k | 189 k | 0,80x |
| LOOP | 3 | 3,5 | 142 k | 72 k | 0,51x |
| mLVvkifg… | 4 | 1,9 | 130 k | 1,0 k | 0,01x |
| **TMNP** | **19** | **55,2** | 227 k | 570 k a los ~20 min → **3,1 k** después | **2,51x → 0,01x** |

**La columna «ahora» es una foto, no un veredicto.** Lectura **corregida dos veces**: de 8 calls **ninguna
terminó en verde**, y el «ganador de 2,51x» fue un dato de un momento — TMNP llegó a 570 k a los ~20 min y
cerró en **3,1 k (−99 %)**. Lo que sí separa es la **fuerza de la ráfaga**: la única que **dio ventana de
ganancia** tenía **19 wallets distintas y 55 SOL**, y todas las demás (3-7 wallets, ≤13,8 SOL) **nunca subieron
por encima del precio del aviso** (mejor momento 0,08-0,91x). Más wallets distintas = más gente real comprando;
3 wallets con 3 SOL es un par de amigos o un mini-bundle. Presentar esta tabla cuando pregunte «¿cuáles salieron
bien?», con la advertencia honesta de que **8 calls es muestra chica**.

**Nunca juzgar una call con una lectura de minutos después** (clave, y se falló dos veces): leerla a los 20 min
dio «2,5x» en la que después hizo **−99 %**. El veredicto sale de la **serie de precios desde el aviso** —
sección siguiente.

## Medir el resultado de cada call: serie de precios, pico y ventana

Implementado en `~/.hermes/data/memecoins/registro_calls.py` (registro + muestreo + informe). Tres piezas:

1. **Registro automático.** `alertar_token()` llama a `registro_calls.registrar(raf, ev)` al mandar el aviso: se
guarda el mcap/liquidez del momento, la nota con **los motivos línea por línea**, wallets, SOL, slots, calidad
del token y el `ts_epoch`. Dos filtros aprendidos: **no re-registrar el mismo mint dentro de ~6 h** (el mismo
token se re-alerta y duplicaba las entradas) y **descartar mcap >50 M** (activos tokenizados y stablecoins se
cuelan en las listas del radar y generan «calls» de $168 M que no son memecoins).
2. **Muestreo de precio cada 5 min durante 6 h** (`--muestrear` por cron): append `{t, mcap}` **solo con
DexScreener, cero créditos de Helius**. Sin esta serie el pico no existe: es la pieza que responde «¿después del
aviso subió?».
3. **Pico y ventana** (`_pico`): máximo de la serie (y del `ath_market_cap` de pump.fun **si su timestamp es
posterior al aviso**) → **(múltiplo respecto al mcap del aviso, minutos desde el aviso)**. De ahí salen: % de
calls **con ventana** (>1,05x), pico promedio, mediana del tiempo hasta el pico y «si vendías en el pico» vs
«si aguantabas». Chequeos en 1 / 6 / 24 h (`--evaluar`, cron cada 30 min) para el método viejo, que sigue
sirviendo de contraste.

**Marcar la serie que arranca tarde (`serie_tardia`) y no contarla como «no hubo ventana».** Si el seguimiento
empieza >30 min después del aviso, el pico **no es reconstruible hacia atrás**: contarla en el denominador hace
decir al informe cosas que no puede saber. Se marca, se informa cuántas quedaron afuera y recién se cuenta sobre
las que tienen serie propia. Sembrar a mano mediciones propias viejas **se puede**, marcándolas como tales
(campo `fuente`), para que el informe arranque con datos en vez de vacío.

Resultado medido (8 calls con serie desde el aviso): **1 con ventana de ganancia** (la de 19 wallets y 55 SOL,
**2,45x a los 39 min**, después −99 %), **pico promedio 0,649x**, mediana del tiempo hasta el pico **105 min**,
el más rápido 39. Dos conclusiones que ordenan el diseño: (a) **el pico es lo que hay que predecir**, no el
valor final — el puntaje acertó en señalar la única con ventana (fue la de 10/10, 🔥 ALTA); (b) **la ventana es
corta** (39-105 min): si aparece, se toma ahí. Con muestra de 8 sigue siendo indicio, no veredicto.

## Presentar resultados: el podio no es la estrategia (y hay que decirlo)

Una tabla de «top 8 del día» con picos de 11,5x / 8,2x / 7,5x **se lee como una estrategia ganadora y no lo es**.
Antes de publicar el podio, calcular **cuánto daba comprar TODAS las calls** con la misma apuesta y una regla de
salida fija: la suma de `(múltiplo − 1)` sobre la muestra, usando la serie de precios de cada call.

| Regla de salida | Total (por apuesta) |
|---|---|
| al primer muestreo (~4 min) | **−9,6** |
| al primer ≥1,5x (si no llega, al final) | **−23,0** |
| a la hora | **−38,3** |
| aguantar hasta el final | **−42,0** |

114 calls, extremos reales. Lectura: los ganadores existen y son enormes, pero **no pagan la sangría** del resto
(la mayoría cae a 0,2-0,4x) y **aguantar multiplica la pérdida por 4** — la regla de salida pesa más que la
entrada. Al informar: (1) publicar el total de «comprar todo» **al lado** del podio; (2) decir que el **pico** es el
mejor momento posible, no una salida que uno capture solo; (3) recordar que la serie es cada ~4 min y **sin
comisiones** (2,5 % ida y vuelta) → la realidad es peor.

**El puntaje de CALIDAD DEL TOKEN (0-100) no discrimina: no usarlo para seleccionar.** Medido sobre 114 calls,
comparando las de pico ≥2x (16) contra el resto (98): puntaje 30 vs 31, FDV del aviso $24,9k vs $23,1k, liquidez
$45,5k vs $112,7k, edad 21 vs 25 min → **ningún separador**. Lo único que mostró diferencia fue el **SOL de la
ráfaga** (3 vs 1) y las **wallets de grupos trackeados dentro** (69 % vs 50 %, señal débil). La selección tiene que
salir de ahí (fuerza de la ráfaga + grupos), no del puntaje del token.

**Techo de FDV: un token que ya corrió no tiene múltiplo.** Medido: las cinco calls del día con FDV alto
(OIL $3,0 M · IOF $3,1 M · Speed $701 k · Joker $608 k · NASA $879 k) terminaron **todas en 0**, mientras **todos**
los ganadores salieron de $16 k-$404 k. El filtro de calidad corta por arriba (`mcap_max` ≈ $500 k): se avisa sólo
hasta ese techo y las de arriba se **registran en silencio**, para seguir midiendo el tramo.

**Un pico igual al FDV del aviso es un dato, no un bug de muestreo.** Cuando el «pico» coincide exactamente con el
FDV del aviso, el token **nunca subió por encima del aviso** — verificado contra la serie cruda (los muestreos sí
se mueven: varias bajaron a 0,2-0,3x). Antes de culpar al muestreo, leer la serie; y en la ficha poner la nota
`(nunca pasó del aviso)` **más la columna «ahora Xx»**, porque un veredicto que sólo muestra el pico **esconde la
caída** (medido: la lista decía 1,00x y el token valía 0,24x).

## Por qué llegan pocas calls: revisar en este orden

El usuario pregunta seguido «¿por qué salen tan pocas?». No adivinar ni bajar umbrales primero:

1. **¿El servicio está vivo?** por **PID** (`ps -p $(cat vigilante.pid)`), no por nombre.
2. **¿Hay excepciones en el log de cada componente?** Un error en el bloque de ráfagas del radar **mata las
   calls del radar en cada pasada sin ruido visible**: el sistema «parece andar» (analiza, silencia) y desde
   afuera se lee como mercado flojo. `grep -E "Error|Traceback|is not defined"` sobre `logs/cron.log`.
3. **¿Cuántas evaluaciones y cuántos avisos?** Muchas evaluaciones con 0 avisos = el problema está en la
   **lectura** de la ráfaga, no en el mercado.
4. **¿De qué lado de la ráfaga se lee?** Regla dura: **leer el ARRANQUE de la ráfaga, no la cola.** Las últimas
   N tx de un token que ya está bajando son **todas ventas** → el detector nunca ve los 3 compradores. Medido:
   con la cola, **314 evaluaciones y 0 avisos**; mirando el arranque (primeras 20 tx de la ventana) vuelven a
   salir calls.
5. **¿La lista de jóvenes está poblada y el tope de suscripciones la cubre entera?** Con `MAX_POOLS` por debajo
   del tamaño de la lista, la mitad de los tokens no se vigila nunca (había 38 jóvenes y tope 18).
6. **Recién ahora** mirar los umbrales, y decirle el costo de bajarlos: más avisos = más polvo.

**La realidad del mercado que hay que decir junto a eso:** buena parte de las «ráfagas» de tokens jóvenes son
**polvo** — compras de **0,002-0,03 SOL** por wallet (bots de volumen), que el filtro de tamaño ignora **a
propósito**; y las ráfagas fuertes (≥15 wallets, ≥50 SOL) son **unas pocas por día**. «Pocas calls» suele ser el
filtro haciendo su trabajo, no una falla.

## De dónde salieron estas señales (para volver a buscar cuando haga falta)

- `baronguyen001/wallet-cluster-detector` — *un clúster de carteras **puntuadas** comprando el mismo token
dentro de una ventana es la señal; seguir una sola cartera es ruido*.
- `agiprolabs/sybil-detection` — co-trade por **slot** como prueba de coordinación (el mismo-slot de acá).
- `RachitSrivastava12/dec-clust` — clúster por fondeo + compras + patrón de gasto, para detectar acumulación
**antes** del movimiento de precio.
- `Karma-234/sol-whisperer` — detección por **spike de volumen de swaps** en vez de por wallets.
- Whitepaper de DeFade — **fresh wallet flagging** (de ahí el conteo de carteras nuevas).
- Notas de freedomcore — **no medir bundles por «supply retenido»**: los bundlers no retienen, venden rápido.
- Docs de Helius **LaserStream** — de ahí salió el salto a WebSocket, ya **validado y en producción** (ver
«Modo en vivo por WebSocket»).

## Modo en vivo por WebSocket (validado)

`vigilante_calls.py` (mismo proyecto) reemplaza el sondeo por una **suscripción WebSocket** y avisa la ráfaga en
segundos. Corre como servicio con keepalive por cron (`*/5`, `arrancar_vigilante.sh`) sobre
`wss://mainnet.helius-rpc.com/?api-key=<key del .env>` — handshake **HTTP 101**. La dependencia hay que
verificarla **con el intérprete exacto con el que se lanza** (`<py> -c "import websockets"`): en este equipo
`python3` y `/usr/bin/python3` (el del cron) pueden ser versiones distintas y una de las dos puede no tenerla —
usar el `python` del venv cuando el módulo vive ahí, y no asumir.

Qué suscripción sirve, medido (`logsSubscribe`):

| Filtro | Resultado |
|---|---|
| `mentions: [mint]` | **la que sirve**: notifica cada trade del token, en la curva y en PumpSwap |
| `mentions: [pool]` | **casi nunca dispara** (0-2 avisos en 25-40 s sobre un pool con 100+ firmas recientes) |
| `mentions: [programa pump.fun]` | **firehose**: ~7.800 notificaciones en 25 s → no viable |
| `accountSubscribe [pool]` | sin notificaciones útiles |

Arquitectura: el radar deja `tokens_jovenes.json` (mint + pool + símbolo de los tokens ≤2 h); el vigilante lo
relee cada 60 s, suscribe el **mint** (tope 18), guarda `(ts, firma)` por token (ventana 150 s) y **dispara por
RITMO**: ≥8 notificaciones en los últimos 60 s — usar el total de la ventana dispara igual con tokens que ya
estaban calientes y no son una call nueva. Al disparar baja 6 tx y aplica los mismos candados del detector.

**El mapeo suscripción→token NO es el `id` de la petición**: la respuesta del `subscribe` trae el `result` (id
del nodo) y cada notificación llega con `params.subscription` = ese número. Guardar `id_peticion → mint` al
enviar y `result → mint` al recibir; sin ese mapa no se sabe de qué token es el aviso.

**El bucle de evaluación es el gasto que hay que entender antes de tocarlo.** Evaluar en **cada** notificación
una vez pasado el umbral quemó **10.200 créditos en 3 minutos** (≈5.600/min) — no es «el costo de la
suscripción», es un bucle mal puesto: la evaluación se dispara por **RITMO** (≥8 notificaciones en 60 s) y
**una vez por disparo**, no por notificación. Bien puesto, una evaluación cuesta ~60 créditos (`TX_POR_EVAL = 6`
alcanza para ver 3 wallets; subir a 8-12 tx solo encarece).

**Sobre los topes de gasto: este usuario pidió explícitamente NO limitar Helius.** Con eso, el tope global por
hora y el diario quedan **sin efecto** (valores altos, no borrados) y lo que sigue vigente es el freno
**lógico**: no reevaluar el mismo token antes de ~5 min y no repetir el aviso del mismo token antes de ~15 min
(sin esto, el mismo aviso llega decenas de veces por minuto). En ese modo hay que **decirle el ritmo medido**
(~2 evaluaciones/min sostenidas ≈ 170 k créditos/día solo del vigilante → el plan gratis de 1 M se agota en
2-4 días, y cuando se agota **dejan de llegar las calls**) y ofrecer el plan pago (10 M ≈ 9 M/mes de uso) —
pero no reintroducir topes por cuenta propia.

**Servicio: verificar por PID, no por nombre.** `arrancar_vigilante.sh` usa archivo de PID (`kill -0
$(cat vigilante.pid)`); con `pgrep -f vigilante_calls.py` el script se encuentra a sí mismo (o a cualquier shell
cuya línea de comandos nombre el archivo) y sale sin arrancar nada. Y el `log()` escribe **solo a stdout** con el
arranque redirigiendo a `logs/vigilante_calls.log`: escribir también al archivo desde la función duplica cada
línea. Verificación real: `ps -p $(cat vigilante.pid)` + el log + el gasto en `vigilante_estado.json`.

### Aviso por WALLET copiable: el vigía en vivo (`vigilante_copiable.py`)

Es el mismo WebSocket, pero suscrito a las **wallets** en vez de a los tokens: apenas una wallet que ya
puntuamos compra, el aviso sale — sin esperar a que se junte un grupo ni a la pasada del cron. Medido: **0,7-0,9 s**
desde el bloque, contra **~4 min de mediana** del sondeo por patrulla (que es el «me llegan tarde» del usuario).
Corre como servicio con `arrancar_vigia.sh` (keepalive `*/5`) y la patrulla queda de red de fondo.

Trampas medidas, en orden de aparición:

1. **El commitment.** Leer la tx del aviso con el commitment por defecto devuelve `null` y **todas** las compras se
   pierden en silencio (ver «Trampa nº 2 del RPC» en `SKILL.md`): `"commitment": "confirmed"`.
2. **Una suscripción por wallet y un mapa `suscripción → wallet`.** En la notificación **no viene la dirección**
   (sólo el id de suscripción): buscar la wallet dentro de los logs (`if w in logs`) **nunca** matchea y el vigía
   no ve nada. Guardar el `result` que devuelve cada `subscribe` contra su wallet al recibirlo.
3. **El aviso trae SÓLO los logs**, no la transacción (`params.result.value.{signature, logs, err}`): para saber
   si es compra hay que pedir la tx aparte. (El `transactionSubscribe` que entrega la tx ya parseada —y ahorraría
   el pedido— no está disponible en el plan gratis: el camino es `logsSubscribe` + `getTransaction`.)
4. **Filtro barato por log ANTES de pagar la lectura**: sólo consultar la tx si el log parece compra
   (`"Instruction: Buy"` y no el patrón de venta). Sin ese filtro se paga una lectura por cada mensaje (medido:
   561 mensajes en 45 s con 62 wallets).
5. **Una compra en el log no es una compra de NUESTRA wallet**: en una tx ajena puede estar sólo mencionada. La
   confirmación es el parseo por balance (Δtoken > 0 **y** ΔSOL < 0 de esa wallet, descartando polvo); si no,
   se cuenta como «no era compra» y se sigue.
6. **Frenos obligatorios (una wallet copiable hizo 50 compras en 55 s).** Piso de **0,1 SOL** (por debajo es
   polvo: muchas de 0,01), **3 min de enfriamiento por wallet** y **tope de avisos por hora** en el canal. Sin
   frenos, el canal del aviso instantáneo se convierte en un río y el aviso deja de significar algo.
7. **Logear la demora en cada aviso** (`tardó 0,7 s desde la compra`): es la prueba de que el modo en vivo está
   cumpliendo, y sin ese número no hay forma de contestarle «¿llegan tarde?» con datos.

## Entrega bajo volumen alto: el control de ritmo de Discord

Con los umbrales bajos y varios tokens jóvenes por pasada, el detector larga muchos avisos **juntos** y Discord
contesta **429 Too Many Requests**: medido, **8 fallos en un minuto y avisos PERDIDOS** (no retrasados: el embed y
su mensaje de contrato no llegaron nunca). Reintentar no alcanza porque el corte es por ventana.

Freno en el punto de envío — `enviar_embed()` y `enviar_en_canal()` de `pump_analizador.py` — con un contador
**compartido en archivo** (`discord_ritmo.json`: minuto + canal, tope ~15 msg/min por canal, contando que cada
call son **2** mensajes por el contrato aparte). **El contador en memoria NO sirve**: cada corrida del cron es un
proceso nuevo que arranca en cero, así que entre todos los scripts igual se pasa el límite del canal (medido:
avisos perdidos con un tope «de 20/minuto» ya puesto, porque cada proceso lo aplicaba sólo a sí mismo). Se
consulta **antes** de cada POST; pasado el límite el aviso se **saltea y se loguea** (`aviso salteado: ritmo máximo…`). Lo que
NO se saltea es el **registro**: la call se guarda igual, así la medición de resultados no pierde muestras por un
límite de entrega. Si el usuario pide más volumen, se sube el límite o se abre otro canal — el freno no se saca.

## Tabla propia del líder de resultados y comandos de autoservicio

Implementación: `tabla_calls.py` (tabla) + `comando_discord.py` (comandos), sobre el registro de `registro_calls.py`.

- **La métrica para comparar con un líder externo (Rick `/ga`) es «FDV del aviso → PICO posterior»**, no el valor
  final: el final castiga al que ya se fue (mediana **0,48x**) mientras que al pico la mediana es **~1,0x**, con
  **15 % ≥1,5x**, **10 % que dobla** y **4 % que triplica** sobre ~100 calls con seguimiento; los mejores picos
  llegaron en **5-45 min**. Al informar, **decir con qué métrica se está midiendo** — la misma muestra se lee como
  desastre o como oportunidad según cuál se elija.
- **Enviadas vs frenadas por el filtro de calidad**: el registro marca cada call como **salió al canal** o
  **frenada** (`silenciosa`), y la tabla compara los dos tramos. Es lo que convierte el filtro en algo que se
  recalibra con datos: si el tramo frenado rinde igual o más, se baja el listón con evidencia. Hasta que haya
  muestras del tramo frenado decirlo («sin mediciones todavía»), no dar por bueno que el filtro funciona.
- **Comandos de autoservicio: slash nativo vía plugin de Hermes, no prefijo.** El usuario pidió explícitamente
  un comando con barra, y se puede sin depender de nada: Hermes ya sostiene el gateway de Discord y sus
  plugins registran comandos (`ctx.register_command`), que el adaptador publica como **slash nativos**. Lo que NO
  se puede es levantar un segundo gateway con el mismo token (Discord admite una sola sesión por bot: echaría la
  conexión de Hermes). Comandos: `/besti` (tabla del día), `/besti todo`, `/besti rick` (contratos para pegar a
  mano en el bot externo), `/besti rick todo`, `/besti profit` y `/besti <contrato>`. El handler **no recalcula
  nada**: llama a `tabla_calls.py` con flags (`--mint`, `--profit`), el mismo código del parte diario. Receta
  completa (manifest, `hermes plugins enable`, doctor, reinicio para publicar, política de sync, trampas): skill
  **`hermes-slash-commands`**.
- **Chequeo por contrato: «¿hubo profit después de la call?»** (`!profit` / `!profit <contrato>` por prefijo,
  `/besti` / `/besti <contrato>` por slash; `tabla_calls.py --profit` / `--mint <contrato>` por consola). El
  veredicto va **en llano y con la línea base del FDV del aviso**: ✅ ≥1,5x · 🟡 1,1-1,5x (marginal, contando
  comisiones) · ❌ <1,1x · ⏳ **muy reciente**. Esa última banda no es cosmética: una call de minutos de vida
  tiene **una sola muestra**, así que su «pico» es el FDV del propio aviso y marcarla ❌ sería **mentir** (pasó
  con las últimas calls: todas 1,00x). Regla: no juzgar una call hasta tener ≥2 muestras o ~20 min de serie. La
  ficha por token suma el pico y **a qué hora** llegó, los cortes de +1 h / +6 h y dónde está ahora.
- **Alimentar un tracker externo: pasarle SOLO las calls recientes.** Su métrica arranca en el **primer scan**,
  o sea en el momento en que **un humano pega el contrato**: si se le pegan calls de hace horas, su línea base
  arranca corrida y **no cuenta nada de lo que el token ya subió**. Por eso el comando de contratos devuelve por
  defecto los **últimos 30 min** con la orden de pegar **ya mismo**, y las variantes de día e histórico existen
  con la advertencia. Nuestra tabla es la medición **fiel** (mide desde el aviso); la del tracker externo es una
  copia atrasada. Complemento: registrar **cuándo pegó** el humano (y la respuesta del tracker) para poder
  cuantificar la demora en vez de discutirla.
- **Si se deja además el camino por prefijo** (`comando_discord.py` + cron cada minuto), tres reglas que no se
  saltean: **ignorar los mensajes cuyo autor sea un bot** (si no, los propios avisos del sistema disparan el
  comando y el sistema se contesta solo), **dedupe por id de mensaje** en un archivo de estado (si no, responde
  en cada pasada del cron) y los contratos van **uno por línea en texto plano** — el bloque de código no se copia
  en todos los clientes de celular.
- **Verificación del comando sin depender de que alguien escriba**: probar la lógica con la API simulada
  (contesta a un humano, ignora al bot, no repite), mandar **una prueba real** al canal y **releerla**, y dar el
  cron por bueno sólo cuando aparece el archivo de log — la línea en el crontab no prueba nada. Para un slash, el
  equivalente es que el comando figure en la lista real de la aplicación (`get_plugin_commands()` después de
  `hermes plugins enable`), y el paso final —escribirlo— sólo lo puede hacer una persona: dejar un aviso
  automático que publique si quedó registrado.

## Cómo se verifica

1. Compilar con los **dos** intérpretes (`python3` 3.11 y `/usr/bin/python3` 3.14, el del cron) y después una
   **pasada real**: el detector suelto sobre tokens que acaban de despegar siempre encuentra alguna ráfaga, y
   ahí se ven `slots_iguales`, `frescas`, `conocidas` y `compras_en_ventana`. Es el caso de prueba real — no
   inventar datos.
2. Releer el canal por API (`GET /channels/{id}/messages?limit=3`) y confirmar: el `content` con los números y
   el contrato copiable, los `fields` inline y que `embeds[].image.url` venga resuelto como
   `cdn.discordapp.com/attachments/...`. El 200 del POST no prueba nada.
3. Todo valor nuevo del aviso (título de bundle, conteo de nuevas, línea de slot) se valida **leyendo un
   mensaje publicado**, no en la lógica: el caso de la edad se descubrió así.
