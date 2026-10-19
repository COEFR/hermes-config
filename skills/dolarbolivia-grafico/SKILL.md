---
name: dolarbolivia-grafico
description: "Use when tocando DólarBolivia: sitio y gráfico USDT/BOB."
---

# DólarBolivia — sitio y gráfico USDT/BOB

Proyecto de Dylan: `dolarbolivia.site` (React + Vite, GitHub Pages sirviendo `docs/`).
Repo de trabajo: `~/.hermes/data/dolarbolivia`, remoto `COEFR/dolarbolivia`, rama `main`.

## Mapa

- **Fuente del front**: `dolarbackup/backend/src/` (ojo: ahí vive el código, no en `build/`).
- **Gráfico**: `dolarbackup/backend/src/components/PriceChart.tsx` — única gráfica del sitio, en la portada (la página `/grafico/` fue una duplicada y se borró; no recrearla).
- **Build**: `dolarbackup/build/build.sh` copia `backend/src` → `build/src`, compila con Vite y deja el resultado en `docs/`. Después hay que commitear `docs/assets` + `docs/index.html`.
- **Datos del gráfico**: `docs/api/grafico.json` ← `tools/grafico.py` ← `data/historial_p2p.csv` (+ `data/historial_diario.json`).

## Pipeline de datos (lo que hace que las velas se vean bien)

1. `tools/muestra.py` — **cada minuto**, guarda compra/venta con **4 decimales** = promedio de los 15 anuncios de Binance por lado (respaldo: la API de referencia). Es el único escritor del CSV.
2. `.github/workflows/muestreo.yml` — corre `muestra.py` y commitea el CSV. Se dispara desde el VPS con `tools/disparar_muestra.sh` en el crontab (la línea necesita `set -a; . ~/.hermes/.env; set +a` delante o no hay token).
3. `.github/workflows/tasas.yml` — corre `tools/importar_intradia.py`, `tools/importar_diario.py` y `tools/grafico.py`, y commitea `docs/api/grafico.json` + `data/historial_diario.json` + `data/historial_externo.json`.
4. `tools/importar_diario.py` — histórico diario 2024→hoy desde el CSV abierto de dolarenbolivia.com (atribuido en el pie del gráfico).
5. `tools/importar_intradia.py` — **tramos ya agregados** de la referencia (7 d de 15m, 30 d de 1h, 6 m de 4h, 1 a de 1d) a `data/historial_externo.json`; `grafico.py` los publica como `"ext"` y `PriceChart` usa el tramo **sólo si cubre el rango pedido** (`serieExt[0].time <= rango.desde + 3600`), prefiriendo `dia` para 1D. Es lo que quita las velas incompletas y los huecos de 15m/1h/4h sin inventar un dato.

**La densidad manda, y son dos densidades distintas**: (1) **muestras por vela** — con 1 muestra por vela todas las velas son planas (raya de 1 px) y la librería no rellena huecos ni detecta intervalos (tradingview/lightweight-charts #1426); (2) **velas por píxel** — con más de ~400 velas en el ancho del panel cada una mide ~1 px y se ve como una línea invisible. Ahí no se arregla con colores ni con estilo: se **engrosa la temporalidad** (con Todo se abre en **1S semanal**, ~118 velas de ~9 px). La vista con la que **abre** la portada es **1 mes / 1h** (~10 px por vela): en Todo las velas de las últimas semanas existen pero no se leen, y Dylan lo vive como «no veo las últimas velas» — explicárselo con el número de píxeles por vela, no con «es la escala». Si el usuario pide «Todo», la vista larga va en 1S y el detalle se mira en 1 mes/3 meses o con la rueda (dejar la pista de zoom escrita debajo del gráfico).

**El borde derecho se completa con lo propio**: el diario de la referencia se publica al día siguiente y los tramos `ext` llegan con 10-60 min de retraso → agregar la **vela de hoy** (1D, agrupando las muestras del día) y la **vela en curso** (15m/1h/4h) desde `historial_p2p.csv`, o el extremo derecho queda vacío y parece que la serie terminó. Los huecos **internos** siguen sin inventarse: se completan con los tramos `ext` de la referencia; el 5m propio se llena solo con el tiempo.

## Trampas

- **El bot commitea cada minuto.** Al empujar desde el VPS, `git push` rebota. Receta: commitear solo código/build (nunca `data/` ni `docs/api/grafico.json`), luego `git branch -f tmp <sha>` → `git fetch` → `git reset --hard FETCH_HEAD` → `git cherry-pick tmp` → en conflicto de datos `git checkout --ours <archivo> && git add` → `cherry-pick --continue` → `git push`. Restaurar la URL del remoto sin token al final.
- **`GITHUB_TOKEN` del .env está vencido (401)**; usar `GITHUB_TOKEN_DOLAR`.
- **GitHub Pages tarda ~2 min** en servir el bundle nuevo y manda `cache-control: max-age=600` (10 min de caché en el navegador). Antes de decir «está publicado»: bajar el HTML del sitio, sacar el `index-*.js` que referencia, bajar **ese** archivo y buscar dentro un símbolo del arreglo (`grep setStretchFactor`); eso prueba que el cambio está en el aire y no sólo en el repo. Para que Dylan lo compruebe solo, el componente imprime la **versión** en el pie (nombre del bundle, leído de `document.querySelector('script[type="module"][src]')`) y se le pasa el link con `?v=<timestamp>`; si ve otro código, es caché → Ctrl+Shift+R. Cuando dice «creo que no lo publicaste», la respuesta es esa prueba + el link, no volver a compilar.
- **`timeVisible` según la serie que se dibuja, no según el botón**: con velas diarias o semanales el eje debe mostrar **solo fechas**; si muestra horas, una vela de 00:00 UTC se lee «20:00» en Bolivia y el usuario reporta «la hora no está correcta». Vale también cuando 1h/4h caen al diario (`nota` activa). Intradía sí lleva hora, corrida por `getTimezoneOffset()` del navegador (una sola vez, nunca dos).
- **`rightOffset: 1` en 1D/1S** (4 en intradía): si la última vela queda lejos del borde, la última **etiqueta** del eje es de meses antes y el usuario concluye «la última vela es del 20 de julio». Además, cuando se agrega una temporalidad nueva, revisar el orden de ramas del memo: la rama genérica de «caer al diario con nota» se come el intervalo nuevo si no se la excluye explícitamente (`intervalo !== 1440 && intervalo !== 10080`).
- **«Velas invisibles» o «la serie termina en julio»: revisar el RANGO VISIBLE antes de culpar a la escala.** La librería arranca con `barSpacing: 6` y no lo baja al hacer `fitContent()`: con cientos de velas en un panel de ~950 px no entran, la vista se corta y **los últimos meses quedan fuera de pantalla** (costado derecho vacío y última etiqueta de meses atrás). Se arregla calculando `barSpacing = ancho del panel / cantidad de velas` y fijando `setVisibleLogicalRange({from: 0, to: n-1})` (receta en `references/lightweight-charts-ajustes.md`). Confirmarlo con el probe: `rangoVisible` tiene que ser `0..n-1`. Recién cuando el rango es correcto y las velas siguen chatas aplica la escala: en Todo el eje va de ~8 a ~20 Bs por el pico de 2025, así que 11,8–11,9 ocupa 1-3 px; decirlo con esos números y ofrecer 1 mes/3 meses o zoom, en vez de seguir tocando el componente. Igual que TradingView en «All».
- **Paneles secundarios (brecha, estocástico)**: `setHeight()` **no se respeta** (ni antes ni después del layout: con dos paneles la brecha queda en una franja de ~10 px aunque se pida el 16 % del alto). Lo que sí funciona es **`chart.panes()[i].setStretchFactor(n)`**: reparto proporcional y estable con dos paneles a la vez — precio 5 · brecha 1,5 · estocástico 2. Aplicarlo después de crear los paneles y de nuevo dentro del ajuste (rAF + ~150 ms). Verificado en vivo con las cinco capas encendidas: brecha con eje propio 5-25 % y estocástico debajo, sin franjas.
- **Noticias de la portada**: la sección tira de `api.rss2json.com`, que a veces responde **422** y deja un error de consola (`No se pudo obtener el feed de noticias`). No es del gráfico: al hacer QA del gráfico, ignorar ese error o revisarlo aparte, no perseguirlo como si rompiera las velas.
- **El gráfico lee su estado de la URL**: `?rango=&intervalo=&capa=` (rango: hoy|ayer|3d|7d|1m|3m|6m|1a|todo; intervalo: 5|15|60|240|1440|10080; capa: oficial,banda,medias,brecha,estocastico). Sirve para probar y para compartir.
- **Tema**: el gráfico va oscuro, estilo del sitio (Dylan lo eligió así), no el claro de la referencia.
- **«Hay un menú repetido»**: no lo está. Son dos controles distintos —rango (Hoy…Todo) y temporalidad (5m…1D y 1S)—, igual que en TradingView; el DOM servido tiene un botón de cada uno. Comprobarlo con `--dump-dom` + `grep -c` antes de tocar el componente, y contestar con ese conteo (si él sigue viéndolo, es caché: Ctrl+Shift+R). Nunca agregar controles nuevos que dupliquen rango o temporalidad: Dylan ya rechazó una página `/grafico/` duplicada.

## Referencia (dolarenbolivia.com) — cómo lo hace

- Endpoints `https://dolarenbolivia.com/grafico/parallel?range=7d&interval=1h` y `/grafico/official?range=7d` devuelven las velas ya agregadas, pero **403** sin cabeceras de navegador: mandar `User-Agent` de Chrome y `Referer: https://dolarenbolivia.com/`.
- Sus velas tienen 4 decimales (11.8945) porque promedian anuncios de Binance y Bybit; muestrean cada 60 s desde 2024. A 7d/15m: 649 velas, 0 huecos, rango mediano 0,0025.
- **Binance no sirve para histórico**: no existe par USDT/BOB al contado, la API de P2P solo da anuncios actuales y la oficial de C2C solo las órdenes propias.

## Verificar antes de responder

Dos comprobaciones, siempre las dos, antes de decir «arreglado»:

1. **Qué se está dibujando de verdad**: `scripts/probe_grafico.py` (CDP sobre Chromium headless) lee `window.__grafico` —`{intervalo, rango, velas, primera, ultima, serie, serieUltima, rangoVisible}` que el componente deja para diagnóstico— y dice cuántas velas y desde/hasta qué fecha se plotearon. Contesta en segundos dudas que inspiran capturas («¿la última vela es de julio?») sin adivinar. **`rangoVisible` es el dato decisivo**: si `.to` supera la cantidad de velas, la vista se fue más allá del final y el gráfico se ve vacío aunque los datos estén bien (bug de `barSpacing`). Dejar también `window.__chart = chart` en el componente para poder leer `getVisibleLogicalRange()` a mano después de unos segundos: el valor que se lee en el mismo instante de `setData` todavía no se aplicó y engaña. Si la clave no aparece, el componente no llegó a dibujar (fetch lento): esperar y reintentar.
2. **Cómo se ve**: captura headless con `--force-device-scale-factor=2` (el 1× no deja leer los píxeles finos) y recortar el bloque del gráfico con PIL detectando las filas del color del panel (`#131722`). Dylan pide la foto: mostrarla siempre, y si el diagnóstico dice que el problema es de escala/densidad, explicarlo con números en vez de prometer otra iteración.

3. **Barrido de rangos, no una sola vista**: `scripts/qa_rangos.py` recorre 8 combinaciones rango×intervalo contra el sitio en vivo y exige `visible.from ≈ 0` y `visible.to ≈ n-1` en cada una (si no, la serie está cortada). **Esperar ~2,5 s después de navegar antes de leer**: leer apenas carga devuelve el rango por defecto (~160 velas pegadas al final) y hace creer que hay un bug que no existe — con esa espera las 8 dieron `0..n-1`. Sumar una captura a 390 px de ancho: los controles se acomodan en filas y las velas tienen que seguir leyéndose.

Detalle de opciones del widget, agregación semanal y trampas de la librería: `references/lightweight-charts-ajustes.md`.

## Entrega

Español, emojis para ordenar y cierre con **«Conclusión»** que resuma la causa y el arreglo. Mostrar siempre la captura del sitio en vivo y separar lo verificado (con el número medido: 118 velas → rango `0..117`) de lo pendiente. Si dijo «sigo viendo lo mismo» dos veces, dejar de proponer ajustes a ciegas y medir el rango visible / el ancho por vela antes de tocar el componente.
