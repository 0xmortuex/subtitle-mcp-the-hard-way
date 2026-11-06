# Module 06: The Translation-Chunking Contract

Translating a subtitle is the textbook "give it to the AI" task. The wrong design hands the AI the
file: it returns a translated file, and now timing, indices, tags and cue count are all at the mercy
of a language model that is about to be bored by cue 400. The right design assumes the AI is a very
good translator and an unreliable bookkeeper, and gives it **only the part it is good at**.

## The contract

1. `chunk_for_translation` returns numbered pieces of **text only**: `[{"id": "12", "text": "..."}]`.
   No timestamps. The AI cannot damage what it never sees.
2. The AI returns `{"12": "translated text", ...}` for **all** ids.
3. `apply_translation` checks the mapping against the file **before** it writes anything, copies the
   timing, identifiers and settings from the original cue, and replaces only the text.

The server never calls a translation service and holds no API key. The agent that is already talking
to you does the translating.

## Stable ids

An id is the cue's 1-based position in the file. That sounds too simple, so why not a hash or an
opaque token? Because the id must survive being **typed back by a language model**, checked by a
human, and compared across calls. `"12"` does all three. It is stable as long as the file is not
edited, and `apply_mapping` verifies the ids against the file it is given: an id past the end means "this
mapping was made for a different file".

Chunking (`make_chunks`) is deterministic: the same file and `max_chars` always yield the same chunks, so the agent
can ask for chunk 3 without chunk 1 and 2 shifting under it. A single cue longer than `max_chars`
gets a chunk to itself rather than being cut.

## All or nothing

`apply_mapping` raises for:

- ids that are not cues of this file (extra or stale);
- cues with no translation (a lazily skipped cue would silently stay in the source language).

The error lists the offenders (first 10 or 20) so the agent can fix its answer instead of guessing. The full
server adds `partial=true` for chunk-by-chunk workflows, and still names exactly which cues were left.

## Warnings: things that are valid but suspicious

A translation can be a perfectly legal string and still be wrong for a subtitle:

- **empty** where the source has text;
- **much longer or shorter** (outside 0.4x-1.6x): usually an omission or an addition;
- **formatting tags that differ** from the source (`<i>` lost, `{\an8}` lost): the text between
  tags is translated but the italics vanish;
- (full server) **reads too fast** now that the text is longer.

They do not block the write. They are returned in the answer, so the agent can revise cue 17 and send a
corrected mapping. This is the pattern for anything judgement-shaped: **errors block, warnings inform.**

Next: [Module 07](../07-mcp-wrapper-and-testing/) — wiring everything into an MCP server, and proving it works.
