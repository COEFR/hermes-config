---
name: deepseek-cost-tuning
description: "Estirar el saldo de DeepSeek API: caché, salida, pico."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [deepseek, costos, tokens, cache, reasoning, hermes]
    related_skills: [hermes-local-ops, trading-signals]
---

# Estirar el saldo de DeepSeek (medido, no de memoria)

Orden de palancas por impacto real, con los precios oficiales de `deepseek-flash` (doc de DeepSeek):
entrada cacheada **$0,003/1M** off-peak · entrada sin caché **$0,15/1M** · salida **$0,60/1M** (en horas pico, 2×).
Un token de salida cuesta **200×** uno cacheado; uno sin caché, **50×**. Consecuencia: **el saldo se lo
comen la salida y los fallos de caché, no el contexto**.

## Horas pico (2× precio) — gratis de evitar
**01:00–04:00 y 06:00–10:00 UTC, lunes a viernes** (Bolivia UTC-4: 21:00–00:00 y 02:00–06:00).
Todo lo demás y los fines de semana completos son off-peak. Mover el trabajo pesado fuera de esas ventanas
es un 50% de descuento sin tocar nada más.

## La caché es por prefijo exacto (byte a byte)
- DeepSeek compara el **prefijo exacto**; cualquier cambio arriba del final invalida todo lo que sigue.
- **Rompe la caché**: cambiar de modelo en la misma sesión (las claves son por modelo), cambiar el set de
  herramientas/skills a mitad de sesión, un timestamp o id aleatorio en el prefijo, y **comprimir el contexto**
  (en Hermes la compresión es *la única* ruptura sancionada — por eso las skills/herramientas nuevas se aplican
  en la sesión siguiente, no en la actual).
- **Mantiene la caché**: prefijo estable turno a turno, contexto estático primero y lo variable al final,
  sesiones largas mejor que muchas cortas (más prefijo reutilizado), y el API oficial directo (los revendedores
  tipo OpenRouter pierden la caché por los headers).
- Medir siempre con el campo `cache_hit_tokens`, no estimar.

## La salida es el token caro: bajar el razonamiento
- En Hermes el esfuerzo de razonamiento es un nivel: `none, minimal, low, medium, high, xhigh, max, ultra`
  (`--reasoning LEVEL` por corrida, o `agent.reasoning_effort` / `agent.reasoning_overrides` por modelo).
- En DeepSeek el modo pensante viene **encendido por defecto** y el reasoning se factura como **salida**: los
  reportes de la comunidad van de «5000 tokens de razonamiento por respuesta» a «duplica la longitud de la
  respuesta». Para tareas mecánicas o conversación, bajar el nivel es el ahorro más grande y más rápido.
- Contraindicación honesta: el razonamiento es lo que hace al modelo bueno en problemas difíciles; medir el
  costo por **tarea terminada**, no por token — un modelo barato que se va por las ramas sale más caro.

## Trabajo auxiliar con el modelo barato (Hermes)
El trabajo de fondo (compresión de contexto, títulos, curación de skills, visión) se puede fijar por tarea bajo
`auxiliary:` en `config.yaml` (`auxiliary.compression.*`, con `fallback_chain`). Fijar el modelo flash
para comprimir es más barato y más rápido; usar un modelo distinto para comprimir además garantiza fallo de
caché en esa llamada.

## Las herramientas y las skills: recortar el prefijo fijo
- En Hermes, **cada tool y cada descripción de skill viaja en cada llamada** (medido en este equipo: el system
  prompt más largo es de **~21.400 caracteres ≈ 5.355 tokens**).
- El catálogo de plugins de Hermes ya trae los instrumentos que la comunidad recomienda:
  `tool-slimmer` (recorta el esquema de herramientas por llamada), `skill-router` (carga solo las skills
  relevantes en vez de listarlas todas), `tokenwatch` (mide el uso y **congela** al llegar a un umbral),
  `reasoning-switch` (cambia el nivel de razonamiento desde la barra de estado).
- **Advertencia medida**: si el prefijo ya se lee a precio de caché, recortarlo ahorra centavos; el recorte
  importa cuando se arranca muchas sesiones nuevas (prefijo frío) o el prefijo es enorme. Priorizarlo después
  de la salida y de los fallos de caché.

## Estructura de almacenamiento (para no re-enviar contexto)
- Guardar decisiones y estado en **archivos o skills** al momento de tomarlas, no en el historial: es lo que
  sobrevive a la compresión y evita re-explicar (el patrón `NOTAS.md` de los proyectos de este equipo).
- Para el estado volátil, dejarlo en el **último** mensaje (o en el propio razonamiento del modelo) en vez de
  reescribir el principio del contexto: reescribir arriba es pagar un prefijo entero a precio de fallo.

## Automatizaciones: scripts, nunca agente
Cualquier tarea periódica que se pueda escribir como script (alertas, informes, vigilancia) debe serlo: es
**0 tokens**. Un cron del agente o un subagente arranca con caché fría y paga salida. Este equipo ya lo aplica
(el bot de señales manda alertas por Bot API con 0 tokens de LLM).

## Cómo reportar esto
Antes de proponer recortes, **medir** en `state.db` (`sessions`: `input_tokens`, `cache_read_tokens`,
`output_tokens`, `estimated_cost_usd`) y calcular el reparto real del gasto entre caché / fallos / salida.
Citar los números del usuario, no promedios de internet.
