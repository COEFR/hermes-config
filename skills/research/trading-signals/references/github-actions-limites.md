# GitHub Actions como host de un bot con cron: límites medidos

Medición en `COEFR/Hermes-Signal-bot` (repo público, cuenta nueva), octubre 2026: 80 corridas.

## 1. El programador de GitHub NO respeta el `cron` pedido
Con `schedule: */15 * * * *` (96 corridas/día esperadas), la cadencia real fue:

| intervalo entre corridas programadas | valor medido |
|---|---|
| mínimo | 0,7 h |
| promedio | ~4 h |
| máximo | 8,9 h |
| corridas reales por día | ~6 (en vez de 96) |

Además: una corrida quedó **`in_progress` 9,5 h** y una corrida **manual (`workflow_dispatch`) quedó `pending` 10+ min** sin arrancar el job. Es despriorización de GitHub (típica en cuentas nuevas o repos sin actividad), no un problema del YAML.

**Cómo medirlo en 30 segundos** (no hace falta token en repos públicos):
```bash
curl -s "https://api.github.com/repos/OWNER/REPO/actions/runs?per_page=25" | python3 -c "
import json,sys,datetime as dt
d=json.load(sys.stdin); runs=sorted(d['workflow_runs'], key=lambda r:r['created_at']); prev=None
for r in runs:
    t=dt.datetime.fromisoformat(r['created_at'].replace('Z','+00:00'))
    print(t.strftime('%d/%m %H:%M'), r['event'], r['status'], r.get('conclusion'), '' if prev is None else f'+{(t-prev).total_seconds()/3600:.1f} h')
    prev=t"
```
Los **pasos** de una corrida también son públicos y dicen en qué paso murió: `GET /repos/O/R/actions/runs/<id>/jobs` (con `steps[]` y su `conclusion`). Los **logs** sí requieren token.

**Separar los DOS retrasos posibles antes de diagnosticar** (decide la solución): cada corrida trae `created_at` (cuándo GitHub la creó) y `run_started_at` (cuándo una máquina la tomó). Si `created_at` se corre respecto del cron pedido → el culpable es el **programador**, y un reloj externo que llame a la API lo arregla (la corrida creada a demanda arranca al instante); si lo que se corre es `run_started_at` → la cola de máquinas. Medido en 29 corridas: `created_at` con huecos de 3-7 h y `run_started_at` **inmediato** (0,0 min de espera, job de 0,1-0,2 min) → la máquina no es el cuello de botella, el programador sí; o sea que el problema tiene arreglo con un reloj externo, no con más infraestructura.
La despriorización **mejora con las semanas de actividad del repo**: re-medir la cadencia más adelante en vez de dar la cifra por eterna (y mientras tanto no prometerla).

## 2. Cuentas con política de «solo acciones propias»
Síntoma: la corrida muere en **startup failure** con
> The actions actions/checkout@v4 and actions/setup-python@v5 are not allowed in OWNER/REPO because all actions must be from a repository owned by OWNER.

Es una restricción de la cuenta/repo (Settings → Actions → General → *Actions permissions*). Se puede pedir que la abran, pero **no hace falta**: el workflow puede ir con **cero acciones de terceros**:
```yaml
steps:
  - name: Traer el repo
    run: |
      git clone --depth 1 "https://x-access-token:${{ github.token }}@github.com/${GITHUB_REPOSITORY}.git" repo
      cd repo && git config user.name "bot" && git config user.email "bot@users.noreply.github.com"
  - name: Dependencias
    run: python3 -m pip install --quiet "pillow>=10,<13"   # ubuntu-latest ya trae Python 3.12
  - name: Ciclo
    working-directory: repo
    run: python3 gh_run.py
  - name: Guardar estado
    working-directory: repo
    run: |
      git add -A
      git diff --cached --quiet || { git commit -qm "estado $(date -u '+%F %H:%M UTC')"; git push; }
```
El `${{ github.token }}` sirve para clonar y para el `push` si el workflow declara `permissions: contents: write`. Los pasos con `working-directory: repo` corren dentro del clon.

## 3. Verificación sin poder leer los secretos
GitHub **nunca devuelve los valores** de los secrets (ni con token: solo los nombres). Para no quedar a ciegas:
- **Chequeo duro** de las claves vacías antes del ciclo → `grep -c '=$' ~/.hermes/.env` (ojo: devuelve exit 1 cuando el conteo es 0, usar `|| true`) y `exit 1` si hay alguna. Así una corrida verde no puede ocultar que falta un secreto.
- **Prueba de entrega manual** (`if: github.event_name == 'workflow_dispatch'`): manda un mensaje real a cada canal de destino; si llega a los dos, los tokens están bien. Se puede probar el mismo script en local (manda de verdad: avisarlo).
- **Modo verificación** para no duplicar mientras el host viejo sigue mandando: `GH_DRY: "1"` en el step del ciclo → corre todo en seco (no envía, no escribe estado); se saca esa línea en el cambio de mando.
- **Estado commiteado de vuelta** en cada corrida = keepalive (esquiva la desactivación a los 60 días sin actividad) y evita reenviar señales ya mandadas. Antes de activar el host nuevo, commitear el estado fresco del host viejo.

## 4. Detalles que muerden
- `on:` se parsea como **`True`** (booleano) al validar el YAML con PyYAML (YAML 1.1) → iterar `w[True]`, no `w['on']`.
- Las corridas programadas **por defecto arrancan recién cuando el workflow está en la rama default** (`main`): un push a `master` deja el cron muerto.
- Un `concurrency` con `cancel-in-progress: false` hace que una corrida colgada **encole** las siguientes — y una corrida `pending` 10+ min se lee como «la cola de máquinas es lenta» cuando la está bloqueando la anterior: mirar el estado de la corrida previa antes de culpar al runner.
- **`conclusion: cancelled` NO es un fallo, y contarlo como fallo produce una alarma falsa.** Con el candado de concurrencia, GitHub cancela la corrida que estaba *esperando* cuando entra la siguiente; en un flujo cuyo ciclo dura más que su intervalo eso pasa en la mayoría de las corridas y **no se pierde nada** (el estado se guarda y la siguiente lo retoma). Al auditar la salud de uno o varios flujos, contar `success` / `cancelled` / `failure` por separado y **reaccionar solo al `failure`**: medido en tres flujos de este equipo, un «4/10 exitosas» era en realidad **0 fallos y 6 cancelaciones** por solapamiento. Un `success/total` bajo se informa como **cadencia mal elegida** (subir el intervalo o poner tope por `timeout-minutes`), nunca como «está fallando». Conteo: `Counter(r['conclusion'] or r['status'] for r in runs)` sobre las últimas 20-30 corridas; `failure` y `timed_out` son los únicos rojos reales.
- Ponerle **`timeout-minutes` al job**: sin tope, un ciclo colgado corre hasta el límite de 6 h de GitHub y el problema se ve como «tarda mucho». Fue el tope (25 min) el que destapó que el ciclo **no termina** desde el runner.
- Con la política de acciones restringida, un `if: failure()` que avise por Telegram con `curl` «funciona» igual con token vacío (el error de HTTP se pierde con `-o /dev/null`) → no confiar en ese aviso para deducir que los secretos están bien.
- **El paso que commitea el resultado necesita `permissions: contents: write`**: con `contents: read` el `git push` final falla y la corrida queda en **rojo después de haber medido todo** — el dato se pierde por el permiso, no por la sonda. Declararlo explícito y comprobar que el paso de commit cerró en verde (una corrida «exitosa» que no commiteó nada se lee como «la sonda no corrió»).
- **El repo con DOS committers ensucia el árbol local**: el runner commitea estado/resultados mientras el host propio corre su cron, así que `git pull --rebase` falla con *«Your index contains uncommitted changes»* aunque no se haya tocado nada. Secuencia que funciona: `git stash` → `git pull --rebase` → `git push` → `git stash pop` (el stash devuelve el estado vivo del bot). Si un rebase anterior quedó a medias, primero `git rebase --abort` (o borrar `.git/rebase-merge`), o el siguiente intento se niega a arrancar. Y un rebase **exige identidad configurada**: un `-c user.email=…` por commit no alcanza → `git config user.email` / `user.name` una vez en el clon.

## 5. La causa raíz medida: el runner es de EE.UU. y Binance le responde 451
La sonda de red «pasó» (30 pedidos en 5 s, ≈150 ms cada uno, corrida en 20 s) y la conclusión que se publicó —«la red del runner está bien, el bloqueo de las IPs del CI queda descartado»— **era falsa**: esos 150 ms eran **respuestas de error rápidas**. El motivo lo dejó escrito el propio runner al intentar dibujar el gráfico del camino de producción:

    gráfico: FALLÓ (HTTPError: HTTP Error 451: )

**HTTP 451 = «no disponible por razones legales»**: `api.binance.com` **no sirve a IPs de EE.UU.**, y los runners de GitHub están ahí. Sin velas no hay gráfico ni señal: el bot queda inhabilitado entero, sin importar la cadencia ni los secretos.
- **Regla de método: una sonda que solo mide tiempos puede dar verde con todo roto.** Registrar siempre **código HTTP y si el cuerpo trae datos** (`len(cuerpo) > 20` y presencia del arreglo esperado), nunca solo la latencia: un bloqueo geográfico responde rápido. Se retractó una vez por anunciar la hipótesis sin medirla y otra por medirla a medias.
- **El síntoma que parecía una falla de la subida (mensaje que llega sin adjunto) era la misma causa**: la sonda pedía velas para dibujar el PNG, con 451 no había PNG, y el envío cae por diseño a «solo texto» cuando el archivo no existe. Antes de diagnosticar una subida rota, comprobar que el archivo **exista** — y que el paso que lo genera haya salido en verde.
- **La geografía del host es criterio de primer orden para un bot que come datos de Binance**, no un detalle de infraestructura: un host estadounidense no recibe respuesta del exchange. El host de producción que hoy funciona está en **Canadá**.
- **Sondear las fuentes alternativas antes de cambiar de arquitectura**: hosts alternativos de Binance (`data-api.binance.vision`, el endpoint público de datos, y `api1`/`api2`/`api4`), Binance US, y exchanges que sí sirven a EE.UU. (Coinbase, Kraken, Bybit, OKX, Bitstamp, Gate, KuCoin, MEXC). Medido **desde el host propio las 15 responden** (sirve de referencia, no de prueba); **desde el runner está pendiente** (`dev/sonda_fuentes.py`, que escribe su resultado en el repo). Si alguna entrega las mismas velas desde EE.UU., GitHub vuelve a ser viable **cambiando solo la URL base**.
Lo que sí quedó medido: el ciclo de este bot (~400 pedidos) tarda ~2 min en un host propio, y las corridas cortadas a los **25 min** por el `timeout-minutes` eran corridas **viejas en modo real** intentando entregar ~14 alertas con imagen a 2 canales.
- **Una sonda de pedidos chicos NO prueba la entrega pesada**: `getMe` / `users/@me` contestan en 5 s y eso no dice nada de la **subida multipart de un PNG**, que va a otro endpoint. Hay que sondear el camino exacto de producción (generar el gráfico con el código real y subirlo) y **mirar el adjunto desde afuera**, contando `attachments` en el canal (`GET /channels/{id}/messages`) contra una corrida del host propio.

**Cómo medirlo desde el runner** (sin depender de leer logs, que necesitan token):
- Un workflow **solo manual** (`on: workflow_dispatch:`, sin `schedule`) que corre una sonda de red aparte del ciclo — no toca estado ni manda alertas, así que se puede correr sin riesgo mientras el host viejo sigue emitiendo.
- La sonda mide N pedidos a cada servicio (velas, ping, y las APIs de aviso) y reporta **media, mínimo, máximo y errores por servicio**, más una estimación del ciclo completo (`pedidos_por_ciclo × latencia`).
- El resultado se manda **fuera de banda** (Telegram/Discord con la Bot API), no se imprime y se espera: los logs de una corrida requieren token, y además el canal de entrega del propio CI es parte de lo que se quiere probar (si el mensaje llega, la salida sirve; si no, eso también es un dato).
- Correr la misma sonda en el host propio da la referencia contra la cual comparar.
- **Sacar el resultado del runner sin token**: el job escribe su resultado en un archivo del repo y lo **commitea** al final (`git add -A; git diff --cached --quiet || { git commit -qm "sonda …"; git push; }`) → se lee desde afuera con `git log`/`git show`; los logs del runner, en cambio, requieren token. Meter en el archivo el nombre del runner, si el gráfico existe y su tamaño, y el resultado de cada subida.
- **Al pasar a modo seco, revisar las corridas ya encoladas**: cada corrida ejecuta el commit del momento en que se **creó**, así que las creadas antes del cambio siguen corriendo el modo viejo (modo real) aunque el YAML ya diga `GH_DRY`. Comparar `head_sha`/`created_at` de cada corrida con el commit del cambio antes de afirmar «no va a enviar nada».

Mientras esa medición no esté hecha, la conclusión es «GitHub sirve para lo liviano y de baja frecuencia (reportes diarios, seguimiento, respaldo), no para el escaneo frecuente de muchos pedidos» — y no se rediseña el bot (menos pares, caché incremental, jobs en paralelo) apostando a que la red andará bien.

## Veredicto
GitHub Actions **no puede correr este bot** mientras pida datos a `api.binance.com`: sus runners están en EE.UU. y Binance les responde **451**. No es un problema de cadencia, ni de secretos, ni de la subida de archivos —secretos, clonado, commit del estado y **alertas de texto** quedaron verificados desde el runner—: es que **no hay velas**. Dos salidas, ninguna cerrada todavía: (1) **una fuente de datos que sirva a IPs de EE.UU.** (sondear `data-api.binance.vision` y los exchanges de EE.UU.; si alguna entrega las mismas velas, se cambia la URL base), o (2) **un host fuera de EE.UU.** La capa gratuita de GCP **cae por el mismo motivo** (sus tres regiones libres son estadounidenses), así que la búsqueda de $0 sigue abierta: el requisito duro no es el tamaño de la máquina, es **su país**.
