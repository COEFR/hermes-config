---
name: hermes-agent-state
description: "Use when writing agent memory or reading session history."
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, memory, user-profile, sessions, history, sqlite, state]
    related_skills: [hermes-tool-availability, hermes-agent]
---

# Hermes Agent State — memory and history

Operating the agent's own persistent state: `MEMORY.md` / `USER.md`, and the session store behind
questions like "can you see the earlier chat?".

## Enable memory before writing anything (two independent switches)

- Toolset: `hermes tools enable memory [--platform <platform>]`.
- Config flags: `hermes config set memory.memory_enabled true` and
  `hermes config set memory.user_profile_enabled true`.

A toolset-only change leaves the tool present but refusing every write ("writes are disabled in memory
config"); a flags-only change leaves the tool out of the schema. Verify with a real write, or
`check_memory_requirements()` from the repo venv.

## Write through the store, never by hand

The `memory` tool is session-scoped: a conversation that started before the toolset was enabled has no
`memory` in its schema, and the write must not wait for `/new`. Use the store API directly:

```bash
cd "$HERMES_HOME/hermes-agent" && source venv/bin/activate && HERMES_HOME="$HERMES_HOME" python - <<'PY'
from tools.memory_tool import load_on_disk_store
s = load_on_disk_store()
print(s.apply_batch("memory", [{"action": "add", "content": "..."}]))
PY
```

- Targets: `memory` = environment/project facts about this machine and its work; `user` = who the user
  is and their standing preferences. One compact, fact-carrying sentence per entry.
- Never write `MEMORY.md` / `USER.md` with a file tool: the store's drift guard then refuses later writes
  (silent data-loss protection) and the file has to be repaired by hand.

## Pitfalls that cost data

- **`replace` swaps the WHOLE entry, not a substring inside it.** `replace(target, "<one phrase from the
  entry>", "<that phrase plus more>")` deletes everything else in the entry — it survives as just the new
  string. To extend an entry, the new content must be the complete rewritten entry.
- After any `replace`, read the file back and reconcile the entry against the reported `usage`: a drop the
  edit cannot explain means an entry was truncated.
- Budgets are checked on the FINAL result and a batch is atomic: over-limit refuses every operation in it.
  Consolidate (remove verbose entries + add new ones) inside ONE `apply_batch` — never a write followed by
  a second attempt after trimming.
- Limits: `memory.memory_char_limit` / `memory.user_char_limit` (defaults 2200 / 1375 chars). Contents are
  injected into the system prompt on every turn, so raising a cap costs tokens per request. Prefer folding
  technical detail into a project file (`$HERMES_HOME/data/<project>/NOTAS.md`) and keeping a one-line
  pointer entry in memory.
- Store durable facts only: not task progress, not "we were in the middle of X".

## History questions ("can you see the previous chat?")

- The agent's own history is `$HERMES_HOME/state.db` — SQLite, tables `sessions` and `messages`
  (`messages.session_id` → `sessions.id`). Read column names from `pragma table_info(<table>)` instead of
  assuming them, and query with python3's `sqlite3` module (the standalone CLI binary is frequently absent).
- Platform history the bot never received is unreachable: the Telegram Bot API exposes no history endpoint
  (`getUpdates` returns only unconfirmed updates), so messages sent before the bot was connected are gone.
  The clean recovery path is a **Telegram Desktop chat export (JSON)** handed over as a file; index it once
  it arrives.
- **Cost and token questions** ("how much did this cost?", "does anything here burn tokens?"): the same
  `sessions` table carries `source`, `started_at`, `input_tokens`, `output_tokens`, `cache_read_tokens` and
  `estimated_cost_usd` — sum them per session for the real figure instead of estimating. Automation that
  spends tokens shows up as a **`source` that is not a human conversation**, or as sessions appearing on a
  schedule; if every session maps to a chat or a one-off CLI run, nothing burns tokens while idle. Report
  the split (conversation vs. automation) and the measured total, never a bare "no cost".
- Answer with evidence from the store (first message id/text, counts, timestamps) rather than recollection,
  and state plainly which window is and is not covered.
- **Cuando el usuario dice que ya te mandó algo** ("revisá el historial, te lo pasé"), buscá en `messages` por
  un fragmento distintivo del dato antes de responder que no lo tenés: la coincidencia confirma que existe
  (y de quién es). Los secretos vuelven **enmascarados** en la salida de las herramientas, así que se pueden
  comparar por igualdad, medir el largo y ver los extremos, pero **no repetir en el chat**: si el usuario
  necesita el valor, devolvéselo por otra vía (un archivo adjunto) o decíle de qué mensaje suyo copiarlo.

## References

- `references/memory-store.md` — file layout, delimiter, capacity/usage accounting, operation shapes and
  the exact error texts the store returns.
