# Restaurar el agente en una VPS nueva

Todo lo necesario para revivir a Hermes con su memoria y sus skills. Los secretos **no** están
acá: en `.env.example` queda la lista de claves que hay que volver a cargar.

## 1. Instalar Hermes

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash   # instalador oficial
```

## 2. Traer este respaldo

```bash
git clone https://github.com/COEFR/hermes-config.git ~/hermes-config
```

## 3. Copiar memoria, skills, scripts y configuración

```bash
mkdir -p ~/.hermes/{memories,skills,scripts,cron}
cp -r ~/hermes-config/memories/*        ~/.hermes/memories/
cp -r ~/hermes-config/skills/*          ~/.hermes/skills/
cp -r ~/hermes-config/scripts/*         ~/.hermes/scripts/
cp    ~/hermes-config/config/config.yaml ~/.hermes/config.yaml
cp    ~/hermes-config/cron/jobs.json    ~/.hermes/cron/jobs.json
chmod +x ~/.hermes/scripts/*.sh
```

## 4. Cargar los secretos

```bash
cp ~/hermes-config/.env.example ~/.hermes/.env.example   # lista de claves
# crear ~/.hermes/.env y completar los valores (tokens de GitHub, Discord, Telegram,
# Helius, claves de proveedores, etc.)
chmod 600 ~/.hermes/.env
```

## 5. Servicio del gateway

```bash
hermes gateway install --user
systemctl --user enable --now hermes-gateway.service
loginctl enable-linger "$USER"
hermes gateway status
```

## 6. Crontab del sistema

```bash
crontab ~/hermes-config/config/crontab.txt
crontab -l
```

Revisar que las rutas del crontab existan en la máquina nueva (`~/.hermes/...`) y que los
scripts referenciados estén en su lugar.

## 7. Proyectos (aparte)

Los proyectos viven en sus propios repos y se clonan en `~/.hermes/data/<proyecto>`:

- `COEFR/dolarbolivia` — sitio + Action de tasas y muestreo.
- `COEFR/Hermes-Signal-bot` — bot de señales (corre en GitHub Actions).
- `COEFR/Argos-Memecoin-sniper` — proyecto de memecoins (pausado).
- Los privados: `argos-datos`, `edgar-reporte-empleo`, `boliviatoy-facebook`, `zeroscript`,
  `ai-vtuber-tiktok`, `usdt-boo`.

## 8. Verificar

```bash
hermes doctor
hermes gateway status
ls ~/.hermes/skills | wc -l          # tienen que estar las 76
cat ~/.hermes/memories/MEMORY.md | head
```

Si el gateway responde en Telegram/Discord y las skills aparecen, la restauración está completa.

## Qué se respalda y con qué frecuencia

`scripts/sync_hermes_config.sh` corre por cron cada 6 horas y sube: memoria, skills completas,
scripts, `config.yaml`, `cron/jobs.json`, el crontab del sistema y la lista de claves del `.env`.
No incluye secretos, sesiones ni logs.
