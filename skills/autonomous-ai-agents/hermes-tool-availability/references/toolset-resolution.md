# Toolset resolution in Hermes

## Model

1. A tool is registered at import time by `tools/*.py` (`registry.register(...)`).
2. It becomes visible only if a toolset names it: `toolsets.py::TOOLSETS` maps toolset key → tool
   names, and `_HERMES_CORE_TOOLS` is the shared bundle platform base toolsets inherit.
3. `platform_toolsets.<platform>` (e.g. `telegram`, `cli`) selects the enabled list for that surface.
4. `agent.disabled_toolsets` is subtracted **last and strictly** — a tool named by any disabled
   toolset disappears, even when another enabled toolset also names it.

The gateway resolves this per turn (`_resolve_turn_toolsets` → `_load_gateway_config()`); CLI and
spawned `hermes chat -q` processes resolve it at startup.

## Shared-tool membership

Grep rather than memorise — new tools get added:

```bash
grep -n '"web_search"' $HERMES_HOME/hermes-agent/toolsets.py
```

Known multi-toolset tools at time of writing:

- `web_search` ∈ `web`, `search` (the pair that produces the "has web_extract, missing web_search" bug)
- `web_extract` ∈ `web`
- `browser_*` ∈ `browser`
- `memory`, `todo`, `session_search` are their own opt-in toolsets, disabled by default in a fresh
  profile — a user asking for persistent memory usually needs this toolset enabled, not a new tool.

## Settable vs config-only toolset names

`hermes tools enable/disable` accepts `CONFIGURABLE_TOOLSETS` plus plugin toolset keys. Names that
live only in `agent.disabled_toolsets` (legacy buckets such as `search`) are rejected with
`✗ Unknown toolset '<name>'`; rewrite the whole list with `hermes config set` (the value is parsed
with `yaml.safe_load`, so pass a JSON array string).

## Web backend knobs (`web:` config section)

- `backend` / `search_backend` / `extract_backend` — pin a provider (strict, no autodetect probe).
- `keyless_fallback` (default `true`) — anonymous rotation across the ring vendors' public free
  tiers (Exa, Parallel, Firecrawl, Keenable) when no key is configured. This is why web search works
  on a fresh install with no API keys.
- `provider_tier.<name>: free|paid` — pins one vendor's anonymous or keyed path.
- `extract_char_limit` (default 15000), `cache_enabled`, `cache_ttl_minutes`.

## Readiness gating

`web_search`/`web_extract` both register `check_fn=check_web_api_key`, which probes the configured
backend, the legacy backends, then the plugin registry — so availability can be true keyless.
`check_fn` results are TTL-cached process-wide keyed by the profile home, which is why a probe run
before plugin discovery can answer `False` while the real session sees the tool.
