# Module 07: The MCP Wrapper, and How to Test It for Real

Modules 01-06 are a library. Module 07 turns it into six tools an agent can call:

| Tool | From module |
|------|-------------|
| `subtitle_info` | 01, 02, 05 |
| `shift` | 03 |
| `resync` | 04 |
| `check_problems` | 05 |
| `chunk_for_translation` | 06 |
| `apply_translation` | 06 |

`mcp = MCPServer("mini-subtitle", instructions=...)` creates the server, and `mcp.tool()` registers
a function: its **name** becomes the tool name, its **type hints** become the JSON schema, its
**docstring** becomes the description the agent reads when it decides whether to call it. That makes
the docstring the interface. Write it for an agent that has never seen your code: what the tool does, what each
argument means, what is written where, what it will refuse.

## Errors are the user interface

In `mcp` 2.x, the client only receives the message of a `ToolError`. Any other exception becomes
`Error executing tool shift` and the agent learns nothing. So the `tool` decorator catches the
errors we expect (`ValueError`, `OSError`) and re-raises them as `ToolError(str(e))`. The messages come
from modules 03-06 and were written with the next step in mind: *"cue 1 would start at -1000 ms, before
00:00:00; use a smaller negative offset or shift only from a later cue."* Anything we did **not** expect stays a
bug and is not dressed up as an answer.

## Guard rails for a tool that writes files

An agent can be wrong, confused, or steered by text it just read in a file. Four rules cost very
little and bound the damage:

1. **Sandbox (`--dir`).** `resolve()` makes every path absolute, resolves `..` and symlinks, and requires the result to be
   inside an allowed directory. The check happens **after** resolving; checking the string
   `"../"` first is the classic bypass.
2. **Extension allow-list.** Only `.srt` and `.vtt`. `output="C:/Windows/system.ini"` is refused no matter what.
3. **No overwrite by default.** Edits go to a new sibling (`movie.shifted.srt`). Replacing a file needs
   `overwrite=true`, a deliberate act the agent has to make visibly.
4. **Atomic writes.** Write `x.tmp`, then `os.replace` it. Readers see the old file or the new one, never half of a file,
   even if the process dies mid-write. (The full server also reserves the name with `O_EXCL` so two
   writers cannot both pass the "does it exist?" check.)

## Testing it for real

The check at the bottom of `main.py` does not call the tools as functions. It:

1. starts `main.py --serve --dir TMP` as a **subprocess**;
2. connects an MCP client over its stdin/stdout, exactly like Claude Desktop or Claude Code would;
3. lists the tools, asserts the names;
4. runs a resync, a frame shift, a translation, and reads the **files it wrote**;
5. calls the failure paths and asserts the agent-visible message: negative shift, path escape,
   an existing output, an incomplete translation.

Calling `shift()` directly would never notice a missing `@tool` registration, a schema that does not serialise, a
`print` that corrupts the protocol on stdout, or an exception that arrives as a useless string. Only the real
transport shows those. (Stdout belongs to the protocol: diagnostics go to stderr.)

## What the full server adds

Encoding detection, ASS reading, search and range reads, merge and split, line re-wrapping, tag stripping,
glued-cue recovery, and a test suite with 2,400 generated round-trips and ffmpeg as an independent oracle.
See [subtitle-mcp](https://github.com/0xmortuex/subtitle-mcp).

## Run it

```bash
python main.py            # the real stdio session, with asserts
python main.py --serve    # the server itself; point an MCP client at it
python ../verify.py       # everything
```

To use it from Claude Code: `claude mcp add mini-subtitle -- python /full/path/to/main.py --serve --dir /your/videos`.
