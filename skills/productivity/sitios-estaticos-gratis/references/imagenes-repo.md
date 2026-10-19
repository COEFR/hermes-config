# Imágenes de un repo: foto del código, banner y capturas

Todas salen de renderizar HTML/SVG en el Chromium que ya está en el equipo
(`~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome`) y de ajustar con Pillow
(`/tmp/venvimg/bin/python`, venv armado con `uv` si no existe).

## Foto del código (la que el usuario pidió y le gustó)

Es una ventana de editor falsa con código real resaltado. Pasos:

1. Elegir un fragmento que **explique el sistema**, no una utilidad: el algoritmo central del proyecto (p. ej. el
   union-find que arma los grupos, el indicador que genera la señal). ~20 líneas, sin `import` ni `if __name__`
   de arranque.
2. Resaltar a HTML completo:
   `pygmentize -l python -f html -O full,style=monokai -o out.html fragmento.py`
3. Quedarse con `<style>…</style>` y `<pre>…</pre>` y envolverlos en una ventana propia: barra con tres puntos
   (rojo/amarillo/verde), título con `archivo.py · qué hace`, borde redondeado, todo sobre fondo casi negro.
4. **Forzar el texto claro.** El HTML de Pygments viene con fondo claro y texto oscuro; incrustado así se lee mal.
   Regla: `pre, pre * { background:#101010 !important }` y `pre { color:#f8f8f2 !important }`.
5. Capturar y convertir:
   `chrome --headless --disable-gpu --no-sandbox --hide-scrollbars --window-size=1010,600 --screenshot=out.png "file:///tmp/ventana.html"`
   → Pillow reescribe a PNG optimizado (~47 KB).
6. **Mirarla con visión antes de subirla.** Si el código no se lee, la foto no sirve por más linda que sea la
   ventana.

## Banner (SVG)

`<img src="img/banner.svg" width="100%">`. GitHub renderiza el SVG inline pero **sanitiza scripts y fuentes
   externas**: todo con `<rect>`, `<text>` con `font-family` genérica y un `viewBox` ancho (≈1200×300). Renderizarlo
   con el mismo Chromium y mirarlo: el texto se pisa con los adornos si no se ajusta. **Default: sin banner** (el
   usuario lo rechazó dos veces; ver SKILL.md).

## Capturas del sitio

`--virtual-time-budget=12000` para que el JS alcance a escribir los datos (sin eso la captura sale **en blanco** y
pesa ~5 KB) y `--screenshot` toma **toda la página**, no el viewport. Optimizar con Pillow antes de subir. Sirven
como prueba real de que el sitio renderizó con datos, no como maqueta.

## Diagrama de arquitectura (lo que más cambia la impresión)

El README que el usuario calificó de «no se ve nada técnico» ya tenía el contenido bien: le faltaba la capa visual,
no los datos. El diagrama es la pieza que más pesa. SVG escrito a mano:

- Una **fila por etapa** (ingesta, agrupamiento, origen, medición) con la etiqueta al margen izquierdo y una **caja
  por paso** (`rx=10`, `fill` en degradado oscuro, borde `#2c2f35`), unidas con flechas (`<marker>` + `marker-end`).
- Dentro de cada caja, **los parámetros reales del sistema** en monoespaciada ámbar (`300 s · 0,1 SOL mínimo`,
  `jsonParsed · paginado · caché`, `6 saltos hasta el pagador`): eso es lo que lo hace técnico en vez de decorativo.
- Un lazo de control en **verde punteado** que vuelve del test contra el azar al pipeline («si no le gana al azar,
  no sirve») y un pie con las decisiones de fondo (librería estándar, sin tokens de LLM, `flock`).
- Ancho ≈1240, una fila cada ≈160 px, fondo `#0b0c0e`; en el README va como `<img src="img/arquitectura.svg"
  width="100%">`, solo entre dos líneas en blanco.

**Trampa: las etiquetas de fila se cortan.** Con `font-size 13` una etiqueta de 10+ caracteres choca con la primera
caja (que arranca en x=120): «AGRUPAMIENTO» y «ORIGEN Y VIVO» salían cortadas y hubo que acortarlas. Dejarlas en
**una sola palabra**. Y **renderizarlo y MIRARLO antes de commitear** (captura del SVG + visión): una etiqueta
pisada o una flecha fuera de lugar no se detectan leyendo el código.

## Bloque de métricas en rojo/verde

Un ```diff con los números medidos —lo bueno con `+`, lo malo con `-`— es la única forma de meter color en un README
sin salir de Markdown, y de paso obliga a mostrar también lo que no conviene (mediana contra pico, insiders
rentables: cero, el umbral que descalifica). Va dentro de la sección de hallazgos; el **gráfico** de resultados,
  en cambio, va arriba de todo (ver abajo).

## Gráfico de resultados (barras, generado desde los datos)

Lo que el usuario pidió como «más bonito» no era decoración: era ver el resultado sin leer una tabla. SVG de ~1000 px
de ancho, escrito **por un script que lee el JSON de resultados** (`grafico_resultados.py` → `img/resultados.svg`), y
ese mismo script escribe la tabla Markdown que va debajo: una sola fuente, cero contradicciones, y se regenera
cuando el medidor completa más datos.

- Encabezado con el universo medido y **la línea base explícita** («1.029 calls del registro · línea base: el FDV
  del momento en que el bot publicó el contrato»). Una fila por call: puesto, token, `aviso → pico`, barra y múltiplo.
- Barra proporcional al múltiplo (`largo_barra * mult / max`), degradado ámbar, y el **ancho máximo acotado**
  (~370 px sobre 1000): si la barra llega al borde, la etiqueta del múltiplo del primero queda encima de la barra y
  no se lee.
- Lo que no se midió, `—`; y un pie con el motivo por el que el pico del aviso puede superar al ATH del pool.
- **Filtrar antes de graficar**: las filas con la base rota se van al podio y arruinan el gráfico (ver SKILL.md).

**Trampa que deja el gráfico en blanco: entidades HTML en un SVG.** El SVG es XML: `&middot;`, `&rarr;` y cualquier
entidad fuera de las cinco predefinidas (`&amp; &lt; &gt; &quot; &apos;`) **no parsean**; Chromium dibuja un
rectángulo vacío sin decir nada. La señal es el peso: ~4 KB de PNG contra los ~100 KB de uno con contenido. Usar los
caracteres reales (`·`, `→`) con el archivo en UTF-8 y validar antes de subir:
`python3 -c "import xml.etree.ElementTree as ET; ET.parse('img/x.svg')"` — un `undefined entity` en la línea N lo
delata. Renderizarlo y **mirarlo con visión** igual: puede parsear y aun así tener el texto pisado.
