---
name: sitios-estaticos-gratis
description: "Use when publicando, reviviendo o manteniendo un sitio gratis con datos propios."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [github-pages, hosting, dns, https, api-publica, cotizaciones]
    related_skills: [github, publicar-proyectos-github, trading-signals, hermes-local-ops]
---

# Sitios y paneles propios, gratis y sin VPS (GitHub Pages + Action)

Cuándo: «reviví / publicá / poné online» un sitio o panel propio (cotizaciones, landing, tablero) y no hay VPS que
pagar. Implementación de referencia, ya funcionando: `~/.hermes/data/dolarbolivia/` — sitio React compilado en
`docs/` + `tools/tasas.py` (genera los datos) + `.github/workflows/tasas.yml` (lo corre cada 10 min).
**Extender eso, no rearmarlo.** Leer el `NOTAS.md` del proyecto antes de tocar nada.

## Arquitectura que funciona
- **Repo público** (Pages gratis solo en repos públicos) con el sitio **compilado** en `docs/`: `index.html`,
  `assets/…` y una carpeta propia `api/` con los JSON de datos.
- **Una Action** con `schedule` + `workflow_dispatch` que consulta la fuente, escribe `docs/api/<algo>.json` y
  **commitea** — el commit redespliega Pages solo. Necesita `permissions: contents: write`.
- El front pide los datos por **ruta relativa** (`api/rates`, no `/api/rates`).

## Procedimiento
1. **Subir el sitio** (repo nuevo o existente) con el sitio compilado en `docs/`, un `README` que explique de
   dónde salen los datos y un `.gitignore` que deje fuera `.env`, cachés y volcados. **Antes de hacerlo público,
   grepear claves en el árbol** (`grep -rniE 'ghp_|api[_-]?key|token|secret'`) y revisar que no viajen datos ni
   cachés: un repo público es para siempre. El grep por **nombre** no alcanza (nombres locales como
   `llave_github` no matchean `id_rsa`): escanear también por contenido. Para publicar o poner al día el lote
   completo de proyectos (con candado de secretos y verificación repo por repo): skill
   `publicar-proyectos-github`.
2. **Activar Pages** por API: `POST /repos/{owner}/{repo}/pages` con
   `{"source": {"branch": "main", "path": "/docs"}}`. El **204 no trae cuerpo**: leer el cuerpo vacío como
   «falló» es un falso negativo clásico. Después `PUT /repos/{owner}/{repo}/pages` con
   `{"cname": "<dominio>", "https_enforced": true}`.
3. **DNS en el panel del usuario** (no es de GitHub): **4 registros A** a `185.199.108.153`–`185.199.111.153`,
   **CNAME `www` → `<usuario>.github.io`**, y **borrar el A viejo** que apunte a otro hosting (ese es el motivo
   número uno de «el sitio está caído con dominio propio»). TTL automático. Si pide los valores «en un block de
   notas», mandar además un `.txt` adjunto (`MEDIA:<ruta>`) con los valores exactos para copiar.
4. **Verificar** con HTTP medido, nunca con la sensación: `curl -s -o /dev/null -w '%{http_code}'` al dominio y
   al archivo de datos, y leer el JSON para confirmar que el número es fresco (marca de tiempo de hoy).

## Recompilar el sitio (tocar el código, no parchear el minificado)
El proyecto real está en `dolarbackup/`: **la fuente completa vive en `backend/src/`**; `frontend-source/` sólo
tiene las configs (`vite.config.ts`, `index.html`, `tsconfig*.json`).

**Camino corto, que ya está montado**: `dolarbackup/build/` tiene sus `node_modules` (con `lightweight-charts` y
`recharts`) y un `build.sh` que hace todo: sincroniza `backend/src` → `build/src`, corre Vite y copia `dist/` sobre
`docs/` conservando `docs/api/`. Editar **siempre** `backend/src/…` (es la fuente; `build/src` se pisa en cada
corrida) y compilar con `cd dolarbackup/build && ./build.sh` (~15 s). Comprobar que salga un `assets/index-<hash>.js`
nuevo en `docs/assets/`: el script imprime «Compilado y publicado» aunque el build haya fallado, porque el pipe se
come el exit code (Trampa 11).

Receta manual, sólo si el staging se perdió:
1. Staging en `dolarbackup/build/`: copiar `backend/src`, las configs, un `public/favicon.*` y un `index.html`
   con `<script type="module" src="/src/main.tsx">`.
2. `package.json`: partir del de `backend/` (trae las deps del código: radix/recharts/lucide) y agregar
   `vite@^6`, `@vitejs/plugin-react@^4`, `tailwindcss@^3`, `postcss`, `autoprefixer`, `react-router-dom`.
3. `vite.config.ts`: `base: './'` + `resolve.alias { '@': fileURLToPath(new URL('./src', import.meta.url)) }`
   (los imports usan `@/…`, y `__dirname` no existe en una config ESM).
4. `tailwind.config.js` + `postcss.config.js`: el CSS usa `@tailwind base/components/utilities` = **Tailwind v3
   con PostCSS**; el plugin `@tailwindcss/vite` es v4 y **no** procesa esas directivas.
5. `npm install --legacy-peer-deps` (React 19 choca con next-themes 0.3 y recharts 2 → subir a `next-themes@^0.4`
   y `recharts@^3`, más `react-is` que recharts 3 necesita) y `node node_modules/vite/bin/vite.js build`.
   **No usar vite 8/rolldown**: rechaza los imports de tipos (`«X is not exported by types/y.ts»`) que el código
   escribe sin `import type`.
6. Desplegar: copiar `dist/index.html` + `dist/assets/` sobre `docs/` **borrando los assets viejos**, y conservar
   `docs/api/`, `docs/history.json` y `docs/CNAME`.
7. Verificar en vivo: que el asset nuevo (`assets/index-<hash>.js`) dé **HTTP 200** y que el bundle servido
   contenga la marca del arreglo (`curl … | grep -c '<texto nuevo>'`).

## Agregar una gráfica de precios (velas estilo TradingView)

Pedido típico: «que haya un gráfico de <activo> vs <moneda>», «hacelo como una tabla de TradingView». La receta
—librería, agregación en velas, fuente del dato y recolección— está en `references/graficas-precios.md`, junto con
la sección «Replicar la gráfica de una página de referencia» para cuando el pedido llega como «en esta página hay
una gráfica, implementala en mi página». Estas reglas van siempre, y todas costaron una ronda:

- **«En esta página hay una gráfica, implementala en mi página»: el entregable es ESA gráfica dentro de SU página,
  no una página nueva.** Armar un `/grafico/` aparte se lee como no haberlo escuchado y hay que rehacerlo. Antes de
  escribir una línea: localizar el componente que HOY dibuja el gráfico en la portada (`grep -rn '<Componente'
  `src/pages/`) y el staging de build ya montado (`dolarbackup/build/build.sh`); el trabajo es reemplazar ese
  componente y recompilar, no montar un sitio paralelo. Si la página aparte ya se creó, **se borra de verdad**
  (`git rm -r docs/<pagina>`) y se comprueba que devuelva **404**: dejarla viva es lo que hace preguntar «¿lo
  duplicaste?». Y ante «quiero que esté igual», preguntar **qué eje**: apariencia (tema claro/oscuro) o datos y
  controles — este usuario eligió conservar el tema oscuro de su sitio con los controles de la referencia.
- **La gráfica de la referencia se replica desde su bundle, y sus endpoints SÍ se dejan leer con encabezados de
  navegador.** A un pedido pelado contestan **403**; con `User-Agent` + `Referer` + `Accept: application/json`
  devuelven las velas ya agregadas (`/grafico/parallel?range=&interval=`). Eso no sirve sólo para medir la vara:
  **es lo que completa nuestro pasado** (7 d de 15m, 30 d de 1h, 6 m de 4h, 1 a de 1d) sin inventar un dato.
  Del bundle se saca lo otro: qué librería usan, qué controles tienen y qué capas dibujan. Receta y regla de
  fallback en `references/graficas-precios.md` → «Completar el pasado».
- **Auditar la gráfica que YA está en el sitio antes de mejorarla: puede estar inventando los datos.** Una serie
  hecha con `Math.random` alrededor del precio actual tiene forma de gráfico y nadie la nota — se publica durante
  meses como si fuera historia. `grep -rnE 'Math\.random|generateHistory|mock|dummy|placeholder' src/` y leer los
  comentarios de los componentes de gráfico es el primer paso. Encontrado así un `// Generate realistic mock
  historical data` que era una caminata aleatoria.
- **«El gráfico no aparece»: comprobar que el componente se RENDERIZA, no que está importado.**
  `grep -rn '<Componente' src/pages/` — un `import` sin uso compila perfecto, el build sale en verde y el sitio
  sigue sirviendo lo viejo; el tiempo se pierde buscando caché o deploy, donde no está el problema. Recién después
  verificar el bundle: `curl` al `index.html` sin caché para sacar el hash servido y grepearle dentro la marca del
  arreglo (el nombre de la librería, la ruta del JSON nuevo). El hash nuevo da **404 hasta que Pages despliega**
  (uno o dos minutos): no leer ese 404 como fallo.
- **«Creo que no lo publicaste» con el sitio ya publicado: darle un sello de versión visible, no otro push.** Pages
  sirve el HTML con `max-age=600`, así que una publicación de hace minutos convive con su copia vieja y él no tiene
  cómo saber qué está mirando. Probar primero por contenido —`curl` al HTML, sacar el hash del bundle, bajar ese
  `.js` del dominio y `grep` de la marca del arreglo (p. ej. `setStretchFactor`)— y después hacer que el sitio lo
  diga solo: imprimir en el pie la versión que corre (`document.querySelector('script[type="module"]')?.src`, el
  hash del archivo) y entregarle la URL con `?v=<timestamp>` más Ctrl+Shift+R. La próxima vez basta con pedirle que
  mire ese sello; se ahorra la ronda de «¿lo subiste?» y la discusión sobre caché.
- **«Hay un menú repetido» casi nunca es un menú duplicado: son dos controles distintos.** Rango (Hoy · Ayer ·
  3 d · 7 d · 1 mes … Todo) y temporalidad (5m · 15m · 1h · 4h · 1D) van en dos filas, igual que en TradingView.
  Antes de tocar el componente, contarlos en el DOM servido: `chrome --headless=new --dump-dom <url> > dom.html`
  y `grep -o 'Estocástico\|Compartir\|1 mes\|Velas' dom.html | sort | uniq -c`. Si cada uno aparece **una** vez,
  el problema es la caché del navegador (Ctrl+Shift+R) o la lectura de las dos filas como una sola; si aparece dos
  veces, hay dos componentes montados (`grep -rn '<Componente' src/pages/`). Contestar con el conteo medido
  («34 botones, uno de cada uno»), no con «no está duplicado».
- **Una gráfica que se congela: el Action mide, pero no versiona lo que deriva.** Si un paso anota cada medición
  en un CSV (`data/historial_p2p.csv`) y otro lo convierte en el JSON que dibuja el gráfico
  (`docs/api/historial.json`), el workflow tiene que **correr los dos pasos y listar los dos archivos en `git add`**.
  Lo que no está en el `git add` muere con el runner efímero: el precio se sigue publicando y el gráfico queda
  clavado en la última fecha que alguien commiteó, **sin ningún error en la corrida**. Síntoma único: la cabecera
  del JSON dice `"hasta": "<fecha vieja>"` mientras el resto del sitio está al día. Arreglo: agregar el paso que
  regenera, y **rescatar lo perdido desde otro archivo que sí se commiteaba** (el histórico de precios que el
  workflow ya versiona) agregando sólo las filas posteriores a la última marca del CSV — sin duplicar y sin
  rellenar el hueco con un precio plano. Cerrar con el rango publicado (`hasta` = hoy) leído del árbol del remoto
  y del dominio: el JSON va por el CDN de Pages y puede tardar minutos en mostrar el rango nuevo, así que un
  `hasta` viejo ahí no significa que el push falló (confirmar con `git show origin/main:<ruta>` y
  `GET /repos/{o}/{r}/pages/builds/latest`).
- **«Las barras se ven mal» casi siempre es densidad de datos, no la librería.** `open/close` es el cuerpo y
  `high/low` la mecha: con **una sola medición por vela** open = close = high = low, el cuerpo mide cero y la
  librería dibuja un guion de 1 px — ninguna opción del chart lo engrosa. Antes de tocar el componente, contar
  cuántas mediciones caen por bloque y cuántas velas tienen `high - low > 0`; si es ~1 por vela, el arreglo es
  **muestrear más seguido** (la referencia lo hace cada 60 s) y **un solo escritor del CSV**, no otra configuración.
  **Y la resolución del precio es la otra mitad**: con la mediana a 2 decimales el valor se repite dentro del bloque y
  la vela mide cero igual — la referencia guarda 4 decimales porque promedia los anuncios. Guardar 4 en el CSV y **no
  redondear a 2 al armar las velas** (receta y números medidos en `references/graficas-precios.md` → «Velas planas»).
  Mientras no haya densidad, dejar por defecto el intervalo que sí la tenga (1h/4h) y decir cuál se llena solo y
  cuándo. **Y contar bien los huecos**: el eje de la librería es por índice, no por tiempo, así que lo que parece un
  espacio vacío casi siempre es un doji de 1 px — lo que evita rellenar la serie (rellenarla la empeora). Antes de
  culpar al componente, medir además **si la fuente se mueve** (5 lecturas en 3 min): un precio plano no produce
  velas con cuerpo ese día. Diagnóstico, receta y qué NO hacer: `references/graficas-precios.md` → «Velas planas».
  **Si pide «inventá datos para ver si las barras están bien» es una prueba de render**, no un dato a publicar:
  generarlos en `~/.hermes/cache/scratch/`, servir en `127.0.0.1` y capturar Hoy/5m (prueba que dibuja bien) y
  7d/15m (prueba que el ancho es el límite); nunca commitearlos. Para completar los rangos largos se usa el **CSV
  diario abierto de la referencia** (819 velas desde 2024, sin huecos, con atribución), no Binance: no tiene par
  USDT/BOB al contado ni histórico público de P2P. Detalle en `references/graficas-precios.md` → «Qué NO puede dar
  Binance».
- **Antes de escribir código, buscar quién ya lo resolvió** — es lo que el usuario pide con «investigá en Reddit y
  GitHub cómo lograr esto». Lo que aparece ahorra el trabajo entero: la librería del propio TradingView, un repo
  público con el histórico ya recolectado, dos APIs abiertas del país. Reportar los hallazgos diciendo qué aporta
  cada uno y cuál se elige, y recién después tocar el proyecto.

## Traer cotizaciones EXACTAS de una página de referencia
Pedido típico: «quiero que los valores sean exactos, tomá de referencia esta página».
1. **Buscar la API pública de la referencia antes de scrapear**: bajar el HTML y el JS compilado y
   `grep -oE 'https?://[a-zA-Z0-9.-]+/[a-z0-9/_-]*'` → base de la API; probar `/health` y los endpoints
   (`/v1/...`) con `curl`. Casi siempre el número que se ve en pantalla sale de un endpoint que ya está
   verificado por ellos: usarlo como **fuente primaria** y dejar el scrape propio como **respaldo**.
   Ya integrado y funcionando: `https://api.dolarbluebolivia.click/v1/officialRate` (manda el blue compra/venta y
   el oficial unificado en un solo llamado, sin API key) — fuente primaria de `tools/tasas.py`;
   `/v1/official-unificado` da el oficial con sus fechas de vigencia.
2. **La autoridad es el número que la referencia muestra en su PÁGINA, no el de su API.** Las APIs de referencia
   suelen devolver convención de exchange (`buy` = el número **bajo**, `sell` = el alto) mientras su propia página
   etiqueta al revés (`COMPRA` = el número **alto**, lo que al usuario le cuesta comprar): el mismo momento puede
   leerse `buy 11.82 / sell 11.86` en la API y `Compra 11.86` en la página. El bundle del front
   (`grep -o '.\{60\}Compra.\{60\}'`) dice **qué campo** consume cada etiqueta, pero **no** decide la convención:
   la del usuario es la de la página que él mira. Leer el **DOM renderizado**
   (`chrome --headless --dump-dom <url> | tr '<' '\n<' | grep -iE 'compra|venta' -A6`) — filtrando siempre, un
   volcado completo son ~90 KB que se comen el contexto —, comparar campo por campo y dejar en el JSON los nombres
   explícitos (`compra`/`venta`) además de `buy`/`sell` para que la ambigüedad no vuelva.
3. **Marcar el origen en el propio dato**: el JSON lleva `"fuente": "<referencia>"` cuando salió del endpoint
   verificado y `"fallback"` cuando se usó el scrape propio — así el front (y el usuario) saben si la lectura
   está respaldada o es de reemplazo.
4. **Cerrar con la comparación campo por campo**: referencia → nuestro JSON → «coinciden: SÍ/NO». No alcanza con
   «quedó mejor»; el usuario pidió exactitud y quiere ver el número de la referencia al lado del nuestro.
5. **Acreditar la fuente** en el `README` y en el pie del sitio (una línea).

## Que el dato esté SIEMPRE al momento (arquitectura en capas)
Pedido típico: «es importante que el precio esté cotizado al momento». Un JSON que escribe un bot programado
**siempre** puede estar viejo (el reloj de GitHub larga las corridas cada 1-9 h), así que la frescura se diseña en
capas, de la más fresca a la más vieja:
1. **El navegador lee la fuente directo, en cada visita** — lo más «al momento» que existe. Antes de darlo por
   imposible, **probar CORS**:
   `curl -s -D - -o /dev/null -H "Origin: https://<mi-dominio>" <api> | grep -i access-control`. Con
   `access-control-allow-origin: *` el front hace `fetch(<api>, { cache: 'no-store' })` directo: sin bot, sin token
   y sin reloj. Probado con `api.dolarbluebolivia.click` y `apibcb.cucu.bo`.
2. **Si la fuente no responde → el JSON propio** (`./api/rates`, relativo) → **si tampoco → el scrape del
   navegador** → y nunca un valor fijo (Trampa 1). Meter las capas **dentro de la función que ya consumía el JSON**
   para no tocar el resto del flujo.
3. **Si además el JSON tiene que estar fresco** (lo consumen la API pública, los posts de Facebook o un bot), el
   reloj es externo (Trampa 5). Orden de preferencia: cron-job.org del usuario → crontab local de este equipo →
   nada; decir el costo real de cada uno antes de elegir.
4. **Verificar con la medición antes/después**, nunca con «quedó mejor»: minutos de atraso antes y después, más el
   log de los disparos (p. ej. 74 min → 4 min, disparos 204 a las 22:05 y 22:10). Que la lectura sea en vivo se
   nota porque el número **se mueve entre dos consultas seguidas**.
5. **«¿Está al instante? ¿Sin delay?» → medir el piso de cada capa y decirlo, no prometer cero.** Cada sistema
   tiene un límite que ningún reloj arregla: la fuente tarda lo suyo en refrescar (medido: 1 min de antigüedad en
   el dato), las señales por indicadores se calculan sobre **velas cerradas** (antes del cierre el dato no existe;
   15m/1h/4h/1d → el piso es el cierre más el reloj) y un vigilante por WebSocket avisa en el **orden de los
   segundos** (medido en su propio log: *tardó 0.7 s*). Armar la tabla por capa con el número medido al lado
   (en vivo: 0,7 s · cotización: 1 min · señal: ≤5 min desde el cierre) y aclarar **qué se arregló de verdad**:
   que deje de saltearse chequeos (de cada 5-6 h a cada 5 min), no adelantar el piso técnico. El usuario pregunta
   seguido por el delay; lo que le sirve es el piso con su número, no un «es instantáneo».

## Embellecer el repo (README, foto del código, capturas, favicon, ficha)
Pedidos típicos: «embellecé el repo», «que la descripción suene más complicada», «cambiá la miniatura de la pestaña».
**Se hace de A UN repo por vuelta**: primero el inventario (qué tiene cada uno, cuál está peor), elegir el orden con
el usuario y cerrar cada repo con **verificación por API** (el README en la rama con sus secciones, los temas
aplicados, el conteo de archivos) y un reporte de números medidos, no de promesas. Cuando el pedido llega como
«lo mismo con el de <repo>», **confirmar cuál repo y mirar su estado actual antes de reescribir nada**: puede estar
hecho ya (el usuario lo ve viejo por caché del navegador) y el «perdón, me refería a <otro>» del turno siguiente
deja claro que el nombre dicho no siempre es el repo buscado. Si ya está hecho, responder con la prueba —commit y
secciones que sirve la API— y recordar el Ctrl+Shift+R, no volver a pasar el tratamiento. En la misma pasada, sacar del
índice la basura y bloquearla en `.gitignore`: `*.pid`, `*.log`, temporales, volcados.
- **Capturas reales, no maquetas**: el Chromium de Playwright ya está en el equipo
  (`~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome`). Un sitio React necesita `--virtual-time-budget=12000`
  (sin eso la captura sale **en blanco** y pesa ~5 KB) y `--screenshot=` escribe **toda la página**, no el viewport.
  Si no hay Pillow ni ImageMagick, un venv con Pillow pasa la captura de 2,3 MB a ~64 KB (y de paso genera el .ico).
  **Mirar la captura con visión** antes de subirla: así se confirma que el sitio renderizó con datos reales.
  Todas las recetas de imagen (foto del código, banner, capturas, **diagrama de arquitectura y bloque diff de
  métricas**) están juntas en `references/imagenes-repo.md`.
- **Favicon**: generar los cuatro archivos —`favicon.ico` multi-tamaño (`sizes=[(16,16),(32,32),(48,48),(64,64)]`),
  `favicon-32.png`, `favicon-192.png`, `apple-touch-icon.png`— y **declararlos todos** en el HTML. Guardar el diseño
  como SVG editable (`img/favicon.svg`) para poder cambiarlo en un minuto.
  **El ícono viejo NO se va con Ctrl+Shift+R**: el navegador cachea favicons por días y ni el refresco forzado los
  suelta, así que el usuario insiste con «aún no me sale» aunque lo publicado sea lo nuevo. La solución es
  **sello de versión en las URLs** (`./favicon.ico?v=2`, subiendo el número en cada cambio): el navegador lo trata
  como archivo nuevo y se saltea la caché. Antes de hablar de caché, **probar que el servidor sirve lo correcto**:
  `curl -s -o /tmp/s.ico <url> && md5sum /tmp/s.ico` contra el local (mismo hash = es nuestro problema cero) y
  `curl -s -D - -o /dev/null <url> | grep -iE 'age|cache-control'` (el CDN de Pages sirve el HTML con
  `max-age=600`; `age: 0` = ya está el nuevo). Y darle la prueba limpia: **ventana de incógnito** (sin caché); si
  ahí aparece, en su ventana normal se soluciona cerrando y reabriendo la pestaña, no con F5.
- **Ficha del repo** — parte del embellecido, por API: `PATCH /repos/{o}/{r}` con `description` + `homepage`, y
  `PUT /repos/{o}/{r}/topics` con `{"names": [...]}` (hasta 20, minúsculas y guiones). Misma voz técnica que el
  README: es lo primero que se lee al entrar. **La `description` tiene tope de 350 caracteres y pasarse devuelve
  `422` sin decir por qué** (el error no menciona el largo): contar con `len()` antes de mandarla. Ya rebotó dos
  veces por esto y el mensaje de GitHub no orienta nada.
- **Las etiquetas y el texto llevan reglas distintas.** Si el usuario pide evitar ciertas palabras («que no diga
  trading ni crypto»), **no sacarlas de las etiquetas sin preguntar**: los topics son el mecanismo de búsqueda de
  GitHub y ahí las palabras genéricas sirven; lo que se limpia es la `description` y el README. Corrección textual
  del usuario: «en la parte de las etiquetas puedes dejarlas». Conservarlas **sumadas** a las precisas que se
  agreguen (quedan 13 en vez de 11) y verificar las tres capas por separado: descripción sin ellas, README con 0
  apariciones, etiquetas que las llevan a propósito.
- **Banner: proponerlo, no imponerlo.** El usuario rechazó el banner dos veces («no me gustó», «elimínalo»): el
  **default es sin banner** salvo que lo pida. Lo que sí pidió y le gustó es la **foto del código real** (receta en
  `references/imagenes-repo.md`). Si va banner, SVG propio en `img/` referenciado como
  `<img src="img/banner.svg" width="100%">` (GitHub lo renderiza; sin fuentes exóticas ni scripts, que los
  sanitiza) y renderizarlo y mirarlo antes de subir para que el texto no choque con los adornos.
- **README**: badges de shields.io (incluido el del workflow), capturas y secciones: qué hace (los pasos del
  sistema), cómo funciona, estructura, reglas operativas y créditos de la fuente de datos. Voz corregida por el
  usuario: **sin emojis**, **sin jerga de IA** («bajo el capó», «caja negra», «servicio de datos») y tono humano y
  técnico; el vocabulario «que suene complicado» se permite **sólo si la capacidad existe de verdad** (larpear),
  nunca para inventar features.
- **Lo técnico no alcanza si no SE VE técnico.** Corregido así («me sigue saliendo eso, no se ve para nada
  técnico») sobre un README que ya tenía el contenido correcto: prosa sola = texto plano. Tres piezas visuales
  obligatorias: **diagrama de arquitectura** propio (SVG, una fila por etapa, con los **parámetros reales** dentro
  de las cajas), **bloque ```diff de métricas** (GitHub lo pinta verde/rojo; es la única forma de meter color en
  Markdown) y **foto real del código**, más la tabla de umbrales con el motivo de cada uno. Recetas y trampas en
  `references/imagenes-repo.md`. Cerrar midiendo: líneas, secciones, tablas, imágenes presentes y emojis en 0.
- **El registro del texto es la otra mitad, y suele corregirse después: voz coloquial = «se ve muy IA».** Corregido
  así («me refería al texto, hacelo más serio y más técnico, se ve muy IA») sobre un README que ya tenía el
  diagrama y los datos correctos. Lo que delata texto generado son las metáforas y los remates («se cae la
  máscara», «el corazón son treinta líneas», «snipers entretenidos», «no hay a quién venderle») y el comentario
  meta («esta sección va antes a propósito»). Reescritura que funcionó: oraciones declarativas («La vinculación se
  resuelve con union-find con compresión de caminos»), secciones con nombre de especificación (Arquitectura ·
  Parámetros · Implementación · Resultados medidos · Metodología · Estructura · Criterios fijos) y los resultados
  negativos en neutro, sin opinión. Los datos, el diagrama y la foto **no** se tocan: el cambio es de tono, y se
  explica con pares antes/después — eso es lo que hace entender y aceptar el cambio.
- **La sección más valiosa es «qué encontró», y lleva lo negativo primero.** El usuario quiere ver lo medido aunque
  no sea lindo: «insiders rentables: cero», «el reparto masivo tiene firma — el mismo saldo exacto repartiendo a
  cientos de wallets», «los grupos grandes son snipers». Un README que sólo cuenta virtudes no le sirve: es el que
  se lee para decidir.
- **Los resultados medidos van PRIMERO y como gráfico, no como tabla de texto.** Corrección textual: «poné más
  bonito el resultado de las calls y que esté al principio, es lo más importante eso». Van apenas el título y la
  línea de alcance, **antes** del pipeline y de la arquitectura: es lo que el lector vino a ver. La tabla de texto
  no alcanza para eso; el gráfico de barras (proporcionales, con el múltiplo al lado y el ATH donde esté medido) es
  lo que se mira. Generarlo **con un script que lea el propio JSON de resultados** (`grafico_resultados.py` →
  `img/resultados.svg`) y que **ese mismo script escriba la tabla Markdown** que va debajo: una sola fuente, el
  gráfico y la tabla nunca se contradicen, y se regenera cuando el medidor completa más datos. Antes de graficar,
  **filtrar las filas con la base rota** (un FDV de aviso de 48 USD da un múltiplo absurdo y se lleva el podio) y
  ordenar por el campo que se muestra, no por otro: un dato roto arriba desacredita todo el gráfico.
  Receta y trampas en `references/imagenes-repo.md`.
- **Agrupar los módulos por función** (cosecha, forense, vigilancia, medición, infraestructura) en lugar de listar
  decenas de nombres sueltos, y **no citar contadores volátiles** (wallets puntuadas, grupos clasificados, cohortes):
  cambian entre corridas según el estado del bot y el README queda mintiendo. Citar el proceso y lo medido estable.
- **Limpieza y build**: buscar duplicados (builds viejos de ~1 MB: `frontend/`, `simple_build/`, `build/dist/`),
  sacarlos del índice y bloquearlos en `.gitignore`; un `build.sh` de un solo comando reemplaza la receta manual.

## Trampas (todas costaron una ronda)
1. **Un respaldo fijo se convierte en cotización vieja sin que nadie lo note**: el oficial estaba hardcodeado en
   `11,37` y se seguía mostrando como oficial cuando el vigente era `11,73`. Regla: la fuente primaria en vivo,
   el respaldo **marcado** en el dato, y si el respaldo no llega → decir «sin dato» antes que publicar un número
   que puede no ser el de hoy.
2. **El bundle compilado trae rutas absolutas**: `${base}/api/rates` funciona en el dominio propio y **se rompe**
   en `usuario.github.io/repo/`. Parchear a relativa en el archivo compilado (y en la fuente si existe):
   `${base}api/rates`.
3. **`https_enforced: true` antes de que exista el certificado** devuelve *«the certificate does not exist yet»*:
   **no es un fallo**, GitHub lo emite minutos después de que el DNS resuelve. Reintentar más tarde y decirlo así
   al usuario. Mientras tanto el cert servido es el de `*.github.io`, así que un `curl https://<dominio>` normal
   falla por nombre: probar con `curl --resolve <dominio>:443:<ip-de-github> https://<dominio>/` para saber si el
   sitio ya responde.
4. **La caché DNS del propio equipo miente**: hay que consultar resolvers públicos (`dig +short @1.1.1.1 <dominio>`
   y `@8.8.8.8`). Medido: los públicos ya devolvían las IPs de GitHub mientras el resolver local seguía con la IP
   vieja → a punto de declarar «no propagó» cuando sí había propagado. Decirle al usuario que desde su celular
   puede tardar igual (caché del operador) y ofrecerle probar con datos móviles.
5. **El programador de GitHub es impuntual** (medido: corridas cada 1-9 h en vez de cada 10 min) → si el dato tiene
   que estar fresco, el reloj es **externo**: `POST /repos/{owner}/{repo}/actions/workflows/{file}/dispatches` con
   `{"ref":"main"}` (GET 404 · POST sin cuerpo 422 · POST con cuerpo 204) desde el cron-job.org que ya usa el
   usuario. Receta completa: skill `trading-signals` → `references/hospedaje-sin-vps.md`.
   **Antes de tocar la configuración del usuario, localizar el fallo disparando el mismo POST desde el terminal.**
   Medido: llegó `400 Bad request: the server could not understand the request`; desde acá, con su misma URL y su
   mismo token, respondió **204** con y **sin** `Content-Type` (ese encabezado **no** hace falta) → la falla estaba
   en **cómo llegaba el cuerpo**, no en la URL, el método ni el token. El 400 con ese texto es la firma de un
   **JSON malformado**, y la causa número uno es el pegado: **comillas curvas** que mete el teclado del celular, o
   barras invertidas de un `--data` copiado entero. Arreglo: que el usuario **borre el campo y escriba a mano**
   `{"ref":"main"}` (14 caracteres, comillas rectas, sin espacios). `The URL could not be parsed` es lo mismo pero
   en la URL: un espacio o un salto de línea colado al copiarla — dar las URLs como **texto suelto sin bloques de
   código** y el checklist (empieza con `https://`, termina en `/dispatches`, una sola línea). En el panel: el
   método en **POST**, el cuerpo en el campo del cuerpo, y el token como **encabezado**
   `Authorization: Bearer <token>` junto con `Accept: application/vnd.github+json`; **«Requiere autenticación HTTP»
   va apagado**, porque eso es basic auth y no es lo que usa la API.
   **Plan B validado cuando el usuario no quiere o no puede tocar cron-job.org**: un trabajo del **crontab de este
   equipo** que hace el mismo `POST` y loguea el código HTTP (`*/5 * * * * set -a; . /home/<usuario>/.hermes/.env;
   set +a; <script>.sh >> <log> 2>&1`), con el token leído del entorno (Trampa 8) y nunca dentro del script. **Ese prefijo no es opcional**: sin
   `set -a; . <ruta>/.hermes/.env; set +a` el script sale por falta del token, cron se come la salida (no hay
   `MAILTO`) y el log queda vacío — el síntoma se lee como «el reloj no dispara» cuando dispara y muere. Verificar
   que el log de disparos tenga líneas nuevas y el código HTTP, no que el `crontab -l` muestre la línea. Antes
   de editarlo, `crontab -l` y copia de respaldo: ya hay trabajos corriendo que no se deben pisar. Caveat que va en
   el mismo mensaje: **este reloj muere con el equipo**, mientras que la lectura en vivo del navegador (capas 1-2)
   sigue funcionando igual.
   **Un script por proyecto, no uno genérico**: cada uno hace el `POST` a su propio workflow, loguea el código HTTP
   y lleva su nombre, así el log dice cuál disparó. Medido: con el `schedule` propio de GitHub, un workflow pedido
   cada 5 min corrió **4 veces en todo el día**.
   **Cómo detectar que el reloj externo murió**: mirar el espaciado de las últimas corridas
   (`GET /repos/{o}/{r}/actions/runs?per_page=5`): si caen cada **horas** en vez de cada N minutos, el trabajo de
   cron-job.org dejó de disparar (medido en este equipo: `#602 01:29 · #603 07:45 · #604 14:50 · #605 19:26` con un
   reloj que debía correr cada 15 min; el de cron-job.org era del usuario y no se puede ver desde acá — hay que
   decirle que lo revise en su cuenta). Antes de proponer arreglarlo, **verificar si el problema es el reloj o el
   sistema**: si el bot igual mandó sus avisos (buscarlos en el log del ciclo), el sistema está vivo y lo único
   muerto es el disparador; un reporte viejo que dice «0 en 24 h» es la pista falsa clásica.
   **Con ciclo de trabajo corto (decenas de segundos) disparar cada 5 min no pisa nada**; si el ciclo es largo
   (minutos), el `POST` encima de una corrida viva encola en vez de cancelar — revisar el espaciado después.
6. **El push de la Action choca con cualquier empuje externo** → en el paso de guardado, `git pull --rebase
   --autostash` + reintentos, no `git commit && git push` a secas.
7. **Un deploy key (llave SSH) alcanza a UN solo repo** — el propio GitHub lo dice en el saludo
   (`Hi <owner>/<repo>!`). Para varios repos: una key por repo o un PAT. Preferir llave SSH para los pushes
   propios; un PAT clásico que se pegó en el chat hay que **rotarlo** después.
8. **Los secretos van a `~/.hermes/.env`, jamás dentro de un script ni impresos en el chat.** El entorno
   **enmascara los secretos** al escribirlos/leerlos: si el usuario dice que ya te pasó un token, **buscarlo en el
   historial de la sesión** antes de dudar de él, y no reescribirlo a mano (queda `***`). **Arreglo probado**:
   escribirlo **con el terminal**, que no enmascara → `echo 'NOMBRE=valor' >> ~/.hermes/.env && chmod 600
   ~/.hermes/.env`; y cuando lo consume un cron, cargarlo con `set -a; . /home/<usuario>/.hermes/.env; set +a` así
   el secreto vive en el entorno y el script nunca lo lleva adentro.

9. **`navigator.clipboard` y `navigator.share` sólo existen en contexto seguro (HTTPS)**: en HTTP son
   `undefined`; si el `catch` del botón usa el mismo API, el botón **no hace nada y sin aviso** (fue el caso de
   «Guardar imagen» y «Compartir»). Receta: respaldo con `document.execCommand('copy')` sobre un `<textarea>`
   temporal, aviso visible del resultado, y al compartir: nativo si hay `navigator.share`, si no WhatsApp
   (`wa.me/?text=`) + copiar.
10. **Un `git push` rechazado con «fast-forwards» puede ser un `.git/rebase-merge` colgado** de un intento
   anterior: `git rebase --abort` + `rm -rf .git/rebase-merge` antes de reintentar. **El mismo residuo miente
   de otra forma**: el `pull` contesta `Please make sure you have the correct access rights and the repository
   exists`, que manda a revisar el token cuando el token está perfecto, y deja la rama en **HEAD suelto**
   (`git branch --show-current` devuelve vacío). Diagnóstico en tres comandos, antes de tocar credenciales:
   `rm -rf .git/rebase-merge` → `git rebase --abort` → `git branch --show-current`; si sale vacío,
   `git checkout main` y recién ahí el pull/push. Vale para cualquier repo con bot que commitea solo. Si el choque es con el
   archivo que **genera la Action** (`docs/api/rates`), no pelearlo: `git reset --hard origin/main` +
   `git cherry-pick <mi commit>` dejando ese archivo fuera del commit — el bot lo regenera. **Pero `git reset --hard` borra lo que tengas
   preparado**, y con el bot commiteando cada pocos minutos eso se paga: la secuencia que no pierde trabajo es
   (1) terminar el cambio chico y commitear **todo** (`git add -A`), (2) `git pull --rebase` —con el árbol limpio
   no se niega; con cambios sin commitear responde «You have unstaged changes» y hay que commitear o stashear—,
   (3) push. Si el rebase igual se traba: `git rebase --abort` + `rm -rf .git/rebase-merge` →
   `git reset --hard origin/main` → **rehacer el cambio chico desde cero** → commit → push. La receta
   «reset --hard + cherry-pick de mi commit» sólo sirve si el commit **ya existe**; si estabas a medio preparar,
   el reset se lleva los cambios y hay que rehacerlos (medido: dos rondas perdidas por esto).
   **«push OK» no prueba que subió**: el código de salida y el texto no alcanzan —un push puede irse a otro HEAD
tras un rebase que se cortó—. Verificar por ascendencia contra el remoto: `git fetch <url> main` y
   `git merge-base --is-ancestor <mi-sha> FETCH_HEAD && echo SI`; y para el contenido, `git ls-tree -r --name-only
   FETCH_HEAD | grep <archivo nuevo>`. Si el archivo nuevo no aparece ahí, el commit propio no está.
   **Un conflicto en un archivo generado no se mergea, se regenera**: cuando el rebase se traba en `UU` sobre el
   JSON que produce el proyecto (`docs/api/grafico.json`), correr el generador (`python3 tools/grafico.py`),
   `git add` del resultado y `git rebase --continue` — elegir «los míos» o «los suyos» a mano deja un JSON que no
   corresponde a ningún estado real.
11. **Un pipe (`npm … | tail`) enmascara el exit code**: `vite build | tail` parece exitoso con `dist/` vacío.
   Mirar el tamaño de `dist/` y el mensaje final (`✓ built in …`), no `$?`.
12. **El certificado puede quedar en `None` (nunca solicitado) y no salir solo nunca.** Medido: con el DNS
   perfecto (los 4 A + CNAME `www`, sin CAA) y *horas* después, la API seguía devolviendo
   `https_certificate: None` y sirviendo el `*.github.io`. Arreglo: **re-disparar la emisión** quitando y
   volviendo a poner el dominio (`PUT /pages` con `{"cname": null}` y a los segundos
   `{"cname": "<dominio>", "https_enforced": true}`): pasó a `approved` al instante y el certificado propio
   (`subject=CN=<dominio>`) salió en ~2 min. Sin contexto seguro **no existen `navigator.share` ni el
   portapapeles moderno**: «el botón de compartir no abre la pantalla de redes» se arregla acá, no en el código.
13. **Configurar la identidad de git en el repo antes de rebasear**: sin `git config user.name` / `user.email`
   el rebase muere con `fatal: empty ident name … not allowed` y el push queda rechazado con la pista de
   siempre (`fast-forwards`), que manda a buscar el problema al lugar equivocado.

14. **La protección de push de GitHub frena el push si el árbol trae una llave**: pasó con
   `migracion/llave_github` (llave SSH privada) en un repo **público** → GitHub respondió
   `Push cannot contain secrets` y no subió nada (salvó la situación). Además del candado propio, excluir
   `migracion/`, `*llave*`, `id_rsa*`, `*.pem`, `*.key`; y **verificar por API el árbol del repo público**
   (`/git/trees/HEAD?recursive=1`) buscando nombres peligrosos: un nombre en español («llave») se escapa de un
   grep pensado en inglés. Y el candado propio debe exigir que el valor *parezca* clave (charset de clave, 24+
   caracteres), o marca falsos positivos como `if l.startswith("HELIUS_API_KEY=")`.

15. **Renombrar un repo deja referencias internas apuntando al nombre viejo.** El web y la API redirigen solas
   (301), pero el `raw` y los badges no: los que rompen son los **scripts que leen sus propios archivos por raw**
   (chequeos de salud del tipo `raw.githubusercontent.com/<o>/<r>/main/ultimo_ciclo.txt`). Barrer
   `git ls-files -z | xargs -0 grep -nE "<o>/<nombre-viejo>"`, actualizarlos (README, notas, scripts; los workflows
   suelen usar `${GITHUB_REPOSITORY}` y se actualizan solos), renombrar por API (`PATCH /repos/{o}/{r}` con
   `{"name": "..."}`) y **verificar que el raw responda por el nombre nuevo Y por el viejo** antes de cerrar.
   Actualizar además el **remoto local** (`git remote set-url origin <url-nueva>`): el empuje propio va con
   `https://x-access-token:<token>@github.com/…`, porque un `origin` pelado pide usuario y contesta
   «could not read Username» — parece un fallo de credenciales y es sólo que esa URL no lleva el token. Y con el
   repo **privado**, un `curl` sin sesión al repo devuelve **404 por diseño**: no es que el rename haya fallado,
   verificar con la API autenticada.

16. **Después de reescribir la historia, la API sigue contando el peso viejo.** Los blobs viejos quedan
   inalcanzables pero presentes en el almacenamiento de GitHub hasta su limpieza automática: la API reporta 20 MB
   cuando el contenido son 1,4 MB. **Medirlo clonando** (`git clone --depth 1` a un temporal y mirar el tamaño) en
   vez de prometer «comprimí el repo», y si el README tiene un badge de tamaño, sacarlo: es el único lugar donde el
   número fantasma se ve. Bajarlo de verdad exige borrar y recrear el repo, y eso **pierde los GitHub Secrets**
   (los tokens del bot) → no hacerlo.

## Al quitar una sección de un README, no borres las líneas en blanco

Un borrado por líneas (sacar un banner, por ejemplo) se lleva también las líneas vacías. Sin ellas el markdown
pega los párrafos, **las tablas no renderizan** y la imagen del README deja de verse: el usuario lo reporta como
«la imagen no sale». Contar las líneas vacías antes y después, y dejar el `<img>` solo entre dos. Si el usuario
insiste en que la imagen no aparece, mirar primero el HTML que sirve GitHub
(`curl -s https://github.com/<o>/<r> | grep -o 'src="[^"]*img/[^"]*"'`): si el `<img>` está, el problema es la
caché del navegador, no el repo (darle la URL raw del archivo para que lo compruebe él).

## Si una Action mantiene el estado de un bot, los archivos de estado van versionados

Un `.gitignore` con `*.json` deja afuera los `state*.json`, `ultimas_tareas.json` y las calibraciones: en GitHub
Actions cada corrida arranca de cero y el bot pierde cooldowns y memoria **sin dar ningún error**. Versionarlos
explícitamente (reglas `!state*.json` o `git add -f`).

## Sanear datos personales antes de publicar (repo público o no)

Un README o unas notas de proyecto acumulan cosas que no van en un repo: el nombre del dueño, citas de
sus pedidos («especificación pedida por <nombre>»), ids de canales de Discord/Telegram, rutas locales
(`/home/<usuario>/…`, `~/.hermes/…`) y rutas absolutas dentro de scripts.

Barrer con `git ls-files -z | xargs -0 grep -nE "<nombre>|<handle>|/home/|~\.|ids"` sobre los archivos
**versionados** (no sobre el árbol entero: lo ignorado no se publica). Reemplazos que funcionan:
«pedido de <nombre>» → «a pedido»; los paths → `"$(dirname "$0")"` en shell y `os.path.dirname(__file__)`
en Python; los ids → una variable de entorno.

**Trampa al verificar: `raw.githubusercontent.com` sirve copias cacheadas** (el `?cb=` de la query no la
rompe). Un grep contra la raw puede reportar como sucio un archivo ya limpio, o al revés. Verificar con
la API de contenidos (`/repos/{o}/{r}/contents/<ruta>` + base64) y, si el archivo es de producción (un
script del cron), correrlo después del cambio para confirmar que sigue funcionando.

**Los mensajes de commit son públicos y quedan en el historial**: nunca escribir ahí lo que se limpió
(«fuera datos personales», «saca 402 gráficos»). Un mensaje así llama la atención sobre lo que se quiso
borrar y sobrevive aunque el archivo se limpie. Usar mensajes neutros y sin detalles internos
(«estado del proyecto», «actualización»).

**Para borrar de verdad lo que ya está en la historia** (el contenido viejo y esos mensajes) hay que
reescribirla, no basta con un commit de limpieza:
1. Pausar lo que commitea solo: `PUT /repos/{o}/{r}/actions/workflows/<archivo>/disable` (204). Si no, la
   Action empuja en medio de la reescritura y choca.
2. En cada repo: `git checkout --orphan limpio` → `git rm -r --cached .` → `git add -- <lista exacta de
   `git ls-tree -r --name-only HEAD`>` → un commit neutro (`git branch -M limpio main`).
3. `git push --force https://x-access-token:<token>@github.com/...` — ojo con el `https://`, un `http://`
   da «Authentication failed».
4. Reactivar los workflows (`/enable`). Los commits siguientes ya llevan el mensaje neutro del workflow.

Verificar con `GET /commits?per_page=3` (debe quedar 1 commit con el mensaje neutro) y con el código:
`GET /search/code?q=<nombre>+repo:<o>/<r>` → `total_count: 0`.

## Tu análisis propio no va en un repo público (y el respaldo privado)

Las direcciones y las transacciones on-chain son públicas; **el criterio no**. Lo que hay que sacar de un repo
público son los archivos de **análisis**: los miembros de cada grupo detectado, los insiders marcados, las
clasificaciones, las auditorías y los calls detectados. Los `.json` de operación chicos (el estado del canal, la
lista de wallets seguidas) se quedan si alguna tarea de la Action los lee.

**Antes de sacar cualquier archivo, ver qué script lo abre**: `grep -rl "<archivo>" *.py` y cruzar esa lista con
los scripts que **corren de verdad** (el lanzador del workflow y `crontab -l`). Sacar un archivo que una tarea lee
rompe la corrida con `FileNotFoundError`, y el síntoma aparece recién en la corrida siguiente del workflow.

**El método que no pierde nada**: `git rm --cached <archivo>` + agregarlo al `.gitignore` — el archivo queda en el
disco local, el bot sigue igual y el repo lo olvida. **Verificar por patrones, no por la lista que uno armó**:
después de sacar, listar el árbol remoto entero (`/git/trees/HEAD?recursive=1`) y filtrar por palabras clave
(`miembros|insiders|auditoria|clasificad`) — se escaparon dos que sólo aparecieron en esa segunda pasada. Y cerrar
disparando el workflow: una corrida en verde **después** del cambio es la prueba de que no se rompió nada.

**El respaldo va a un repo privado, y sin runner**: el estado + el análisis sincronizados por cron cada pocas
horas (copiar una lista explícita de archivos, commit y push con el token del `.env`), dejando afuera lo
regenerable (cachés, volcados). Así el trabajo de semanas tiene copia fuera del equipo y **no corre nada ahí**:
cero minutos de Actions y ningún segundo escritor del mismo estado.

**Y decir la contra antes de proponer el repo privado como corredor**: en un repo privado las Actions **sí**
gastan minutos (2.000/mes gratis) — a ~2,5 min por corrida el techo es una corrida por hora, contra ilimitado en
el público —, y mudar las tareas a Actions **no elimina la máquina encendida** si hay un gateway que sirve
comandos o una vigilancia por WebSocket: eso ningún repo lo reemplaza. Medirlo y decirlo antes de que acepte.

## Entrega (preferencias de este usuario)
- **Separar tajantemente lo hecho de lo pendiente**: primero «ya está, verificado con este número», después «esto
  necesita tu acción» (DNS, cron-job.org, aprobar un push), con los pasos exactos.
- **No anunciar «está online» sin un HTTP 200 medido** y con el dato fresco; si algo quedó sin verificar (el
  certificado, la propagación), decirlo en el mismo mensaje, no después.
- **El código escrito, el build compilado y el sitio publicado son TRES estados distintos, y «¿ya está?» se contesta
  diciendo en cuál está.** Medido con un «¿ya está el gráfico?»: el componente y los datos históricos ya estaban en
  disco, la librería sin instalar, el bundle servido era el viejo y `/api/historial.json` devolvía **404** — para el
  usuario, todavía no estaba. Dar la tabla de los tres con el HTTP medido y qué falta, en vez de un «sí» apoyado en
  el archivo escrito en disco.
- **Cuando pregunte si un pendiente importa** («¿afecta mucho si no lo tuviera?»), responder **con números medidos
  de sus propios datos** (variación del histórico, minutos de atraso), el veredicto en llano primero, y el costo
  real de arreglarlo (tiempo y plata): así decide él. Contestar con «depende» o sólo con opinión no le sirve.
- Español y cierre con **«Conclusión»** que resuma lo esencial. Emojis para ordenar ideas **en el chat**; los
  READMEs y artefactos publicados van **sin emojis** (lo pidió así).
- Cuando el cambio está listo pero el push quedó **sin autorización**, decirlo explícito y pedir el OK en una línea
  («decime *dale* y lo publico»): el archivo escrito en disco no es el sitio publicado.
