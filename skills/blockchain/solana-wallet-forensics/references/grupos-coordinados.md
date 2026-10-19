# Grupos coordinados de compra (cohortes): detección y medición

## Detección: vigilar las WALLETS, no los tokens

- La señal es "miembros del mismo grupo comprando el mismo token". Se detecta leyendo las **transacciones de las wallets** del grupo (getSignaturesForAddress + parseo de pre/post balances), NO buscando miembros del grupo dentro de una lista de tokens: los grupos compran tokens que no están en esas listas (medido: 4 de 6 wallets operando y 0 avisos por esa vía).
- Un aviso válido exige compras **juntas en el tiempo** (≤15 min) y token **fresco** (≤90 min). Un token de 4 h ya no es "el grupo entrando", es tarde.
- Escalar el mínimo de miembros: 2 alcanzan para un dúo; en un grupo de ≥5 hacen falta ≥3, si no todo dispara.
- Topes: máx 3 avisos por pasada y **6 por hora**, con dedupe por TOKEN cada 6 h (no por combinación de wallets). Sin topes la lista se vuelve ilegible: medido 8 por pasada y 48 en una hora.
- Las compras se acumulan en un **buffer**; re-leer los lanzamientos recientes a los ~30 min multiplicó los compradores capturados (8→17 en un mismo token) y destapó los primeros cohortes.

## Evaluar "el mejor grupo": medir, no suponer

- Comparar el mcap **actual** (DexScreener) contra el mcap al momento de detectarlos, token por token, para los tokens donde entraron ≥2 miembros.
- **El tamaño del grupo no predice**: el grupo de 9 wallets con 31,9 SOL dio mediana 0,69x, mientras dos dúos chicos dieron 2,29x y 1,75x. El mcap del token tampoco separó (uno de $13k hizo 3,75x; otros de $8-9k se hundieron). Lo que separa es QUIÉN compra.
- Honestidad con la muestra: 2 tokens por dúo es nada, y los tokens sin precio quedan fuera del cálculo (sesgo de supervivencia que **favorece** a los grupos).
- **El puntaje tiene que pesar QUIÉN compra, no el tamaño del token**: bonus por wallets de grupos ya trackeados (+1,5 con una, +3,0 con dos o más), castigo por red de insiders de RugCheck (−1,5 por wallet conectada), por concentración (top 10 >50% → −2,5) y por creador serial (−0,75 con ≥3 lanzamientos vistos, −1,5 con ≥5), bonus por RugCheck limpio y descarte si el token ya está marcado como rug. Con esos pesos la **misma ráfaga** pasó de 0/10 a 9/10 según el token, y a 10/10 con una wallet de grupo dentro.
- **No se avisa cada compra ni cada combinación**: además de los topes, el aviso exige compras juntas en el tiempo y token fresco, y el dedupe es por token. La señal se mide después (registro + muestreo) para saber si el grupo vale.

## Rankear grupos: por REGISTRO medido, no por tamaño

Método: por cada grupo, tomar los tokens donde entraron ≥2 miembros (con `mcap_cosecha`) y calcular el múltiplo
**del pico si el token está en el registro de calls** (lo justo con el grupo) o **el actual** si no. Con menos de 3
entradas medidas no hay veredicto — decirlo, no rellenar el ranking.

Medido sobre 31 grupos / 524 lanzamientos cosechados / 142 wallets:

- **El grupo más grande es el peor por registro**: 61 wallets, 114 entradas, mediana **0,49x** (con un 11,5x
  adentro) → es una **lotería**, no una ventaja. Si se sigue, seguir al **origen** (el que entra primero), no al grupo.
- **Los de mejor mediana estaban planos (1,07x)**: compran tokens de **$6-28 M** de FDV (USDF, SARP, VSOF) → sin
  lugar para un múltiplo. Un registro plano por tokens gigantes **no es un grupo rentable**.
- **Los únicos con aciertos reales entran a micro-caps frescas** ($7-30 k): 20 % de ≥1,5x (mejor 1,72x) — muestra
  chica, pero es el único perfil con de dónde subir.
- **18 de 31 grupos tenían 1-2 entradas** → no se juzgan.
- **Los avisos filtrados miden mejor que las calls generales** (medido en dos cortes del registro: 25-29 % de
  ≥1,5x contra 18-20 % de las calls generales) → el filtro de grupo (2+ wallets en ≤15 min, token fresco) **suma**.
  Regla de método: medir siempre **el subconjunto que el filtro deja pasar contra el total** — es lo que valida
  el filtro, en vez de discutirlo.

**Un grupo grande puede ser una CADENA, no un grupo coordinado.** La detección por componentes conexas une por
transitividad (A compró con B y B con C → A, B y C quedan en el mismo «grupo»): un blob de decenas de wallets
—medido: uno de 61— sale de **parejas encadenadas**, no de 61 socios. Marcar los blobs grandes como **«red
Difusa»** y no presentarlos como un grupo que actúa junto; los que valen son los chicos y repetidores. El blob **sigue
absorbiendo** (medido: 61 → 101 wallets en un día) y en un aviso de 4 compradores se lee como un error del sistema:
además de marcarlos, **topar la fusión** (no unir dos componentes si el resultado pasa de ~25-40 wallets: las wallets
nuevas forman su propio grupo).

**Grupos solapados no son evidencia independiente.** Dos grupos que comparten los mismos tokens (medido: 3 de 4 en
común) son **la misma jugada contada dos veces**: antes de decir «N grupos con buen registro», cruzar sus sets de
tokens y contar cada token una vez.

**Diseño que sale de esto**: rankear por registro y **silenciar los grupos de registro plano/negativo** (no los
borra: se siguen midiendo), y dejar sonando los chicos de micro-cap. El tamaño del grupo **no** es criterio.

## Clasificar los grupos en TIERS (lo que decide qué avisa y dónde)

El tier sale del **registro medido**, nunca del tamaño ni de la corazonada, y se recalcula solo (cada ~30 min,
con caché de precios con TTL ~30 min para no gastar cupo). El tier **viaja pegado al grupo**: de él dependen el
canal del aviso, el cupo y el filtro.

| Tier | Criterio (medido) | Qué hace |
|---|---|---|
| 🟢 SEGUIR | ≥2 entradas · mediana ≥1,05x · ≥15 % ≥1,5x · compra FDV <$50k | avisa en su canal |
| 🟠 LOTERÍA | mediana <1,0x pero ≥10 % de ≥1,5x o mejor ≥3x (el golpe adentro) | avisa **marcado** (que no se lea como promedio) |
| 🟡 OBSERVAR | 1-2 entradas: no hay veredicto todavía | avisa, sin peso en el análisis |
| 🔴 DESCARTAR | compra FDV >$500k (estructuralmente plano) · o n≥2 con mediana <0,5x y <10 % de aciertos · granjas de bots | avisa sólo en el canal de descarte: no se pierde y se sigue midiendo |

- **El FDV que compran es el discriminador más fuerte, y va antes de la mediana**: los que compran tokens
grandes no tienen de dónde subir (medido: 4 grupos entrando a **$14 M** con mediana 1,09x y **0 %** de ≥1,5x;
otros en $75-475 k, en 0,00-0,03x).
- **Reparto real medido sobre 35 grupos: 2 🟢 · 3 🟠 · 17 🟡 · 13 🔴.** Casi dos tercios sin muestra: decirlo,
no rellenar un ranking.
- **El tier tiene que moverse solo** con cada entrada nueva; no congelar la clasificación del primer día.

### Los avisos van al canal del tier, con cupo POR canal

- Un **canal por nivel** bajo la categoría del sistema (🟢 · 🟠 · 🟡+🔴 juntos, cuando el usuario pide «junta
observar con descartar»). El canal se resuelve por el tier del grupo que dispara el aviso, con caída al canal
general si falta el ID en `.env`.
- **Sin tier, al general — no a un canal de nivel «por defecto».** Mandar los avisos sin nivel al canal de
  observar es lo que hizo que los avisos del grupo grande (🟠) aparecieran en el canal de observar: el general es
  ruido tolerable, un canal de nivel equivocado es información falsa. Al general van también las **noticias**:
  cada grupo **nuevo** se anuncia al detectarlo (nombre, tamaño, quién entra primero y que queda en 🟡 hasta juntar
  registro), sembrando antes la lista de firmas ya conocidas para no anunciar treinta grupos de golpe.
- **El estado compartido entre pasadas se escribe con temporal por PID.** Con el `.tmp` fijo, la patrulla (`*/3`)
  y la cosecha (`*/15`) se pisaron: una renombró el temporal y la otra murió con `FileNotFoundError` **antes de
  clasificar**, así que los grupos quedaron reconstruidos **sin nivel** y sus avisos sin canal (llegaron al
  general). Usar `<archivo>.<pid>.tmp` + reintentos, aislar la clasificación **por grupo** (try/except) y, al
  reconstruir, **arrastrar el tier/nombre** del armado anterior para la misma firma de wallets: entre reconstruir
  y reclasificar nadie queda sin nivel. Comprobar tras la pasada que **todos** los grupos tienen tier.
- **El tope de avisos por hora es POR CANAL, no global.** Con tope global el nivel ruidoso agota el cupo de
  todos (medido: los 🟡 consumían los avisos de la hora y los 🟢 no llegaban a salir).
- **El canal lo decide la WALLET que entra, no el tier del grupo.** Las wallets copiables viven dentro de los grupos
  grandes (🟠): ruteando por tier, sus entradas se iban al canal de lotería y el canal 🟢 quedaba **vacío con las
  mejores wallets operando** (medido: 0 avisos en 15 min mientras copiables entraban a tokens frescos). Si entra **una**
  copiable, el aviso va al canal 🟢 **sin importar el tier del grupo** — y basta 1, no 3.
- **Priorizar un canal = sacar los avisos de los otros, no repartir el cupo.** Cuando el usuario pide «dale prioridad
  a #seguir», lo que rinde es **evaluar ese canal primero** en la pasada y **dejar de avisar** (pero seguir midiendo)
  en los canales de ruido, no subir un cupo y bajar otro.
- **El cupo por hora se dispara junto y después se calla.** Medido: 3 avisos en el primer minuto y el canal mudo los 59
  restantes. Poner el tope **con intervalo mínimo** (goteo: 1 cada N min; el excedente salteado pero registrado) en vez
  de un balde por hora, y **no consumir cupo/dedupe con los avisos que se descartan** — si se escribe la clave de
  dedupe antes del `continue`, los descartados gastan el cupo de los que sí importan.
- **El aviso dice CUÁNTAS wallets entraron, no el tamaño del grupo.** El bug que reportó el usuario («todas dicen 100
  wallets y 4 de ellas compraron») salió de poner el tamaño del grupo en la línea del hecho: arriba «**100 wallets**
  del mismo grupo entraron al mismo token» y abajo «**4** de ellos pusieron 3,95 SOL». La cantidad que ACTUÓ va
  primero; el contenedor, entre paréntesis y como contexto («4 wallets del grupo (100 en total) entraron»). Vale para
  cualquier aviso: **contenedor ≠ hecho**.
- Clavear el estado de dedupe/cupo como **`canal|mint`**; al migrar desde la clave `mint` pelada, **seguir
chequeando el `mint` solo** para no re-avisar tokens ya avisados (cambio de formato sin perder el dedupe).
- Que los 🟡 y 🔴 **también avisen, pero sólo en su canal**: se ve todo y el canal de los buenos queda limpio
(es una decisión de legibilidad, no de calidad — el tier sigue visible en los motivos del aviso).

## Notas de operación de este sistema (Discord)

- Los scripts que avisan necesitan un **control de ritmo compartido por archivo**: cada corrida del cron es un proceso nuevo, así que un contador en memoria no frena nada y el servidor contesta 429 y el aviso se pierde. ~15 mensajes/min por canal; el excedente se saltea pero queda registrado.
- Cada sistema debe tener su propio formato de embed (autor, color, encabezado): si el aviso de grupos reusa el embed de ráfagas, se lee como si el otro sistema se hubiera filtrado.
- **Bot de tracking de terceros (Rick, leaderboards ATH, id `1081815963990761542`) — diagnosticar en este orden, no adivinando:**
  1. **¿Escaneó algo alguna vez?** Listar TODOS los canales del servidor por API (`GET /guilds/{id}/channels` → `GET /channels/{id}/messages`) y filtrar los mensajes de ese bot. Si nunca publicó un **scan**, el leaderboard está vacío por definición: el comando responde "No tokens found" sobre una lista sin tokens.
  2. **¿Quién pega los contratos?** Contar los mensajes con dirección por **autor**. Si todos salen de **tu propio bot**, ahí está la causa raíz: **los bots ignoran los mensajes de otros bots** (anti-bucle), así que un contrato publicado por un bot **nunca se escanea**. El token lo tiene que pegar un **humano**.
  3. **Rol y permisos**: el bot suele exigir un **color exacto** en su rol más alto (Rick: `#B0F646`; sin el color solo funcionan los slash commands y el escaneo automático queda apagado) y Ver canal / Enviar mensajes / **Leer historial de mensajes**. Se verifica por API (`GET /guilds/{id}/roles` → campo `color`, y los `permission_overwrites` de cada canal); ojo que el permiso puede venir del `@everyone` y no del rol, así que mirar la efectiva.
  4. Cierre: pegar un contrato **a mano** y buscar el scan con la insignia `🏆 usuario @ XXk ⋅ Nx` en el pie — sin insignia el token no entró al ranking (filtros de calidad del bot).
  5. **No se puede integrar ni disparar por API**: Discord **prohíbe que un bot use los comandos de otra
     aplicación** (y el bot además ignora mensajes de bots), así que su leaderboard no se alimenta ni se consulta
     desde acá. No prometer «lo comparo con Rick»: el puente es **manual** (un comando propio escupe los
     contratos y los pega un humano) y la comparación de calidad se hace con **tabla propia replicando su
     métrica** (FDV del aviso → pico), no con su `/ga`. Receta de la tabla y de los comandos:
     `references/calls-y-avisos.md`.

## Cuánto mueve de verdad un grupo: medir contra un CONTROL

- **El efecto medido «a lo bruto» se infla por contaminación aritmética.** Si en el resultado se cuentan las compras
  de los propios miembros, el «lift» sale ~2× (paper fundacional, mismo método de detección que usamos: +130,9 %
  crudo → +63,9 % excluyendo a la cohorte → **+16,1 % de compradores** tras emparejar por calidad del lanzamiento, y
  el SOL que entra **indistinguible de cero**). Regla: medir **sin las compras del grupo** en el resultado — lo que
  ve un seguidor es el precio **después** de que el grupo entró, no su propia compra.
- **Sin control emparejado no se sabe si la señal vale.** Comparar los tokens avisados contra **tokens frescos al
  azar de la misma hora/edad/mcap**. Si los avisos no le ganan a ese control, el registro es ruido del mercado, no
  ventaja del sistema. Cuidado con el placebo emparejado por *actividad*: da lift falso positivo y no sirve de
  línea base.
- **No siempre hay seguidores**: en una minoría grande de lanzamientos (7 % en el paper) la cohorte compra y **nadie
  más entra** en los primeros 30 min → un grupo no crea el movimiento. Decirlo cuando se venda el sistema.

## Puntaje por WALLET: se asigna DESPUÉS de medir, y el aviso lo lleva encima

Flujo (así lo pidió el usuario): detectar → avisar → esperar y medir cómo le fue a la compra → **recién entonces puntuar**.

- **Un puntaje sin resultado medido no existe**: con 1-2 entradas la wallet va como **«sin registro»** (nunca una nota
  inventada); el corte para mostrarla es **3 entradas medidas** y para confiar en ella **5+**.
- **El criterio es el PnL de COPIA, no la mediana** (corregido midiendo). PnL de copia = sumar `múltiplo − 1` con $1 por
  entrada, y al lado las **ganadoras cazadas** (entradas que llegaron a ≥1,5x). La mediana **descarta justo a los que
  cazan los monstruos**: entran a todo, así que su mediana es mala (medido: 0,42-0,67x en las tres de mejor PnL)
  mientras su cola es la que paga. Medido sobre 120 wallets: **33 con PnL positivo (+146) contra 87 negativas (−168)**.
  La mediana sirve para descartar grupos estructuralmente planos, **no** para rankear wallets copiables. Tier por PnL
  de copia: 🟢 COPIABLE / 🟡 OJO / 🔴 NUNCA, y el aviso lo lleva encima:
  `🟢<prefijo>… +23,5 (10 ganadoras/42 entradas)`.
- **El que más opera no es el mejor** (34 entradas con mediana 1,00x contra 3 con 2,67x): el volumen solo no puntúa, y
  la nota **va siempre con el tamaño de la muestra al lado**.
- El aviso de grupo lleva el puntaje de los que entran: `👤 quiénes entran: … 7/10 (6 med.) · … sin registro`. La
  decisión llega con el dato en el momento, no después; la nota se recalcula con cada cosecha (puede subir o bajar).
- Se puntúa con lo **medido por el sistema** (las compras detectadas y seguidas), no con la auditoría histórica de la
  wallet: son dos preguntas distintas (¿sus compras de estos días resultaron? contra ¿ganó plata en su vida?).
  Decirlo explícito al entregar, porque el nombre «puntaje» invita a confundirlas.

## El puntaje se SATURA: el canal de «las mejores» se corta por PERCENTIL del día, no por umbral

- Un puntaje absoluto 0-10 es una **suma con tope**: con tres wallets copiables ya llega a 10/10 y deja de
distinguir —medido: un token **sin liquidez real** (en la curva, $0 de par) entró al canal premium con 10/10, y la
pregunta del usuario fue «¿por qué pusiste ese?»—. El corte del canal va por **percentil del día** (top ~10 % de las
calls ya registradas) y el aviso lo dice: `🏆 CALIDAD 9,5/10 · top 4 % del día`.
- **El percentil necesita historial**: al instalar el filtro, rellenar (`nota_calidad`) de las calls ya registradas en
el historial; y con menos de ~10 calls del día, usar de respaldo el umbral absoluto (si no, el canal queda vacío las
primeras horas). **Ojo con el techo del día**: el percentil se calcula contra las calls registradas de ESE día, así
que un día flaco hace pasar cualquier cosa — mirar el n antes de confiar en el corte.
- **Lo que respalda el filtro (medido sobre ~210 calls con resultado)**: tramo 0-4 → 5 % de ≥1,5x · 4-6 → 6 % ·
≥9 → **41 %** (16 % llegan a 3x); y el ingrediente que más pesa, medido solo: **una wallet copiable adentro → 35 % de
aciertos contra 8 %** sin ella. Un filtro así se defiende con esa tabla, no con la intuición.
- **Un 10/10 que sale de sumar no es «lo mejor», es «sumó todo»**: al justificar por qué entró una call, decir QUÉ
wallets entraron y con cuánto, no sólo la nota — y si la suma llega al tope, decirlo.
