# Verificación de los sistemas (memecoins + bot RSI) — recorrido por componente

Pedido típico: «verificá el correcto funcionamiento de todos los sistemas». Tener la línea en el
crontab no prueba nada: recorrer en este orden y reportar ✅/⚠️ por componente, sin inflar.

## 1. Infraestructura base
- `crontab -l | grep -v '^#'` → todas las líneas presentes (una línea comentada puede ser a propósito:
el parte diario del radar quedó así por pedido del usuario).
- `ps -eo pid,etime,pcpu,args | grep python3` → qué procesos viven y desde cuándo.
- `systemctl is-active cron` → activo.

## 2. Procesos con PID propio
`ps -p $(cat <proyecto>/vigilante.pid)`. El keepalive del cron lo revive, pero el PID prueba que ese
proceso **es** el vigilante: `pgrep -f <script>` lanzado desde un shell se encuentra a sí mismo.

## 3. Cada componente, por su marca en el log (no por impresión)
Grep con la marca real de cada uno y mirar la ÚLTIMA ocurrencia:
- radar: `vigilando: N tokens`
- tracker: `pasada lista`
- auditor de direcciones: `sin direcciones nuevas` / `direcciones nuevas`
- detector de ráfagas: `envío: ` — y sobre todo **`fallo el embed` / `429`**: si aparecen, la entrega se
  está cayendo aunque el script salga con exit 0.
- cosecha de cohortes: `lanzamientos en la cosecha: N` y `armando cohortes con N`
- patrulla de cohortes: `cohortes encontrados: N`
- registro de resultados: `muestras nuevas`
- consumo: `gasto de hoy` (el acumulado del ciclo lo lleva el script de consumo)

## 4. Entrega real: leer el canal por API
`GET /channels/{id}/messages?limit=100` (más de 100 = HTTP 400) y confirmar que el mensaje está. El 200
del POST no prueba que el usuario lo vea, y sin canal propio los avisos caen por fallback a otro canal.

## 5. El bot de RSI no vive en este equipo
El ciclo corre en GitHub Actions y lo dispara un reloj externo (cron-job.org); el runner manda las
señales por su cuenta. Lo verificable local es el **vigilante**: que su log diga
`última corrida: #N … completed/success` y `todo bien: el reloj externo está disparando`, y que su cron
corra cada 10 min. El **log local de señales puede estar viejo por diseño** (el escáner no corre en esta
máquina): no reportarlo como falla. Detalle del sistema: skill `trading-signals`.

## 6. Trampas que hacen reportar un falso «caído»
- **Hora**: el host está en **UTC-4** y los scripts del proyecto loguean en **UTC**. Un log cuya última
  línea dice `12:25` con el reloj local en 08:30 está **fresco**. Comparar siempre con `date` antes de
  afirmar que un sistema lleva horas sin correr.
- **Estado vacío ≠ roto**: un JSON de cohortes vacío con pocos lanzamientos cosechados es lo esperado.
  Dar el número y el ritmo medido, no un diagnóstico de falla. Con el umbral de **2 coincidencias** los
  dúos salen ~**1 cada 17 lanzamientos** (medido), así que **cientos** de lanzamientos con 0 cohortes sí
  es para revisar la lectura — y sin re-cosecha el grafo queda a la mitad.
- **`envío: {'discord': False}` o un 429 en el minuto invalida** la verificación del canal, aunque el
  proceso haya terminado bien.
- Cerrar el parte con la **tabla de créditos por componente** y cuántos días quedan al ritmo actual.

## 7. Verificar un arreglo: probar el camino completo, no que compile

`py_compile` no prueba nada de esto (son fallas de runtime o de entrega). Por cada arreglo, correr el
camino entero y **leer el log del componente**, no sólo su salida:

- **Envío**: mandar un aviso de prueba al canal real, releer el canal por API y **borrar la prueba**
  (`DELETE /channels/{id}/messages/{mid}`) para no dejar basura: confirma que llegó el embed **y** el
  mensaje suelto con el contrato.
- **Freno compartido de ritmo**: disparar N envíos seguidos y contar cuántos pasan; el esperado es el
  tope por minuto y el resto salteado **sin perderse del registro**.
- **Ritmo real de una cosecha**: contar los candidatos **nuevos** que suma una pasada, no los que pide la
  configuración (`--cosechar 20` puede sumar 1 si la lista ya está consumida). Reportar el medido.
- **«No manda nada»**: antes de tocar umbrales, verificar **de qué lado se está mirando** y que las
  primeras pasadas no sean sólo línea base (la primera lectura de una wallet o de una lista no avisa).
- Tras un `patch` grande, sacar el código muerto que quede (un bloque `if False:` con el camino viejo
  compila y se ve bien, pero alguien lo va a leer como vivo).
