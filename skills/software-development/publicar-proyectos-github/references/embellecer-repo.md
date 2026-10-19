# Recetas: capturas reales, banner, README, ficha del repo y limpieza

## 1. Capturas reales del sitio (Chromium de Playwright, headless)

```bash
CH=$(find ~/.cache/ms-playwright -maxdepth 3 -type f -name chrome | head -1)
"$CH" --headless --disable-gpu --no-sandbox --hide-scrollbars \
  --virtual-time-budget=12000 --window-size=430,1600 \
  --screenshot=/tmp/movil.png "https://<dominio>/"
```

- `--virtual-time-budget` es **obligatorio** en sitios que se dibujan con JavaScript: sin él la captura dispara
  antes de que corra React y sale casi en blanco.
- **El peso del PNG es el indicador**: un 430x1600 vacío pesa 5-8 KB; con contenido, cientos de KB o MB. Igual hay
  que **mirarla** (`vision_analyze`) antes de meterla en el README: el peso dice que hay algo, no que se vea bien.
- Dos tomas rinden bien: celular (430 de ancho, es el caso de uso) y escritorio (~1280) con la ventana recortada a
  unos 1000-1100 px de alto.
- Sacarlas del **sitio en vivo**, no del build local: así el README muestra lo que el usuario ve hoy.

## 2. Comprimir para el README

- La vía confiable en este equipo es un **entorno virtual de Python + Pillow** (sin instalar nada global):
  `python3 -m venv /tmp/venvimg && /tmp/venvimg/bin/pip -q install Pillow`.
- Objetivo: ancho ~440 px, `JPEG quality=82, optimize=True, progressive=True` → de 2,3 MB a **64 KB**.
- **Reglas que costaron una ronda**: nunca escribir la salida sobre el mismo archivo de entrada (los conversores la
  rechazan o la truncan) y **nunca** borrar los PNG originales antes de confirmar que la salida existe — una
  limpieza con comodín se llevó las capturas y hubo que rehacerlas. Convertir a un nombre nuevo, verificar, y recién
  después limpiar.

## 3. Banner SVG (GitHub lo sanitiza)

- Permitido: `<defs>` con gradientes/patrones, `<rect>`, `<path>`, `<circle>`, `<text>`, `<g transform>`. **No**
  `<script>`, `<foreignObject>`, eventos ni `href` externos (GitHub los elimina y el banner queda roto).
- 1280x320 rinde bien como cabecera con `width="100%"`. Marca que el usuario ya aprobó: fondo `#050505`, acento
  ámbar `#f59e0b`, nombre partido (blanco + ámbar), bandera en barras, píldora «EN VIVO» con punto verde y un
  sparkline ámbar.
- **Verificarlo renderizado**, no sólo que el archivo dé 200: embeberlo en un HTML local, sacarle `--screenshot` y
  mirarlo con `vision_analyze`. Es lo primero que se ve del repo.
- **Un solo estilo, el aprobado** (el de arriba): no diseñar un banner distinto para cada repo. Uno tipo «romano»
  (inscripción en serif, columnas, greca, caduceo) lo rechazó y hubo que sacar el archivo y sus referencias del
  README. Si se quiere variar el registro, **proponerlo antes** de dibujarlo, y dejar los repos que siguen sin banner
  mientras no diga otra cosa.

## 4. README (esqueleto que funciona)

1. `<img src="img/banner.svg" width="100%">` (sólo si el banner está aprobado) · 2. título + una línea de qué es ·
   3. badges de shields.io (estado
   del sitio con `?url=`, último commit, lenguaje, estado del workflow) · 4. tabla de enlaces (sitio, API,
   histórico, bot) · 5. capturas con `width` para que no dominen · 6. qué incluye · 7. cómo funciona (diagrama
   ASCII de componentes y flujo) · 8. API con el JSON real de ejemplo · 9. cómo compilar · 10. estructura ·
   11. pendientes · 12. créditos de la fuente de datos · 13. licencia.

**El diagrama de «cómo funciona» va en SVG, no en ASCII.** Un diagrama ASCII se renderiza como bloque de código y él
lo lee como texto plano: la corrección fue «me sigue saliendo eso, no se ve para nada técnico» sobre un README cuyo
contenido ya estaba bien (parámetros, tablas, todo medido). Lo que pidió ver, y quedó: **diagrama de arquitectura
SVG** —una fila por etapa, una caja por paso y **los parámetros reales del sistema dentro de las cajas** en
monoespaciada ámbar (la ventana de 300 s, `logsSubscribe`, `flock`, los 6 saltos de fondeo)— más un **bloque ```diff
de métricas** con lo medido (lo bueno con `+`, lo malo con `-`; es la única forma de meter color en un README y de
paso obliga a mostrar la mediana contra el pico). Trampas del SVG: las etiquetas de fila de 10+ caracteres chocan con
la primera caja (dejarlas en **una sola palabra**) y hay que renderizarlo y **mirarlo** antes de commitear. Receta
completa: skill `sitios-estaticos-gratis` → `references/imagenes-repo.md`.

**Sin emojis** en títulos ni viñetas: los pidió fuera de los artefactos publicados (en el chat sí los usa). Si un repo
 ya tiene emojis escritos, sacarlos es un cambio mecánico (regex de pictogramas) y hay que **conservar** las flechas
`→` del diagrama y los `·` de las tablas.

**Sin jerga con olor a IA** (esto **reemplaza** al viejo «que suene complicado»: el pedido de vestir el texto con
vocabulario de tesis lo corrigió después). Fuera: «bajo el capó», «caja negra», «serverless», «trazabilidad»,
«pipeline», «motor de detección», «agregador multi-fuente», «cascada de resolución determinista». Cuando pide **más
técnico** quiere **detalle concreto aportado**: umbrales («volumen ≥1,2× y ADX ≥20»), cifras, cómo se calcula cada
cosa, casos límite («división por cero cuando la pérdida media da 0»), qué pasa en cada paso. El resto del texto con
**voz humana**: frases cortas, voz de quien construyó la cosa —«Escanea 20 pares cada 15 minutos… Cuando encuentra
una, la puntúa, la manda y anota entrada, objetivo y stop para ver cómo terminó»—. El bloque de honestidad con los
números que no favorecen al proyecto **se conserva**: lo valora.

**Al editar el README, no borrar las líneas en blanco** (chequeo en §8): sin blanco, Markdown pega título, badges,
tablas y bloques HTML crudo. El `<img>` deja de renderizar y él lo reporta como «la imagen aún no sale en la página
principal», aunque el archivo esté publicado y dé 200. Cualquier limpieza de líneas vacías se hace mirando que cada
tabla y cada `<img>` queden con una línea en blanco arriba y otra abajo.

Los créditos a la fuente externa de datos **no se omiten**: si el número sale de la API de un tercero, va con enlace.

**Favicon (la «miniatura de la pestaña»)**: la pide él en la misma pasada. Receta en la skill `sitios-estaticos-gratis`:
los cuatro archivos, el SVG editable y, sobre todo, el sello `?v=N` en las URLs, porque el navegador sigue mostrando
el ícono viejo y el usuario concluye «aún no me sale» aunque lo publicado sea lo nuevo.

## 5. Ficha del repo por API

```bash
PATCH /repos/<owner>/<repo>          {"description": "…", "homepage": "https://<dominio>"}
PUT   /repos/<owner>/<repo>/topics   {"names": ["bolivia","dolar-blue", …]}
```

Etiquetas: minúsculas, con guiones, sin acentos ni espacios; unas 10 cubren tema + país + stack. La descripción es una
línea con qué hace y cómo corre; el `homepage` es el sitio en vivo.

## 6. Limpieza de duplicados (medida) y `build.sh`

```bash
du -sh <carpeta_duplicada>…        # medir ANTES: ese total va en el reporte
git rm -r -q --cached <rutas>      # fuera del índice
rm -rf <rutas>                     # y del disco
git add -A && git show --stat --oneline HEAD
```

Duplicados típicos: copias viejas del sitio (`frontend/`, `simple_build/`) y, dentro de la carpeta de compilación, el
código sincronizado y el `dist/`. Todos se regeneran con `build.sh`, así que van al `.gitignore` (`build/src/`,
`build/dist/`, `build/public/`, `build/node_modules/`, `build/package-lock.json`).

El `build.sh` vive en la carpeta de compilación, con `set -euo pipefail`, y hace cuatro pasos: sincronizar el código
fuente → instalar dependencias si faltan (`npm install --legacy-peer-deps`) → compilar → copiar `dist/index.html` y
`dist/assets/` sobre `docs/` **sin tocar** `docs/api/`, `docs/history.json` ni `docs/CNAME`. La receta de compilación
en sí (versiones de vite/tailwind, el alias `@`, los choques de React 19) está en la skill `sitios-estaticos-gratis`.

## 7. «Sacá una foto del código» (Pygments + ventana de editor)

```bash
python3 -m venv /tmp/venvpyg && /tmp/venvpyg/bin/pip -q install Pygments
tail -n +416 signals.py | head -33 > /tmp/frag.py        # el tramo real que se quiere mostrar
/tmp/venvpyg/bin/pygmentize -l python -f html -O full,style=monokai -o /tmp/pyg.html /tmp/frag.py
```

- Del HTML `full` de Pygments se aprovechan **dos** piezas: su `<style>` (los colores de los tokens) y el `<pre>`. El
  `<pre>` se mete dentro de un HTML propio —ventana de editor: barra con tres círculos, cabecera con el nombre real
  del archivo— y así se controla el resto del estilo.
- **Obligatorio forzar el color del texto base**: `pre{background:#0f0f0f !important;color:#f8f8f2 !important}`. Sin
  eso el fondo claro de Pygments deja el texto en negro sobre el fondo oscuro y él lo reporta como «el texto se ve en
  color negro». El `!important` sobre el `pre` **no** pisa los tokens (cada `span` trae su color): arregla sólo el
  texto suelto.
- Snippet corto (~30 líneas) para que se lea a ~1000 px de ancho, con nombres reales del repo; capturar con Chromium
  (`--screenshot`) y **mirarla** con `vision_analyze` antes de publicarla.

## 8. Verificación de lo publicado (¿se ve de verdad?)

```bash
curl -s -m 30 -A "Mozilla/5.0" "https://github.com/<owner>/<repo>" -o /tmp/p.html
grep -c "img/codigo.png" /tmp/p.html      # ¿GitHub incluye la imagen al renderizar el README?
grep -c "<table"            /tmp/p.html      # una por cada tabla del README: si faltan, el formato está roto
```

- **Que el archivo dé 200 no alcanza.** `raw.githubusercontent.com` sirve una copia cacheada varios minutos: puede
  mostrar el README viejo y hacer creer que el push no llegó. La verdad está en el HTML de la página del repo o en
  `GET /repos/<owner>/<repo>/contents/<ruta>` (ese endpoint es el que confirma que el commit entró).
- `https://github.com/<owner>/<repo>/raw/main/<ruta>` responde **302** a propósito: para probar el binario, seguir el
  redirect (`-L`) o pedir el raw directo.
- **Chequeo de líneas en blanco** (la causa del «no se ve la imagen»): contar las líneas vacías del README y verificar
  que el `<img>` tenga una en blanco arriba y otra abajo. Un README sano tiene veinte y pico.
- **Jerga = 0**: grepear el HTML renderizado por los términos prohibidos de §4 antes de declarar el repo terminado.
- **Que se VEA técnico, no sólo que lo sea**: contar en el README las piezas visuales —diagrama de arquitectura y foto
  del código— y el bloque ```diff de métricas. Un README sin ninguna de ellas vuelve con «no se ve para nada técnico»
  aunque el texto esté lleno de umbrales y cifras, que es lo que pasó con el último repo de la tanda.
- Si del lado de GitHub está todo bien y él sigue sin verlo, es **caché del navegador o de la app**: darle la URL
  directa del raw para que abra la imagen y sugerir incógnito. No rehacer nada por eso.
- Si cita un hash de commit distinto al que le pasaste, no discutir: `git rev-parse <abbrev>` y devolverle el **SHA
  completo** (la interfaz de GitHub y `git log --oneline` abrevian distinto).
