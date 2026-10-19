---
name: publicar-proyectos-github
description: "Use when publicando o actualizando proyectos en GitHub."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [github, publicar, repos, secretos, api, backup]
    category: software-development
    related_skills: [github, sitios-estaticos-gratis, hermes-local-ops]
---

# Publicar los proyectos del usuario en GitHub (a granel y sin filtrar secretos)

Cuándo: «publicá mis proyectos en GitHub», «sigamos publicando», o hay que **poner al día** repos que se subieron
una vez. Implementación de referencia: `~/.hermes/data/publicar_proyectos.py` + el
`templates/publicar_proyectos.py` de esta skill. Los proyectos viven en `~/.hermes/data/<proyecto>`; los repos,
en `https://github.com/<usuario>/<repo>`.

## Diagnóstico (hacerlo antes de tocar nada)
1. Inventario local contra remoto: listar `~/.hermes/data/*` y, con el token,
   `GET /user/repos?per_page=100&affiliation=owner`. Ese listado también revela **repos de prueba viejos** del
   usuario (sin descripción, nombres raros) que conviene ofrecerle limpiar.
2. Clave del diagnóstico: **los proyectos suelen NO ser repos git** (`ls -d <proyecto>/.git` → no existe) porque
   se subieron con un git temporal. Sin repo local no hay «actualizar con un push»: hay que **re-publicar**.
3. Decir qué se va a hacer antes de hacerlo: qué repos se tocan, cuáles son **públicos** (ahí el candado es
   crítico) y qué se excluye.

## Procedimiento (por proyecto)
1. `git init -q -b main` si falta `.git`. Esto deja el proyecto **actualizable con un push normal** de acá en
   adelante: es la mejora de fondo, no un detalle.
2. Escribir el `.gitignore` **antes** de `git add`; si ya había índice,
   `git rm -r --cached -q --ignore-unmatch .` para que las reglas nuevas valgan sobre lo ya agregado.
   Base: `.env`, `.env.*`, `*token*`, `.token*`, `logs/`, `*.log`, `__pycache__/`, `node_modules/`, `cache/`,
   `*.tmp`, `*.db`. Material privado: `migracion/`, `*llave*`, `id_rsa*`, `id_ed25519*`, `*.pem`, `*.key`,
   `*.crt`, `*.ppk`. Los datos pesados por proyecto (`.json`, `.csv` de estado) se dejan fuera: el repo lleva código.
3. **Candado de secretos (bloqueante)**: recorrer los archivos que git subiría y **abortar ese proyecto** si alguno
   matchea. Patrones: `ghp_[A-Za-z0-9]{20,}`, `github_pat_…`, `\d{8,12}:AA[A-Za-z0-9_-]{30,}` (Telegram),
   `BEGIN (OPENSSH|RSA|EC|PGP) PRIVATE KEY`, y clave embebida
   `(?i)(api[_-]?key|secret|passwd|password|token)\s*[:=]\s*['\"]([A-Za-z0-9+/_-]{24,})['\"]`.
   Que el valor tenga **forma de clave** (charset + 24 o más) evita el falso positivo típico:
   `if l.startswith("HELIUS_API_KEY=")` es una lectura correcta del `.env`, no un secreto.
4. `git commit` + `git push https://x-access-token:<token>@github.com/<usuario>/<repo>.git main:main -f`
   (el token se lee de `~/.hermes/.env`, nunca vive dentro del script). Si en `.env` hay varios tokens
   (`GITHUB_TOKEN`, `GITHUB_TOKEN_DOLAR`, …), probar cada uno con `GET /user` y usar el que devuelva 200: uno vencido
devuelve 401 y cualquier escritura falla sin explicar por qué. Decir al usuario cuál está muerto.
5. Con un repo nuevo, re-apuntar el remoto a la URL limpia (`git remote set-url origin
   https://github.com/<usuario>/<repo>.git`) para que el token no quede en `.git/config`.
6. Verificar repo por repo: `GET /repos/<owner>/<repo>/commits?per_page=1` (mensaje y hora del último commit) y
   `GET /repos/<owner>/<repo>/git/trees/HEAD?recursive=1` (conteo de archivos + nombres peligrosos).

## Trampas (cada una costó una ronda)
1. **GitHub rechaza el push si contiene secretos**: `remote: error: GH013 … Push cannot contain secrets`, con el
   **archivo y la línea** señalados (y un link para desbloquearlo, que NO se usa). No es un fallo del script: algo
   se coló al índice. Excluir ese archivo y reintentar — el candado del paso 3 existe para no llegar nunca a esto.
2. **El historial local se reenvía entero**: si un commit anterior ya tiene la llave, `git rm --cached` + un commit
   nuevo **no alcanza** (el objeto viejo sigue viajando y vuelve a ser bloqueado). Hay que **borrar `.git` y
   re-inicializar** para que el historial nazca limpio.
3. **El grep por nombre de archivo no alcanza**: las llaves del usuario pueden tener nombres locales
   (`migracion/llave_github` no matchea `id_rsa`, `*.key` ni `token*`). Escanear **por nombre y por contenido**.
4. **Revisar el repo público antes de declararlo limpio**: bajar los archivos sospechosos y grepearlos
   (`curl -s https://raw.githubusercontent.com/<owner>/<repo>/main/<ruta> | grep -icE 'ghp_|…'`). Medido: los docs
   de infra en un repo público estaban sin claves aunque el nombre asuste (`manda_secrets.py`, `GUIA_GCP.md`).
5. **Un token hallado en un commit viejo puede estar muerto**: probarlo antes de alarmar
   (`curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer <t>" https://api.github.com/user` → 401 =
   ya no sirve) y contarlo tal cual: cambia por completo el mensaje al usuario.
6. **Alcance del token expuesto**: `curl -sD - -o /dev/null -H "Authorization: Bearer <t>" https://api.github.com/user`
   devuelve `x-oauth-scopes`. Un clásico con todo tildado (`delete_repo`, `admin:org`, `repo`, `workflow`) es la
   llave maestra de la cuenta: decirlo **con la lista concreta**, no en abstracto.
7. **El candado aborta el proyecto, no el script**: seguir con los demás y al final listar qué quedó sin subir.
8. **`POST /user/repos` con `"private": true` por defecto**; público sólo cuando el sitio lo exige (GitHub Pages
   gratis necesita repo público).
9. **Un pipe después del push te miente.** `git push … 2>&1 | tail -3 && echo "push OK"` imprime OK aunque el push
   haya sido rechazado: `&&` evalúa el exit code del último comando del pipe (`tail`), no el de `git`. Correr el push
   sin pipe (o con `set -o pipefail`) y mirar la salida de git; la prueba final es `GET /repos/<o>/<r>/commits` con
   el mensaje nuevo.
10. **Repo con un bot que commitea estado cada minuto.** El clon local queda miles de commits atrás y el push se
   rechaza por non-fast-forward aunque los archivos que tocás no hayan cambiado. Secuencia que funciona:
   `git fetch <url> main` → `git -c rebase.autoStash=true rebase FETCH_HEAD` → `git push`; repetir el ciclo 2-3 veces
   porque el bot puede volver a ganar la carrera en segundos. Antes de rebasear, comprobar que tu base sea ancestro
   (`git merge-base --is-ancestor HEAD~1 FETCH_HEAD`) y que los archivos editados no difieran de los del remoto
   (`git diff HEAD~1:<f> FETCH_HEAD:<f>`): si difieren, rehacer el cambio sobre la versión remota, no rebasear a
   ciegas. El autostash puede dejar `UU` en archivos de estado (`*_estado.json`): resolverlos con el estado vivo y
   **comprobar que sigan siendo JSON válido** (`python3 -c "import json;json.load(open(f))"`) — un archivo con
   `<<<<<<<` rompe el bot en la pasada siguiente. No cerrar la tarea con `UU` ni con un stash abierto.
   Si el `UU` cae en un archivo **append-only** (CSV de mediciones, log de eventos) no elijas un lado: sacá las dos
   versiones con `git show :2:<f>` y `git show :3:<f>`, unilas, deduplicá por la clave de tiempo y ordená. Quedarse
   con «ours» o «theirs» borra o duplica filas que el bot y vos escribieron en paralelo.
11. **La caché de `raw.githubusercontent.com` y de GitHub Pages sirve la versión anterior** varios minutos después de
   un push (`?v=<timestamp>` no la rompe en Pages). Un archivo viejo ahí **no** prueba que el push falló: comprobar
   con `git fetch` + `git show origin/main:<ruta>` y, para el sitio, `GET /repos/<o>/<r>/pages/builds/latest`
   (status `built` y el commit esperado) antes de mirar el dominio. Declarar «publicado» sólo cuando el árbol del
   remoto tiene el contenido nuevo.
12. **Un push disparado en medio de un rebase sube el commit ANTERIOR y la salida dice que salió bien.** Cuando el
   rebase se detiene por un conflicto, `HEAD` queda *detached* sobre el commit del bot (`git status -sb` muestra
   `(no branch, rebasing main)` con el archivo en `UU`), y el `git push` del bucle empuja ese árbol: la salida trae
   `main -> main` / `HEAD -> main`, el bucle imprime «push OK» y tus archivos **no** están en el remoto. El chequeo
   por SHA tampoco lo detecta: `git rebase` reescribe el commit, así que `merge-base --is-ancestor <sha-viejo>` da NO
   aunque el contenido haya subido. Antes de empujar, `git status -sb` tiene que estar limpio de `rebasing`/`UU`;
   cerrá con `git add <archivo resuelto> && GIT_EDITOR=true git rebase --continue` y recién ahí pusheá. Verificá
   **por contenido**, no por sha: `git fetch <url> main && git ls-tree -r --name-only FETCH_HEAD | grep -E
   '<archivo nuevo>'` y `git log --oneline FETCH_HEAD | grep '<mensaje del commit>'` — si aparecen, subió.
13. **Con un bot que commitea cada minuto, el commit propio lleva sólo código y build.** Los archivos que el bot
   regenera (`data/*.csv`, `docs/api/*.json`, históricos) cambian entre el `git add` y el `push`: si van adentro, cada
   rebase choca en ellos y se pierde la carrera una y otra vez. Commitear la fuente y el artefacto compilado
   (`docs/assets`, `docs/index.html`) y dejar los datos al bot. Cuando el rebase ya se enredó, la secuencia que cierra
   sin ambigüedad es: `git rebase --abort` → `git branch -f respaldo <mi-sha>` → `git fetch <url> main` →
   `git reset --hard FETCH_HEAD` → `git cherry-pick <mi-sha>` → en el conflicto del archivo de datos
   `git checkout --ours <archivo> && git add <archivo>` (queda la versión del bot) → `push` → verificar por árbol.
   **Un `rebase` puede imprimir «Successfully rebased» sin haber rebasado**: si `git log --oneline -2` muestra que el
   padre sigue siendo tu commit viejo en vez del commit del remoto, no rebaseó — y el push siguiente va a rebotar con
   la pista de `fast-forwards`. Comprobarlo antes de pushear, no después. **Y el chequeo de ascendencia sólo vale
   DESPUÉS del push y de un `git fetch` nuevo**: el cherry-pick reescribe el commit, así que antes de empujar `HEAD`
   está por delante del remoto y `git merge-base --is-ancestor HEAD FETCH_HEAD` devuelve NO aunque todo haya salido
   bien; después del push la misma orden da SI. Como `reset --hard` deja tu commit sólo alcanzable por el nombre, el
   `git branch -f respaldo <sha>` del paso anterior no es opcional: sin esa rama el sha se pierde y no hay qué
   cherry-pickear.

## Si el usuario minimiza el riesgo («solo yo tengo acceso»)
No insistir ni sermonear. **Verificar lo que NO depende de su acceso** y contarlo en hechos: (a) qué repos son
públicos y si tienen claves en el árbol o en la historia; (b) si el token hallado está vivo (401 vs 200) y qué
alcance tiene; (c) dónde quedó la clave (archivo local, `.env` con `600`, o un repo). Dato que suele cambiarle la
decisión: en un servidor de Discord los **bots también leen el historial**. Después, una línea de «si querés lo
cerramos en 2 minutos» y basta: la decisión es suya.

## Embellecer un repo, paso por paso (repo por repo)
Pedido típico: «vamos paso por paso, repo por repo», «primero decime cuántos tenemos», «embellecé todo el repo,
empezá por <proyecto>». Ritmo que el usuario pide, en este orden:
1. **Primero el número, después el detalle.** Contestar cuántos repos hay separando **nuestros** (los proyectos de
   `~/.hermes/data`) de los **ajenos** (repos de prueba viejos: vacíos, sin descripción) y marcando cuáles son
   **públicos**. Sin ese conteo no arranca.
2. **Un repo por vuelta, en orden.** Primero los **públicos** (ahí el candado, la limpieza y la ficha importan de
   verdad), después los privados; los vacíos/ajenos al final y preguntando antes de borrar. Al cerrar cada repo,
   una línea de «sigo con <el próximo>»: el orden lo marca él.
3. **Checklist fijo por repo**, anunciado de antemano para que sepa qué esperar: visibilidad · README · descripción
   · contenido (claves, datos privados, basura) · orden de carpetas.
4. **Entregables de «embellecer»** (recetas exactas en `references/embellecer-repo.md`): banner SVG propio ·
   **capturas reales del sitio en vivo** (no maquetas) comprimidas · README reescrito con banner, badges, enlaces,
   capturas, **diagrama de arquitectura en SVG (no ASCII)**, **bloque ```diff de métricas**, **los resultados medidos
   ARRIBA de todo y como gráfico de barras** (no como tabla de texto: receta en `sitios-estaticos-gratis` →
   `references/imagenes-repo.md`), cómo funciona, API, cómo
   compilar, estructura, pendientes y créditos de la fuente · la **ficha** del repo por API (descripción, sitio,
   etiquetas) · **limpieza de duplicados** con su `.gitignore` · y si el proyecto compila, un `build.sh` de **un solo
   comando**. El README tiene que **verse** técnico y no sólo serlo: prosa sola vuelve como «no se ve nada técnico»
   (§4).
5. **Cerrar con el antes/después medido** (MB de duplicados eliminados, peso de las capturas, conteo de archivos)
   más el commit y los HTTP 200 de los archivos nuevos. Nada de «quedó mejor» sin número.
6. **Verificar que se VEA, no sólo que exista** (`references/embellecer-repo.md` §8): imagen presente en el HTML de
   la página del repo, tablas renderizadas y jerga con olor a IA = 0. Un archivo publicado con 200 puede no estar
   renderizando: el síntoma típico que reporta él es «la imagen no sale en la página del repo».

## Que el proyecto corra solo en GitHub Actions (sin VPS)

Pedido típico: «¿podés hacer que <proyecto> corra en GitHub Actions?», sobre un bot que hoy depende del crontab de
este equipo. Es la jugada que lo saca de la máquina — y la razón por la que conviene el repo **público**: los
minutos de Actions son ilimitados y gratis.

1. **Los secretos son Secrets del repo, no archivos**: `PUT /repos/{o}/{r}/actions/secrets/{NOMBRE}` con el valor
   cifrado (sealed box de libsodium con la clave de `GET /repos/{o}/{r}/actions/secrets/public-key`). El workflow
   los pasa por `env:` o los escribe en `~/.hermes/.env` antes de correr; el repo nunca los lleva adentro.
2. **El estado del bot se versiona en el repo**, o cada corrida arranca de cero y el bot olvida qué avisó (detalle
   en `sitios-estaticos-gratis`). El guardado va con `pull --rebase --autostash` y reintentos, nunca
   `commit && push` a secas. **Vale para todo archivo que escriba un paso, no sólo el estado**: si un script anota
   una medición en un CSV y otro la convierte en el JSON que consume el sitio, el workflow tiene que correr los dos
   pasos y listar **ambos** archivos en `git add`. Lo que no está en el `git add` se queda en el runner efímero: el
   dato se mide, el precio se publica, y el histórico o el gráfico queda congelado sin que nada falle. Síntoma
   exacto: la parte «viva» se actualiza y la derivada no. Al repararlo, rescatar lo perdido desde otro artefacto
   versionado (p. ej. el histórico de precios que sí se commiteaba) y deduplicar por la última marca de tiempo, en
   vez de rellenar el hueco con un precio plano.
3. **El cron de GitHub es impuntual y su grilla es de 5 minutos**: no se puede pedir «cada 3 minutos». Lo que
   funciona es un **lanzador que decide por reloj**: una corrida cada 5 min que mira la hora y ejecuta la tarea cuya
   franja corresponde (radar, patrulla, cosecha…). Así la cadencia se expresa en turnos de esa grilla. Decirle al
   usuario la cadencia **efectiva**, no la soñada.
4. **Verificación real**: `POST /repos/{o}/{r}/actions/workflows/<archivo>/dispatches` con `{"ref":"main"}` (204 =
   aceptó · 404 = nombre de archivo mal · 422 = falta el cuerpo) y después
   `GET /repos/{o}/{r}/actions/runs?per_page=1` para leer `status` y `conclusion` de la corrida (la clave del JSON es **`workflow_runs`**, no `runs`: parsear `runs` devuelve vacío sin error). Un 204 no prueba
   que la tarea corrió.
5. **Al reescribir la historia de un repo con bot activo, pausarlo primero**
   (`PUT .../workflows/<archivo>/disable`, `/enable` al terminar): si no, el bot empuja en medio de la reescritura y
   choca.
6. **Una corrida rechazada durante esa pausa no rompe nada**: el lanzador decide por reloj y la franja siguiente
   la recupera. Decirlo así en vez de alarmar.
7. **El tope de tiempo por tarea que pone el lanzador tiene que caber en la ventana del workflow, y cuando no cabe
   el fallo es intermitente.** Firma: la corrida falla a una duración sospechosamente redonda («Failed in 9 minutes
   and 10 seconds» = el tope propio de 540 s más el arranque) y falla unas veces sí y otras no, según cuánto trabajo
   encontró esa pasada. El `timeout-minutes` del job es otra cosa: el que corta es el tope del lanzador, que marca la
   tarea como fallida y sale con código ≠ 0. Lo que corresponde es **medir la tarea más lenta y poner el tope con
   margen dentro de la ventana del job** (p. ej. 1200 s en un job de 20 min): el tope existe para que una tarea
   colgada no se lleve la corrida entera, **no** para cortar una tarea que legítimamente tarda.
8. **El estado puede vivir en un repo privado, y entonces el workflow lo baja y lo sube en la misma corrida.**
   Cuando el estado no puede ir al repo público, se hace un repo privado que sólo lleva el estado y el workflow hace
   el viaje completo: `actions/checkout` con `repository: <o>/<repo-privado>`, `token: ${{ secrets.<PAT> }}` y
   `path: estado/`; copiar esos archivos a donde el código los busca; correr; copiar de vuelta y commitear y
   pushear **en ese repo**. Hace falta un **PAT**: el `GITHUB_TOKEN` del workflow no alcanza a otro repositorio, y
   va como Secret del repo. Verificar el viaje de ida **y de vuelta** (que el repo privado tenga un commit nuevo con
   la hora de la corrida, no sólo que el paso de arranque diga que encontró archivos). En ese caso, sacar el
   `permissions: contents: write` del workflow público: ya no escribe ahí.
9. **Antes de optimizar una pasada lenta, medirla por etapas; y desconfiar de la etapa que parece obvia.** El reloj
   de la pasada lo fija la **unidad más lenta** de un `ThreadPoolExecutor.map` (el mapa espera a todos), así que
   paralelizar 8 s dentro de una pasada de 300 s no cambia nada — y paralelizar la etapa que *parecía* culpable
   (los envíos, con su descarga de imagen por aviso) dejó la pasada igual de lenta. Profilar primero con
   `time.time()` por etapa, después cortar por el mayor. Y una pasada lenta hoy **va a** pasarse del tope el día que
   encuentre más trabajo: el tope se pone sobre el peor caso medido, no sobre el promedio.
10. **Los comandos del bot también se hospedan en Actions, y sólo los de texto.** Antes de prometer continuidad,
   separar por **vía de entrega**, no por «el bot»: los comandos de **texto** (`!rsi`, `!ath`, …) son un script
   común que habla con la Bot API con el token del bot → una Action cada 5 min los atiende sin gateway y sin máquina
   encendida (y el «estado de lo ya contestado» se versiona en el repo, o repite las respuestas en cada pasada);
   los **slash** los entrega la plataforma al gateway, así que para independizarlos hace falta el modo *HTTP
   interactions* —un endpoint serverless (Vercel, Cloudflare, Deno) y portar el handler a ese runtime—. Los
   secretos que necesita el workflow son el token del bot y la **lista de canales** (con los canales, el comando
   sabe de qué canal viene el pedido): cargarla también como Secret, no sólo el token.
11. **Pausar el proyecto entero (Actions + VPS) y verificarlo.** `PUT /repos/{o}/{r}/actions/workflows/<archivo>/disable`
   (204) y comprobar `state: disabled_manually` en `GET .../actions/workflows`; un `dispatches` sobre un workflow
   deshabilitado responde **422** («Cannot trigger a 'workflow_dispatch' on a disabled workflow»), así que el reloj
   externo tampoco puede despertarlo. GitHub **tarda en aplicarlo** (~20 min medidos): siguen entrando corridas
   encoladas o ya en vuelo; no cerrar el apagado hasta ver 10+ minutos sin corridas nuevas (mirar el `created_at` de
   la última). En el VPS, pausar en la misma pasada sus líneas de cron (prefijo `#PAUSADO`) y matar los procesos de
   larga vida que el cron no cubre (p. ej. un vigía WebSocket, junto con su `.pidfile`), confirmando con `pgrep` que
   no queda ninguno. Dejar escritas las dos vías de reanudación (`/enable` + `crontab <respaldo>`) y decir en la
   entrega qué deja de funcionar mientras esté pausado (avisos, comandos, datos que se actualizaban solos).
12. **Cerrar la migración apagando el cron local en la misma sesión.** Si las líneas del VPS siguen activas, el mismo
   ciclo corre dos veces con estados separados: doble gasto de API, avisos duplicados y, en una máquina de 4 GB, el
   pico de RAM que tumba el gateway. Revisar con `crontab -l` y `pgrep -af '<script>'`, dejar las líneas pausadas con
   prefijo `#PAUSADO` (no borradas), guardar una copia del crontab anterior para revertir y comprobar que **toda ruta
   referenciada exista** (`crontab -l | grep -oE '/home/[^ ]+\.(py|sh)' | while read f; do [ -f "$f" ] || echo "FALTA $f"; done`):
   una línea que apunta a un script borrado falla en silencio cada intervalo, porque cron no tiene MAILTO configurado.
   **Pausar sólo cuando el reloj externo ya dio señal, y verificarlo en la misma pasada con tres medidas**: el
   espaciado de las corridas nuevas (`/actions/runs`), la frescura del artefacto que publica (p. ej. la marca de
   tiempo del JSON en el dominio, ≤ 5 min) y los commits del bot entrando con la hora en curso. Para esperar un
   ciclo, dormir **menos** que el timeout del comando (`sleep 300` con `timeout 560`): un `sleep` igual al timeout
   se lo come entero y la verificación nunca corre, y el error aparece como «timed out» del tool, no como fallo del
   reloj.

## Entrega (preferencias de este usuario)
- **Separar tajantemente lo hecho de lo pendiente**, con los números medidos (archivos y hora de commit por repo),
  y cerrar con **«Conclusión»**; español y emojis para ordenar.
- **El hallazgo de seguridad va primero**, aunque haya salido de un paso secundario.
- Ofrecerle las decisiones de limpieza (borrar carpetas de infra del repo público, repos de prueba viejos) en vez
  de hacerlas por cuenta propia.
- **Los artefactos publicados van sin emojis y sin jerga con olor a IA** («bajo el capó», «caja negra»,
  «serverless», «trazabilidad», «pipeline», «motor de detección»): los mandó borrar explícitamente después de haber
  pedido un tono «más técnico». Cuando pide **más técnico** quiere detalle concreto aportado (umbrales, cifras, cómo
  se calcula, casos límite, qué hace en cada paso), no adjetivos ni anglicismos de marketing. Detalle en
  `references/embellecer-repo.md` §4.
- **No inventar un banner nuevo por repo**: hay un estilo aprobado; cualquier otro diseño se propone antes de
  dibujarlo. Si rechaza uno, se borra el archivo y **todas** sus referencias, se sube un commit que lo saque y se le
  ofrece **sin banner** para los repos que siguen (reescribir la historia para borrar el commit no se hace: riesgo
  alto por ganancia nula).
- Guardar el script en `~/.hermes/data/publicar_proyectos.py` y correrlo por proyecto (`python3
  publicar_proyectos.py <carpeta>`), no todo junto a ciegas: así se ve el candado proyecto por proyecto.
