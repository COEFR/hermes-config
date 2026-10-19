# MemoryStore internals

Implementation: `tools/memory_tool.py` (surface) + `tools/memory_tool_store.py` (`MemoryStore`).

## Files

| File | Purpose |
|---|---|
| `$HERMES_HOME/memories/MEMORY.md` | environment / project facts (`target="memory"`) |
| `$HERMES_HOME/memories/USER.md` | who the user is, standing preferences (`target="user"`) |
| `*.lock` | per-file flock used to serialise concurrent writers |

Both files are plain markdown: entries separated by `ENTRY_DELIMITER = "\n§\n"`, order preserved.

## Reading limits and usage

```python
s = load_on_disk_store()
s.target_enabled("memory"), s._entries_for("user"), s._char_count("memory"), s._char_limit("memory")
```

Limits come from `memory.memory_char_limit` / `memory.user_char_limit`; a write response carries `usage`
as `"NN% — N,NNN/N,NNN chars"` plus `entry_count`. Treat any unexplained drop as data loss (see the
`replace` pitfall in SKILL.md) and inspect the file before continuing.

## Operation shapes

```python
s.add(target, content)
s.replace(target, old_text, new_content)      # new_content REPLACES the whole matched entry
s.remove(target, old_text)
s.apply_batch(target, [{"action": "add"|"replace"|"remove", "content": ..., "old_text": ...}])
```

- `old_text` is a substring match per entry; an exact duplicate match picks the first entry, distinct
  multiple matches are reported as ambiguous.
- `apply_batch` applies operations in order against the final state, atomically — use it for consolidation.

## Errors you will meet

| Error | Meaning / action |
|---|---|
| `After applying all N operations, memory would be at X/Y chars -- over the limit` | Trim or remove inside the SAME batch; nothing was written. |
| `Refusing to write <file>: file on disk has content that wouldn't round-trip` | The file was edited outside the tool. A `.bak` snapshot is written; merge the content back via the store, then clean the file. |
| `Refusing to write <file>: the file exists on disk but could not be read right now` | Lock / permission / encoding problem — retry; do not assume the file is empty. |
| `Built-in USER.md writes are disabled in memory config` | `memory.user_profile_enabled` is false (same shape for `memory.memory_enabled` / MEMORY.md). |

## Session-store companion

`sessions` holds one row per conversation (`id`, `source`, `chat_id`, `session_key`, `message_count`,
`tool_names`, `title`, token/cost counters); `messages` holds the turns (`session_id`, `role`, `content`,
`platform_message_id`, `timestamp`, `active`, `compacted`). Per-platform routing lives in
`gateway_routing`. When only inspecting, open read-only: `sqlite3.connect("file:state.db?mode=ro", uri=True)`.
