---
name: channel-watcher-bots
description: "Use when un bot con cron vigila un canal y responde."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [discord, telegram, bot, cron, sondeo, estado, idempotencia]
    related_skills: [trading-signals, hermes-local-ops]
---

# Bots que vigilan un canal y responden

Cuándo aplica: un script que cada N minutos lee los mensajes nuevos de un canal con la Bot API, hace algo con ellos
(los contesta, los humaniza, los publica) y anota lo que ya procesó — sin gateway de por medio, y con o sin LLM.

## El ciclo, en orden

1. **Leer pocos y de nuevo a viejo**: `GET /channels/{id}/messages?limit=3` y ordenar **descendente** por timestamp.
   Con `limit` alto, el mensaje recién pegado queda último en una cola larga y el bot contesta lo anterior: el usuario
   lo lee como alucinación. Cola corta, o descartar todo lo anterior a la última corrida.
2. **Filtrar**: fuera los ids ya vistos, los mensajes vacíos y los de bots.
3. **Procesar de nuevo a viejo** y **enviar** la respuesta de cada uno.
4. **Anotar el id recién después de que el envío salió bien**, y guardar el archivo de vistos al final de la corrida.
5. **Candado** (`fcntl.flock` sobre un archivo de lock) alrededor de todo el ciclo.
6. **Verificar releyendo el canal** (`GET /channels/{id}/messages`), nunca con el 200 del POST.

## Las cuatro reglas que cuestan un bug cada una

- **Marcar «visto» SOLO después del envío exitoso.** Si el id se anota antes y el POST falla con un 403/429
  transitorio, ese mensaje **no se responde nunca más**: el usuario ve que pegó un texto y el bot quedó mudo, y no
  hay reintento porque su id ya está en el estado. El estado se anota por envío confirmado, no por lectura.
- **Procesar de nuevo a viejo** (regla 1): es la diferencia entre contestar lo que acaba de escribir y contestarle
  lo de diez minutos antes.
- **Candado, o respuestas duplicadas**: el cron y una corrida manual del mismo script se solapan y cada proceso
  contesta lo mismo por su cuenta. El lock se toma al principio del ciclo y se suelta al final, no por mensaje.
- **Ignorar los mensajes de bots** (`author.bot`) — sabiendo que **una prueba que pega el texto con el token del bot
  deja el mensaje como `bot: true` y el watcher lo saltea en silencio**. Para poder probar hace falta un flag de
  forzado (`<BOT>_FORZAR=1`) que **se apaga después de la prueba**; sin él, «no me contestó» es un falso síntoma de
  la prueba, no un bug.

## Diagnóstico: «le pegué un texto y no hizo nada»

Si el log muestra que el script corrió y leyó el canal, el problema no es el disparador. Revisar en este orden:
1. el id ya estaba en el archivo de vistos (una corrida previa lo marcó sin contestar — ver la regla del envío);
2. el autor del mensaje es un bot (típico cuando la prueba la hizo el propio bot);
3. el filtro de contenido lo descartó (muy corto, sin el prefijo de comando, ya procesado);
4. el flag de forzado quedó apagado.
Borrar el archivo de vistos es el «reprocesá todo» y sirve como prueba barata de que el camino funciona — pero **no**
es el arreglo: si hace falta para que ande, el bug es la regla del envío.

## Formato de la respuesta en el canal

- **El resultado útil va PRIMERO y en texto plano**, fuera de bloques de código: el usuario lo copia de un toque.
  El diagnóstico o el detalle va en **una sola línea** al final, en cursiva. No rodear el resultado de un informe.
- **Discord corta el `content` en 2000 caracteres**: recortar a ~1990 antes de enviar y caer al canal de respaldo si
  la API falla.
- Un emisor nuevo que no manda `User-Agent` propio recibe **403** de Discord, y el síntoma parece un permiso faltante.

## Si el watcher contesta con el modelo

El caso «con LLM» se resuelve llamando al agente en modo **one-shot** (una entrada, una respuesta, sin sesión). Dos
cuidados que costaron una ronda cada uno:

- **El flag del modo one-shot cambia entre versiones**: copiar de un ejemplo viejo uno que ya no existe deja el
  script mudo, y encima el síntoma se lee como «el bot no responde», no como error de invocación. Confirmarlo con
  `hermes --help` antes de escribirlo en el cron, en vez de confiar en la memoria.
- **El gasto de tokens se contiene antes de la llamada, no después**: los filtros, el dedupe y la decisión de
  responder se resuelven con reglas (Python puro) y recién entonces se llama al modelo. Un watcher que consulta al
  modelo para decidir *si* hay que responder paga en cada mensaje del canal, incluidos los que ya contestó.

## Estado: qué guardar

Solo **ids y timestamps** de lo procesado (nunca el contenido: es dato del usuario y crece sin control). Si el bot
lleva memoria propia (contadores, últimos resultados), va en su archivo de estado — y **commiteada de vuelta** si el
corredor es GitHub Actions, o se pierde en cada corrida.
