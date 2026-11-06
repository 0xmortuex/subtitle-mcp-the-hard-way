# Subtitle MCP — The Hard Way

Build an MCP server that lets an AI agent do real subtitle work: parse messy SRT and WebVTT
files, shift and resync them with exact arithmetic, find and repair problems, and run a safe
translate-in-chunks workflow. Start from "what is a timing line" and end with a tested server
that an agent drives over stdio. No subtitle library, no framework hiding the format.

At the end you will have built a small version of
[subtitle-mcp](https://github.com/0xmortuex/subtitle-mcp) yourself, and you will understand the
three things most MCP tutorials skip: **real-world file formats are never as clean as their
spec**, **tools that edit files need guard rails**, and **the AI is a collaborator, so give it a
contract instead of a blank check** (the server never translates anything, it only keeps the
books).

## Why subtitles?

They look trivial and are not. A file can come with a BOM, three kinds of line ending, missing or
duplicated numbers, dots where commas belong, blank lines inside a cue, cues out of order, hour 100,
and text in a Turkish code page. A resync is a linear regression. A frame rate that says "29.97" is
the fraction 30000/1001. A translation touches thousands of cues and must not move one of them in
time. Each of those is a lesson in designing tools that fail loudly and fix things carefully.

## Who this is for

- Developers who built a "hello world" MCP server and want a tool set with real edge cases
- Anyone curious how a subtitle player reads a file and what makes subtitles drift
- People who want the arithmetic of resync spelled out and checked

**Prerequisites:** basic Python. `pip install -r requirements.txt` (that is just `mcp`).

## Modules

| # | Module | What You'll Build |
|---|--------|-------------------|
| 01 | [SRT Format and Parsing](01-srt-format-and-parsing/) | A parser that finds timing lines and reads outward, so missing indices, blank lines and dot-milliseconds do not matter |
| 02 | [WebVTT: What Changes](02-webvtt-differences/) | Header, identifiers, cue settings, NOTE/STYLE/REGION blocks, and SRT to VTT conversion |
| 03 | [Time Arithmetic](03-time-arithmetic/) | Integer milliseconds, half-up rounding, why 29.97 is 30000/1001, and a shift that refuses to go below zero |
| 04 | [Resync: A Linear Fit](04-resync-linear-fit/) | Fix drift and offset with two anchors, exactly, with least squares for more |
| 05 | [Problem Detection](05-problem-detection/) | Overlaps, bad durations, ordering, reading speed; a dry-run fixer that is the real fixer minus the write |
| 06 | [The Translation-Chunking Contract](06-translation-chunking-contract/) | Stable cue IDs, chunks, and an all-or-nothing mapping that cannot touch timing |
| 07 | [The MCP Wrapper and Testing It](07-mcp-wrapper-and-testing/) | Six tools over stdio, a directory sandbox, atomic no-overwrite writes, errors that tell the agent what to do, and a test that drives the server for real |

Each module contains:
- **`README.md`**: the concepts and design decisions
- **`main.py`**: a working, commented, **standalone** implementation of that stage (it includes
  the earlier stages' code, marked by banner comments, then adds the new part and a runnable check)
- **`break-it.md`**: challenges that break your own code, with hints

## How to use this course

**Option A: Build along.** Read the modules in order, run each `main.py`
(`python 03-time-arithmetic/main.py`), then do the break-it challenges.

**Option B: Reference.** Jump to the module you need. Each `main.py` stands alone.

## Checking your work

```bash
pip install -r requirements.txt
python verify.py          # run every module, then drive the finished server over real stdio
python verify.py 03 04    # only some modules
```

`verify.py` runs each `main.py` (every one asserts what its README claims) and then starts the
module 07 server as a subprocess and talks MCP to it on files none of the chapters used. CI runs
it on Linux and Windows.

## What this minimal version leaves out

The full [subtitle-mcp](https://github.com/0xmortuex/subtitle-mcp) adds: text-encoding detection (UTF-16,
Turkish cp1254, ...), ASS/SSA reading, cue-glued-together and blank-index recovery, search, read by
range, merge and split, line re-wrapping, tag stripping, more sandbox checks, and about 100 tests
including 2,400 generated round-trips and ffmpeg as an independent oracle. The tutorial keeps the
ideas and drops the breadth.

## License

MIT
