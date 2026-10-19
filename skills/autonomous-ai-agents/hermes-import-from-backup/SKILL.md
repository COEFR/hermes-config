---
name: hermes-import-from-backup
description: "Use when exporting or importing Hermes backups between machines."
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, migration, backup, archives, secrets-hygiene, memory, restore]
    related_skills: [hermes-agent-state, hermes-tool-availability]
---

# Importing a user's backups from a previous machine

A user migrating an old install (VPS, laptop, another agent) drops archives and files into chat. The job
is: catalogue them, triage what is dangerous, land the durable material where it will survive, extract the
facts into memory, and restore nothing with side effects until asked.

## Procedure

1. **Enumerate the attachment directory, not the transcript.** Transport notices only describe the newest
   files; earlier uploads are still on disk. List `$HERMES_HOME/cache/documents/` with sizes and `file`
   output before deciding anything.
2. **Verify before re-importing.** Users re-send the same archive. `sha256sum` it and `diff` its extracted
   contents against what was already imported, then say "identical — nothing to do" with the evidence. Never
   duplicate memory entries or files because the same bytes arrived twice.
3. **List before extracting, extract into scratch.** `tar -tzf <a>` / python `zipfile.namelist()` first; then
   extract under `$HERMES_HOME/cache/scratch/<name>/`, never in place, never into a live config path.
4. **Triage secrets BEFORE reading or quoting content.** Dump only key NAMES (`grep -o -E '^[A-Z0-9_]+=' .env`),
   note certificates and private keys, and report names plus a rotation recommendation. Never print secret
   values, never copy recovered credentials into the live config, and never silently adopt an old bot token.
   State plainly which secrets travelled over an unencrypted-to-the-platform channel (chat attachments) and
   that they should be rotated.
5. **Land durable artifacts under `$HERMES_HOME/data/<project>/`.** The document cache is prunable and its
   filenames are opaque hashes; a project directory is the stable home for source, builds, CVs, config
   samples.
6. **Write `<project>/NOTAS.md` for the technical detail** — endpoints, ports, service layout, deploy steps,
   caveats, what is missing — and keep the memory entry to one line that points at it. Memory is injected
   every turn; it is not the place for a spec sheet.
7. **Read for real, then report.** An inventory alone is not worth the tokens: name at least one concrete
   finding per artifact (a bug, a dead code path, a stale absolute path, a credential in a file that ships).
8. **Restore nothing with side effects without an explicit yes.** Cron jobs, deploy scripts, posting bots,
   mail senders and credential use all get proposed, not enabled. Catalogue + plan is the default outcome.

## Pitfalls

- **Restrict greps to source globs.** Bundled/minified output (`dist/`, `assets/*.js`, `*.min.js`) matches
  every pattern and can return hundreds of KB in one result. Exclude build directories by path.
- Absolute paths inside restored scripts point at the OLD host (`/root/...`, another user's home). Re-point
  them before any attempt to run, and say so in the report.
- Archives beyond the platform attachment cap (Telegram bots: ~20 MB) silently fail to transfer. Ask the
  user to split the archive or move it out of band instead of retrying the upload.
- Old scripts against live APIs: tokens and app credentials typically expire (page/API tokens, app
  passwords). Flag verification as a required step before reactivating any automation.
- Migrating memory files means re-writing them through the store, not copying them over the live files
  (see `hermes-agent-state`); consolidate during import instead of importing every historical entry.

## El otro lado: armar el respaldo para mudar ESTE equipo

Cuando el usuario va a perder la máquina (VPS que se apaga, equipo que cambia) y pide que no se pierda nada, el
respaldo es un **tar.gz de `$HERMES_HOME`** en un **repo privado**: la máquina nueva se restaura
descomprimiendo en `~` y arrancando Hermes. Con esto la restauración es completa:

`skills/ plugins/ hooks/ memories/ config.yaml SOUL.md auth.json state.db data/`

- **Excluir lo regenerable y lo pesado**: cachés, `venv/`, `node_modules/`, `__pycache__/`, el checkout del
  propio repo de estado, y los JSON grandes que ya están versionados en otro lado. Medido: sin exclusiones el
  archivo daba **107 MB**, y **GitHub rechaza cualquier archivo de más de 100 MB** — el push falla sin decir
  por qué. Apuntar a ~60 MB.
- **Credenciales: afuera por defecto, y decir el costo de cada opción.** `auth.json` trae la **clave del
  proveedor del modelo** y `.env` las de los bots (Helius, Discord, Telegram, GitHub). Dejarlos afuera obliga a
  dos minutos en la máquina nueva (iniciar sesión y recrear el `.env`); incluirlos deja la restauración en un
  paso pero mete las llaves maestras en el repo. Preguntar antes, y si acepta, advertir en el mismo mensaje que
  la privacidad del repo pasa a ser lo único que cubre esas claves.
- **Verificar el contenido por nombres, no de memoria**: `tar tzf` y contar por directorio, y confirmar
  explícitamente si `auth.json` y `.env` están o no adentro. Una credencial que se cuela sin querer es el error
  más caro de esta tarea (medido: el `auth.json` entró en el primer armado y hubo que rehacerlo).
- El repo de respaldo suele tener **su propio cron empujando estado** cada pocas horas: aplica la misma
  disciplina de git que en cualquier repo con bot — `git config user.name/user.email` en ese repo antes de
  rebasar, commitear lo del bot antes de rebasar, `rm -rf .git/rebase-merge` si quedó colgado, y el `pull`
  con el token explícito si el `origin` está sin credencial. Ver `sitios-estaticos-gratis`, Trampa 10.

## Reporting shape for this user

Long technical reports go out in Spanish, with emojis as section markers (📦 findings, ⚠️ risks,
💾 actions taken), square evidence for anything verified, and one closing paragraph titled
**Conclusión**. Admit and repair your own mistakes in the report rather than burying them. Never change
model/provider settings — or price-affecting limits such as memory caps — without asking first.
