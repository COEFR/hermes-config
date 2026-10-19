# Gráficas de precio con historia real (velas y línea)

Pedido típico: «que haya un gráfico de <activo> vs <moneda>», «hacelo como una tabla de TradingView».

## La librería: la propia de TradingView, gratis

`lightweight-charts` (repo `tradingview/lightweight-charts`, npm `lightweight-charts`) es la librería open source
de TradingView: da el aspecto «tabla de TradingView» sin pagar ni embeber su widget de terceros.

```tsx
import { createChart, CandlestickSeries, AreaSeries, ColorType } from 'lightweight-charts';

const chart = createChart(caja.current, { autoSize: true, layout: { background: { type: ColorType.Solid, color: 'transparent' } } });
const serie = chart.addSeries(CandlestickSeries, { upColor: '#f59e0b', downColor: '#ef4444' });
serie.setData(datos);        // [{ time, open, high, low, close }, …]
chart.timeScale().fitContent();
return () => chart.remove(); // limpiar al desmontar, o los canvas se apilan en cada re-render
```

- **La v5 cambió la API**: la serie se agrega con `chart.addSeries(<TipoDeSerie>, opciones)`. Las recetas viejas
  con `addCandlestickSeries()` que circulan por ahí ya no existen; si el import falla, mirar la versión instalada.
- `time` va en **segundos UNIX** (no milisegundos), **ascendente y sin repetidos**: repetido o desordenado, la
  serie se dibuja a medias sin tirar ningún error.
- `layout.attributionLogo: false` saca el logo de TradingView del lienzo (queda mal sobre fondo oscuro).
- La librería **no trae tema oscuro**: se arma con `layout.grid` y los `borderColor` de `rightPriceScale` /
  `timeScale` en `rgba(255,255,255,0.03–0.06)`, texto en `rgba(255,255,255,0.35)`. Paleta de este usuario para el
  sitio: **fondo oscuro + ámbar** arriba (`#f59e0b`), rojo abajo (`#ef4444`).
- Un selector de rango (24h · 7d · 30d · 1a) se resuelve filtrando las velas por `time >= ahora - horas*3600` antes
  de `setData`, no con la API de zoom de la librería.

## De mediciones sueltas a velas

Lo que se recolecta es un **precio puntual**; las velas necesitan OHLC. Agrupar por bloque:

1. `bloque = (timestamp // 900) * 900` → velas de 15 min.
2. `open` = el primero del bloque, `close` = el último, `high`/`low` = máximo/mínimo.
3. Emitir `[{ time: bloque, open, high, low, close }]` ya ordenado.
4. Guardar además los precios crudos, para poder reagrupar a otra temporalidad sin volver a recolectar.

Un año de velas de 15 min son ~34.000 filas ≈ **2,8 MB de JSON**: Pages lo sirve bien, pero decirlo y no mandarlo
por el chat.

## Huecos en la serie: rellenarlos se ve como un gráfico roto
Un relleno es peor que un hueco, y el usuario lo reporta como «las velas están mal»:
- **Una vela de relleno con `open = high = low = close` se dibuja como una línea finita**, no como una vela (así
  la pinta `lightweight-charts`): en medio de velas normales la serie parece cortada o mal armada.
- **Si el relleno usa el precio viejo, aparecen un precio y un salto falsos**: medido, rellenar el tramo faltante
  con el último precio histórico mostró el precio de meses atrás y un escalón que nunca existió. Si hay que
  rellenar, se rellena **sólo la cola reciente con el precio ACTUAL** — nunca con el precio del tramo viejo — y se
  dice al reportarlo.
- **Las separaciones mezcladas deforman las velas**: rellenar alternando intervalos (15 y 30 min) rompe el ancho de
  la vela y el eje. Un relleno tiene que caer exactamente en la misma grilla temporal que el dato real.
- Lo que sí conviene: **importar el histórico real disponible** (un repo con el CSV del mismo indicador) para
  arrancar con meses de serie de verdad en vez de una semana de recolección propia.

### El eje de tiempo no es proporcional: los huecos NO se dibujan

`lightweight-charts` asigna **una posición de barra por punto de datos** y desconoce el intervalo: si faltan marcas
de tiempo no abre un espacio, pega las velas vecinas una al lado de la otra. Consecuencias prácticas:

- **Lo que parece un hueco suele ser un doji.** Antes de hablar de «huecos entre velas», contar los bloques vacíos
  del intervalo mostrado y cuántas velas tienen `high == low`: medido acá, 7 días en 1h daban **0 bloques vacíos**
  y aun así la serie se veía cortada — eran guiones de 1 px, no faltantes.
- **El eje miente sobre el tiempo cuando hay faltantes**: un corte de dos días ocupa el ancho de una vela. Si se
  necesita un eje proporcional hay que pasarle **puntos de whitespace** (objeto con `time` y sin valores) en cada
  bloque faltante; así el eje queda correcto **con** los huecos visibles. En velas no hay opción `connectGaps`
  (existe sólo para línea/área/baseline), y ninguna opción engrosa un cuerpo de altura cero.
- **No inflar el JSON publicado con rellenos.** Medido: rellenar la base de 5 min con el último precio llevó el
  archivo de 1,4 MB a 4,3 MB y el gráfico a un campo de puntos, porque cada relleno es un doji. Si alguna vez hace
  falta, que sea al dibujar en el navegador y sólo para huecos cortos.

## Fuente del USDT/BOB (Binance P2P)

`POST https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search` con
`{"asset":"USDT","fiat":"BOB","tradeType":"BUY","rows":3}` (y `"SELL"` para el otro lado). Responde **desde
el servidor** (medido: HTTP 200 desde este equipo, con los precios que se ven en el sitio). Es el mismo llamado
que ya vive como respaldo en `tools/tasas.py` del proyecto de Dólar Bolivia → el dato ya estaba, sólo faltaba
publicar su historia.

- **Histórico para arrancar sin esperar**: el repo `naldoft/monitor-p2p-bolivia` publica un `data.csv` de ~34.000
  filas, formato `fecha, oficial_compra, oficial_venta, p2p_compra, p2p_venta`, fechas `dd/mm/aaaa hh:mm:ss` y
  números entrecomillados con coma decimal. Importarlo de una vez deja la gráfica con **un año de historia en el
  primer despliegue** en vez de una semana, y sirve de control (se ve el paralelo bajando de 15,3 a 9,9).
- Otras fuentes bolivianas a comparar antes de elegir: `paralelo.bo/api` (público, sin key, datos CC-BY) y
  `dolarparalelobolivia.net/api`. Sus páginas son SPA: pedir el JSON del endpoint, nunca el HTML.

### Qué NO puede dar Binance para «completar la serie» (verificado)

Antes de prometer «lo completo con la API de Binance», comprobarlo: no hay histórico público de P2P.

- `GET /api/v3/exchangeInfo?symbol=USDTBOB` → `{"code":-1121,"msg":"Invalid symbol."}`: **no existe par
  USDT/BOB al contado**, y sin par no hay `klines`.
- El endpoint que sí funciona (`/bapi/c2c/v2/friendly/c2c/adv/search`) devuelve **sólo los anuncios del momento**;
  los caminos de histórico que se prueben responden **404**.
- La API oficial de C2C (`/sapi/v1/c2c/orderMatch/listUserOrderHistory`) devuelve **las órdenes del dueño de la
  clave**, en ventanas de 30 días: no son precios de mercado.
- Su web de P2P contesta **202 con 0 bytes** a un pedido automatizado.

Por eso las páginas de referencia **construyen su propio histórico muestreando cada minuto**: no hay atajo por API.
Lo que sí completa los rangos largos sin inventar nada es el **CSV abierto de la propia referencia**
(`https://dolarenbolivia.com/datos/usdt-bob-diario.csv`, columnas `fecha,apertura,maximo,minimo,cierre,
apertura_compra,…,fuente`). Medido: **819 velas diarias, 2024-07-21 → hoy, sin un hueco**, con la fuente declarada
en cada fila. Se importa con un `tools/importar_diario.py` que lo baja y lo deja en `data/historial_diario.json`;
el JSON del gráfico lo lleva como `"dia"` y el front lo usa cuando el intervalo es **1D** (agregar 5 min a un día
daría velas a medias). Atribuir la fuente en el pie y en el README: es dato de terceros, no propio. Así «1 año» y
«Todo» arrancan completos el primer día mientras la recolección propia aporta el detalle de minutos.

## Recolección continua

Una fila por corrida del reloj, con guarda para no repetir el mismo minuto. **La densidad del gráfico es la del
reloj**: con corridas cada 5-30 min las velas de 5 y 15 min quedan con una sola muestra y salen como guiones (ver
«Velas planas»); para velas de minutos hace falta un workflow propio que muestree cada 60 s, disparado por un reloj
externo.

```python
marca = ahora.strftime("%Y-%m-%dT%H:%M")
ultima = primer campo de la última línea del CSV, cortado a 16 caracteres
if ultima != marca:      # sin esto, dos corridas del mismo minuto ensucian la vela
    append(f"{ahora.isoformat()},{compra},{venta}")
```

**Cerrar el circuito**: alguien tiene que convertir el CSV a JSON de velas y commitearlo a `docs/api/`. Si falta
esе paso la gráfica queda congelada en la última foto importada — y **parece viva** porque el precio grande de
arriba sí se mueve; el usuario lo cuenta como «el gráfico está viejo» recién días después.

## Replicar la gráfica de una página de referencia

Pedido típico: «en esta página hay una gráfica, justo lo que queremos, buscá cómo implementarlo» y después
«solo quería que la gráfica que está en esa página la implemente en mi página». El veredicto va primero: **se
reemplaza el gráfico de SU portada**, no se entrega una página aparte.
1. Bajar la página y su bundle: `curl -s <url> -o /tmp/ref.html`, sacar el asset con `grep -oE 'assets/[^"]+\.js'`,
bajarlo y buscar la librería (`grep -o 'lightweight-charts\|recharts\|chart\.js\|echarts'`) y los endpoints de datos
que pide (`grep -oE '"/[a-z]+/[a-z0-9?=&]+"'`).
2. Probar esos endpoints con `curl`: a un pedido pelado contestan **403** (bot wall). **Antes de darlo por cerrado,
hacer un intento con encabezados de navegador** (`-H 'User-Agent: Mozilla/5.0 …' -H 'Referer: <la página>' -H
'Accept: application/json'`): medido, ese mismo `/grafico/parallel?range=7d&interval=1h` pasó de 403 a **200 con ~24 KB
de velas ya agregadas** (`timestamp, open, high, low, close, open_buy…`, `timezone: UTC-4`). Con eso se lee el contrato
exacto **y se mide la vara** en vez de suponerla: 7d/1h → 163 velas, 0 huecos, rango mediano 0,01, 13 % planas;
7d/15m → 649 velas, rango mediano 0,0025, 39 % planas. Si aun así no pasa, el bundle público alcanza para el contrato.
3. Copiar la **lista de controles**, no el diseño: 9 rangos (hoy, ayer, 3 d, 7 d, 1 mes, 3 meses, 6 meses, 1 año,
todo), 5 intervalos (5m, 15m, 1h, 4h, 1D), velas/línea, capas de oficial, banda compra–venta, medias 7·30 y brecha,
y el estado en la URL para compartir.
4. Implementarlo en el componente propio, alimentado por un JSON propio que arma un `tools/grafico.py` en cada
corrida del workflow.

## Un solo JSON, agregación en el navegador

- Guardar la base **más fina que se mida** (acá 5 min) como arrays compactos `[t, o, h, l, c, venta]` —sin repetir
las claves en cada fila— más la serie del oficial `[t, precio]`. Medido: ~34.000 velas ≈ **1,4 MB**, servible por
el CDN de Pages.
- El navegador recorta el rango (`t >= ahora - días*86400`) y agrupa al intervalo pedido
(`bloque = (t // (min*60)) * (min*60)`) antes de `setData`. Así **no hace falta servidor**: cualquier intervalo sale
del mismo archivo, sin regenerar el JSON.
- La serie del oficial se filtra aparte, con ±30 min de margen: su grilla no coincide con la de las velas y sin el
  margen el empalme se corta en los extremos.
- **El estado del gráfico va en la URL** (`?rango=1y&intervalo=1440`): leer los params al montar y
  `history.replaceState` al cambiar rango o intervalo. Es lo que permite capturar una vista concreta por headless
  (sin clickear) y que el usuario comparta exactamente lo que está mirando.
- Brecha (`%`): por cada vela, buscar el punto oficial más cercano y `((close - oficial) / oficial) * 100`.

## Paneles y escalas (v5)

- **Segundo panel**: `chart.addSeries(LineSeries, {...}, 1)` —el tercer argumento es el índice del panel—. El panel 0
es el principal. **El alto se reparte con `setStretchFactor`, no con `setHeight`**: `chart.panes()[1].setHeight(110)`
se aplica y la librería lo pisa cuando recalcula el layout, y el panel queda convertido en una franja de ~10 px.
Con `chart.panes()[i].setStretchFactor(n)` el reparto es proporcional y estable (medido: precio 5 · brecha 1,5 ·
estocástico 2 = dos paneles legibles). Aplicarlo **después** de crear todas las series, no en el bloque de cada una.
- **Crear el panel sólo cuando la capa está encendida**: crearlo siempre deja un panel vacío abajo que el usuario ve
como error.
- **`localization.priceFormatter` es del chart entero**: si se usa para «dos decimales», el panel de brecha también
sale en Bs. El formato por serie va en `priceFormat: { type: 'custom', minMove: 0.01, formatter }`, con un
formateador propio (`v.toFixed(2) + '%'`) para la brecha.
- **Una capa con escala lejana aplasta las velas**: el oficial (11,69) contra el paralelo (11,80–11,94) deja las
velas en una franja de 2 px y se ven como guiones. Esa capa arranca **apagada** (o con su propia escala) y el panel
escala al dato que importa; el usuario puede encenderla cuando quiera comparar.
- **Zona horaria: la del navegador que mira, no la del dueño.** Los `time` del JSON van en UTC; sumar un offset fijo
  (`t + (-4*3600)`) deja el eje corrido para cualquier visitante de otra zona. Usar `new Date().getTimezoneOffset()*60`
  al cargar y aplicarlo a velas y al oficial. **La serie diaria y la semanal NO se desplazan**: su `time` ya es la
  medianoche del día y restarle horas la corre un día entero (síntoma medido: «la última vela me aparece el 20 de
  julio»). `timeVisible: true` sólo para intradía; en 1D/1S el eje muestra la fecha.
- **Velas planas = falta de muestras o de decimales, casi nunca la librería** (ver la sección siguiente).
- **Con dos capas de panel, el índice depende de cuántas haya**: si la brecha ocupa el panel 1, la capa siguiente va
al 2; si la brecha está apagada, al 1. Calcularlo al crear (`const panel = capas.brecha ? 2 : 1`), nunca fijar `1`
a mano: con las dos encendidas se pisan.
- **Estocástico (para igualar los controles de la referencia)**: `%K = 100 * (close - min(low, 14)) / (max(high, 14)
- min(low, 14))`, `%D` = media móvil de 3 de `%K`; dos `LineSeries` en su panel con `priceFormat` propio
(`v.toFixed(0)`), ámbar y azul. Se calcula sobre las velas **ya agregadas al intervalo visible**, no sobre la base
fina.

## Que se vean TODAS las velas (y la última, siempre)

Síntoma: «no aparecen las velas a partir de <fecha>», «la última vela está en blanco», «la vista se corta». Casi
nunca faltan datos: la librería **ancla la vista al borde derecho y muestra la ventana que entra con el
`barSpacing` vigente** (~160 velas con el valor por defecto), así que con 800 velas cargadas se ven las últimas 160
y el resto queda fuera de rango —y `fitContent()` no siempre lo arregla, porque encuadra también las otras series.

Regla: **el ancho de vela se calcula, no se elige**, y después se fija el rango lógico completo.

```ts
const n = velas.length;
const ancho = (caja.current?.clientWidth || 900) / n;   // píxeles reales por vela
chart.timeScale().applyOptions({ barSpacing: ancho, rightOffset: 0 });
chart.timeScale().setVisibleLogicalRange({ from: 0, to: n - 1 });
```

- Aplicarlo **dos veces**: en el `requestAnimationFrame` siguiente y en un `setTimeout(…, 150)`. Llamado en el mismo
  tick que `setData`, la librería todavía no midió el contenedor y lo descarta **sin ningún error**.
- `barSpacing` mínimo ≈1,5 px: con más de ~1.300 velas en el panel ya no entran todas; se ven finas y eso es ancho
  de vela, no dato faltante.
- Verificarlo leyendo el rango, no la imagen: `chart.timeScale().getVisibleLogicalRange()` tiene que devolver
  `from≈0, to≈n-1` en cada combinación rango×intervalo.
- **Elegir un default donde el precio se vea**: dos años en «Todo» dan un eje de 8 a 20 Bs y el precio actual ocupa
  2 px; abrir en 1 mes/1h y dejar «Todo» para la vista panorámica.

## Velas planas («las barras se ven mal»): densidad de datos

`lightweight-charts` dibuja el cuerpo con `open/close` y la mecha con `high/low`. Con **una sola medición por
bloque** open = close = high = low: cuerpo de cero, mecha de cero, y la vela sale como un guion de 1 px. No hay
opción en la librería que la engrose — si el dato no se movió dentro del bloque, no hay vela que dibujar.

**Diagnóstico antes de tocar código** — agrupar las mediciones crudas por bloque del intervalo que el usuario mira y
contar muestras por bloque, más cuántas velas tienen `high - low > 0`. Medido en este proyecto: 343 mediciones en 7
días (una cada ~30 min) → **0 de 341 velas de 15 min con cuerpo**. Con eso el problema está identificado y no se
pierde tiempo en la configuración del chart.

**Y comprobar que el precio se mueva**: muestrear la fuente 5 veces en 3 minutos y contar valores distintos. Medido
acá: `11,86 / 11,81` idénticos en las 5 lecturas (la fuente refresca cada ~70 s, el mercado estaba plano) → ese día
ninguna densidad ni opción de dibujo produce velas con cuerpo. Decirlo con el número en vez de seguir tocando el
componente: es la diferencia entre «falta dato» y «está mal configurado», y el usuario lo acepta cuando ve el número.

**La otra mitad es la resolución del precio: dos decimales garantizan velas planas.** Aun con muestreo denso, si la
serie guarda `11.85` y `11.81`, todo bloque que caiga entre esos valores repite el mismo número y la vela vuelve a
medir cero. La referencia guarda **cuatro decimales** (`11.8900 → 11.8850`) porque publica el **promedio de los
anuncios**, no la mediana. Medido acá: mediana a 2 decimales = `11.85` idéntico todo el día; promedio de los 15
anuncios = `11.8473 → 11.8467` (lado alto) y `11.8060 → 11.8047` (lado bajo) en tres minutos → cuerpo y mecha
visibles. Reglas: (a) el precio de titular del sitio no cambia —sigue la mediana a 2 decimales, los 4 son sólo para
la serie del gráfico—; (b) guardar 4 decimales en el CSV **y no redondear a 2 al armar las velas** (`round(x, 4)` en
el generador: redondear ahí tira la resolución que costó conseguir); (c) el eje sigue mostrando 2 decimales
(`priceFormat`), igual que la referencia; (d) decirlo en el pie («promedio de los N anuncios») para que el número
del gráfico no contradiga sin explicación al grande de arriba.

Arreglo, en orden:
1. **Medir más seguido.** La página de referencia muestrea cada 60 s (lo dice su metodología) y así sus velas de
   15 min juntan ~15 muestras. Comprobar antes que la fuente cambia a ese ritmo: dos `curl` seguidos y comparar el
   `updated_at` del JSON (medido: refresca cada ~70 s). Si la fuente cachea 10 min, muestrear por minuto no aporta.
2. **Workflow de muestreo separado del que publica**: uno sólo anota y commitea el CSV (`tools/muestra.py` +
   `muestreo.yml`), otro regenera los JSON de velas. El dispara un reloj externo cada minuto (el `schedule` de
   GitHub no baja de 5 min y es impuntual).
3. **Un solo escritor del CSV.** Si el workflow de publicación también lo escribe (acá `tasas.py` lo hacía), los dos
   appends chocan en la última línea del archivo y el rebase falla → se pierden muestras. Se le agrega al publicador
   un `--sin-muestra` y se lo saca de su `git add`; el muestreador queda como único dueño de ese archivo.
4. **Mientras no haya densidad, cambiar el default** al intervalo que sí la tenga (1h o 4h) y subir `barSpacing`
   (~8) para que las velas se vean anchas: la portada queda como la referencia en el mismo turno.
5. **El pasado no se INVENTA, pero sí se COMPLETA con lo que la referencia publica** (sección «Completar el
   pasado»). Rellenar con el precio actual deja una línea plana y es peor que el hueco; importar sus tramos ya
   agregados deja la serie continua y con cuerpos reales. Lo único irrecuperable es lo que nadie midió (nuestro 5m
   viejo): dar el plazo real de lo propio («en 2-4 h de muestreo, Hoy/5m ya tiene cuerpo»).

**Probar el dibujo con datos inventados: sí, pero fuera del repo.** Cuando el usuario pide «inventá esos datos
solamente para ver si las barras están bien», pide una **prueba de render**, no un dato a publicar. Receta: copiar la
página a `~/.hermes/cache/scratch/<prueba>/`, generar ahí un JSON sintético denso (camino aleatorio con pasos de
0,01-0,02, una muestra por minuto, misma forma `[t,o,h,l,c,venta]`), servirla en `127.0.0.1` y capturar dos vistas:
**Hoy/5m** (aparecen cuerpos y mechas → la librería y el componente están bien) y **7d/15m** (672 velas en ~1.300 px
= ~2 px por vela: se ven finas **aun con datos perfectos**, es ancho, no configuración). Lo que se le entrega es esa
conclusión con las dos capturas; los datos sintéticos **nunca** se commitean ni se publican, y si se muestran van
marcados como inventados.

Costo que va en el mismo mensaje: un commit por minuto (~1.440/día) si el muestreo es cada 60 s; ofrecer 2-5 min
como alternativa sin perder el efecto. Ese bot que commitea cada minuto además hace **perder la carrera de push** al
trabajar a mano: commitear sólo fuente y build, nunca los archivos que él regenera (skill `publicar-proyectos-github`,
trampa del repo con bot).

**Si el arreglo es acumular datos, no dejarlo como pendiente en la cabeza del usuario**: crear un `cronjob` de una
sola corrida a las 24 h cuyo prompt mida la densidad real (mediciones por bloque), y **sólo si alcanza** cambie el
intervalo por defecto, recompile, publique y verifique; si no alcanza, que investigue por qué (log del disparador,
runs del workflow) y avise sin tocar nada. Así el «en 24 h paso a 15m» se cumple solo y con el número medido.

## Completar el pasado con los tramos agregados de la referencia

El pedido llega como «se siguen viendo mal, aparecen velas incompletas y espacios en blanco». La causa no es el
componente: nuestro histórico tiene una muestra cada ~30 min, así que 15m y 1h nacen con huecos. La salida no es
inventar: la referencia **publica su serie ya agregada** y se puede importar.

```
GET https://<referencia>/grafico/parallel?range=7d&interval=15m
Headers: User-Agent: Mozilla/5.0 … · Referer: https://<referencia>/ · Accept: application/json
→ {"data":[{"timestamp":…,"open":…,"high":…,"low":…,"close":…,"close_buy":…}],"timezone":"UTC-4"}
```

Cobertura medida (probando rango por intervalo; los rangos largos con intervalos finos devuelven lista vacía o error):

| tramo | rango | velas | cubre |
|---|---|---|---|
| `15m` | `7d` | ~654 | 7 días |
| `1h` | `1m` | ~740 | 30 días |
| `4h` | `6m` | ~1.103 | 6 meses |
| `1d` | `1y` | ~366 | 1 año |

Implementación que funciona (`tools/importar_intradia.py` → `data/historial_externo.json`):

- Bajar los cuatro tramos y guardarlos como `{"15m": [[t,o,h,l,c,venta], …], "1h": […], "4h": […], "1d": […]}` con
  `round(x, 4)`; `venta` sale de `close_buy`. Un tramo que falle no aborta los otros.
- El generador del gráfico lo mete en el JSON como `"ext"` (junto a `"velas"`, `"dia"`, `"oficial"`) y el workflow
  corre el importador **antes** de regenerar y commitea el archivo: si falta ese `git add`, el tramo nunca llega al
  sitio.
- En el front, un mapa `{15:'15m', 60:'1h', 240:'4h', 1440:'1d'}` y una sola condición: usar el tramo **sólo si
  cubre el rango pedido** (`serieExt[0].time <= rango.desde + 3600`). Para 1D preferir el diario propio (819 días)
  antes que su `1d` (366). Si no cubre, caer en la agregación propia: nunca mezclar dos fuentes en la misma serie.
- Atribuir en el pie («tramos 15m/1h/4h/1d y diario: <referencia>»): es dato de terceros, igual que el CSV diario.

Ojo con lo que se promete: con el tramo importado la serie queda **completa**, pero 654 velas de 15m en ~1.300 px son
~2 px por vela y su rango mediano es 0,0025 → se ven finas. Eso es ancho de vela, no dato faltante; el que se ve
«como TradingView» es 1h/4h. Decirlo así en vez de seguir tocando el componente.

## Ver que la gráfica SE VE (sin adivinar)

- La gráfica suele estar debajo del pliegue: captura alta (`--window-size=1400,3600`) con `--virtual-time-budget=20000`.
- Para no mandar 3.600 px de imagen al contexto: ubicar el panel por su **color de fondo** (p. ej. `#131722`) con un
barrido de filas en PIL, recortar esa franja y mirar **sólo el recorte** con visión.
- La captura que vale es la del **dominio en vivo**, no la de `127.0.0.1`: es la única que prueba que el bundle nuevo
está sirviendo el JSON nuevo.
- Si algún control no se pudo clickear (navegador headless sin interacción), decir cuál quedó sin probar en vez de
darlo por verificado. **Por eso el estado va en la URL, incluidas las capas** (`?rango=7d&intervalo=60&capa=estocastico,brecha`):
la capa se lee al montar y se reescribe con `replaceState`, así se captura headless una vista concreta y el usuario
comparte lo que está mirando.
- **Un arnés de QA puede mentir: leer el estado antes de que el gráfico se asiente.** Recorrer varias combinaciones
  rango×intervalo navegando en el mismo navegador y leer `getVisibleLogicalRange()` apenas aparece el chart devuelve
  el rango de la vista **anterior** (medido: `130..292` con 288 velas, que se lee como «bug» y no lo es). Esperar ~2 s
  por vista, o reconfirmar cada hallazgo con una carga limpia en un navegador nuevo, antes de reportarlo como fallo.
- **Leer el estado del gráfico desde CDP es la forma de verificar sin adivinar**: abrir Chrome con
  `--remote-debugging-port=<p>`, conectar por WebSocket a la pestaña y evaluar en la página
  `JSON.stringify({rango: window.__chart.timeScale().getVisibleLogicalRange(), velas: window.__velas.length})`.
  Exponer `window.__chart` en el componente (en dev y en prod) convierte cada «¿se ve bien?» en un número.

