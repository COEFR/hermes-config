---
name: hermes-tool-availability
description: "Use when a Hermes tool is missing or won't enable."
version: 1.0.0
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, configuration, toolsets, tools, gateway, telegram, troubleshooting, verification]
    related_skills: [hermes-agent]
---

# Hermes Tool Availability

When the user says "you don't have tool X" or "activate X", the answer is almost never that Hermes
lacks the tool. It is registered and gated by config. Work the ladder below in order, and finish with
a live call — not with a config read.

For Hermes features beyond tool exposure, the authoritative index is
https://hermes-agent.nousresearch.com/docs/llms.txt (fetch with `curl` when web tools are off).

## 1. A tool is exposed only if a toolset names it

- `toolsets.py::TOOLSETS` maps toolset key → tool names; `_HERMES_CORE_TOOLS` is the bundle platform
  base toolsets inherit. A tool registered in `tools/*.py` with no toolset entry is invisible.
- `hermes tools list --platform <p>` prints ✓/✗ per toolset for that platform. Use it — the bare
  `hermes tools` UI and `hermes tools --summary` both abort with "requires an interactive terminal"
  from an agent/piped shell.
- The two knobs that decide the final list: `hermes config get agent.disabled_toolsets` and
  `hermes config get platform_toolsets.<platform>`.

## 2. The subtraction pitfall that costs an hour

Disabled toolsets are a **strict end-of-pipeline subtraction**, and a tool can belong to more than
one toolset. Leaving a *secondary* member disabled strips the tool even when its primary toolset is
enabled: `web_search` is named by both `web` and `search`, so with `search` still listed in
`agent.disabled_toolsets`, enabling `web` yields `web_extract` **without** `web_search`.

Before concluding a tool is unavailable, grep every toolset that names it
(`grep -n '"<tool_name>"' toolsets.py`) and clear all of them. Symptom to recognise: a session that
has the sibling tool but not the one the user wants.

## 3. Turn toolsets on/off

- `hermes tools enable <toolset> [<toolset> ...] [--platform <p>]` (default platform: `cli`);
  `disable` mirrors it. Run it once **per platform**: a Telegram/Discord session resolves
  `platform_toolsets.<platform>`, not the CLI list.
- Not every name in `agent.disabled_toolsets` is settable: legacy/config-only keys (e.g. `search`)
  are rejected with `✗ Unknown toolset '<name>'` because only `CONFIGURABLE_TOOLSETS` + plugin
  toolsets are accepted. Rewrite the list instead:
  `hermes config set agent.disabled_toolsets '["a2a","browser", ...]'` — the value is parsed with
  `yaml.safe_load`, so a JSON array string works. Copy the current list from `hermes config get` and
  drop only the offending name.
- Back up `config.yaml` before a list rewrite, and never hand-edit that file — `hermes config set`
  is the sanctioned path because a stray indent corrupts the live gateway config.

## 4. Verify by execution, not by reading config

Config reads can look correct while the session schema is stale or broken. And never conclude a tool is
absent from your own reasoning: **`tool_search` searches only the deferred catalog**, not the tools
already in your schema — it can return nothing for a tool that is loaded and fully callable. Check your
schema, then call the tool. Claiming "I don't have X" when X is available is a worse failure than a
call that errors, because the user acts on it.

- Fresh-session E2E is the real check — a new process rebuilds the tool list from current config:
  `hermes -m <model> --provider <provider> chat -q "Ejecuta <tool> con <args> y dime si la herramienta existe en tu lista de tools."`
- **Always pass `-m/--provider` explicitly on verification runs.** A stale `model.default` pointing at
  a provider with no credentials makes the probe die with an unrelated HTTP 400 that looks like a
  toolset failure.
- Cheap gate probe in the repo venv:
  `cd $HERMES_HOME/hermes-agent && source venv/bin/activate && HERMES_HOME=... python -c "from tools.web_tools import check_web_api_key; print(check_web_api_key())"`.
  Seed plugin discovery first: plugin-backed providers report unavailable until discovery has run, so
  a bare `get_active_*_provider()` returning `None` is not proof of absence.
- Report before/after as observed output ("session said the tool did not exist" → "session called it
  and returned results"), never as "should work now".

## 5. Timing for a running conversation

The gateway re-reads config every turn (file-mtime-keyed cache), so a toolset change needs no gateway
restart and none of the pending-restart ceremony. But a conversation that already started keeps its
old tool schema: the new tool appears in a fresh session (`/new`), while a spawned CLI process picks
it up immediately. Tell the user which one applies instead of restarting the gateway out from under
an in-flight turn.

## 6. Don't invent a credential blocker

Check for a credential-free path before saying a key is required: `web_search`/`web_extract` ship
working keyless (`web.keyless_fallback: true`, rotating the ring vendors' free tiers). `hermes tools
list` shows a toolset's state independently of keys, and many toolsets are opt-in purely by config.

## References

- `references/toolset-resolution.md` — resolution model, shared-tool membership, web backend knobs.
