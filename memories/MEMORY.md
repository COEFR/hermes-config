Este equipo: skills locales con los procedimientos → `hermes-local-ops` (entorno, modelo, gateway), `hermes-tool-availability` (tools que faltan), `hermes-agent-state` (memoria/historial), `hermes-import-from-backup` (importar respaldos). Leerlas antes de tocar config.
§
Proyectos de Dylan en ~/.hermes/data/<proyecto>/NOTAS.md (leerla antes de trabajar): dolarbolivia (sitio React + API), edgar (reporte de empleo), facebook (BoliviaToys), zeroscript, aivtuber.
§
Avisos sin tokens de LLM: los scripts Python pueden mandarse mensajes con la Bot API de Telegram (token y chat ya en la config del gateway) y agendarse con el crontab del sistema, que sobrevive reinicios.
§
repo público COEFR/Hermes-Signal-bot (antes COEFR/hermes: el nombre viejo redirige)
§
Memecoins/pump.fun: analizador de tokens + tracker de wallets en ~/.hermes/data/memecoins (NOTAS.md, skill memecoins-pumpfun), cron cada 3 min. Solo avisa, no opera.
§
`uv` vive en /home/ubuntu/.hermes/bin/uv y NO está en el PATH de los shells en segundo plano (los comandos con background=true fallan con "Command 'uv' not found"): llamarlo por ruta completa.
§
Push/API a GitHub: `GITHUB_TOKEN` del .env está vencido (401); el que responde es `GITHUB_TOKEN_DOLAR` (usuario COEFR).
§
Relojes fuera de la VPS (19-oct): bot de señales y DólarBolivia (tasas 5 min, muestreo 1 min) se disparan desde cron-job.org; sus líneas de crontab quedaron #PAUSADO. Canal ✨-rsi-goty = divergencias con volumen ≥1,0× y RSI ≥55.