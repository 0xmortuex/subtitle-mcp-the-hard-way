"""Module 07: MCP: six tools over stdio, sandbox, safe writes, a real test.

Standalone: this file contains everything from the earlier modules (marked by
banner comments) plus this module's new code and a runnable check at the bottom.

    python main.py [--serve]
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from fractions import Fraction
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pathlib import Path
from typing import Any

# ===========================================================================
# MODULE 01 - SRT format and parsing
# ===========================================================================

# A timestamp is [hours:]minutes:seconds[,.]fraction. Real files disagree about
# nearly everything here, so the pattern is deliberately loose:
#   - hours may have any number of digits (100:00:00,000 exists in the wild)
#   - the separator before the fraction is a comma (SRT) or a dot (WebVTT)
#   - the fraction may have any number of digits ("5" means half a second)
TS = r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d+))?"

# A timing line: two timestamps around an arrow, then optional trailing text
# (WebVTT cue settings, or SRT screen coordinates). "-+>" accepts "-->" and "->".
TIMING = re.compile(r"^\s*" + TS + r"\s*-+>\s*" + TS + r"(?:\s+(.*?))?\s*$")


def round_half_up(x: Fraction) -> int:
    """Round to the nearest integer, halves up. Python's round() rounds halves to
    even (round(0.5) == 0), which would make 0.5 ms vanish."""
    return math.floor(x + Fraction(1, 2))


@dataclass
class Cue:
    start: int  # milliseconds. Integers, never floats: see module 03.
    end: int
    text: str  # lines joined with "\n"
    ident: str | None = None  # WebVTT cue identifier (module 02)
    settings: str = ""  # text after the timestamps


def ts_to_ms(h: str | None, m: str, s: str, frac: str | None) -> int:
    ms = (int(h or 0) * 3600 + int(m) * 60 + int(s)) * 1000
    if frac:
        # "5" is 0.5 s; "0005" is 0.5 ms, which rounds to 1.
        ms += round_half_up(Fraction(int(frac), 10 ** len(frac)) * 1000)
    return ms


def ms_to_ts(ms: int, sep: str = ",") -> str:
    if ms < 0:
        raise ValueError(f"a time of {ms} ms is before 00:00:00 and cannot be written")
    h, rest = divmod(ms, 3_600_000)
    m, rest = divmod(rest, 60_000)
    s, milli = divmod(rest, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{milli:03d}"  # hours grow past 99 if needed


def split_lines(text: str) -> list[str]:
    # Not str.splitlines(): that also splits on U+2028 and other characters that
    # can legitimately appear inside subtitle text.
    return re.split(r"\r\n|\r|\n", text.lstrip("﻿"))  # lstrip drops a BOM


def parse_srt(text: str) -> list[Cue]:
    """Find every timing line, then read outward from it. This one idea survives most
    real-world damage: it does not care whether indices exist, are duplicated, or are
    out of order, and it does not need blank lines to be where they should be."""
    lines = split_lines(text)
    timing_at = [i for i, line in enumerate(lines) if TIMING.match(line)]
    cues: list[Cue] = []
    for n, i in enumerate(timing_at):
        m = TIMING.match(lines[i])
        assert m is not None
        g = m.groups()
        stop = timing_at[n + 1] if n + 1 < len(timing_at) else len(lines)
        body = lines[i + 1 : stop]
        # The line just above the next timing line is that cue's index, not our text.
        if n + 1 < len(timing_at) and body and body[-1].strip().isdigit():
            body.pop()
        while body and not body[-1].strip():  # blank separator lines between cues
            body.pop()
        cues.append(Cue(ts_to_ms(*g[0:4]), ts_to_ms(*g[4:8]), "\n".join(body), settings=g[8] or ""))
    return cues


def write_srt(cues: list[Cue], newline: str = "\n") -> str:
    blocks = []
    for number, cue in enumerate(cues, 1):  # always renumber 1..N: indices are noise
        timing = f"{ms_to_ts(cue.start)} --> {ms_to_ts(cue.end)}"
        if cue.settings:
            timing += " " + cue.settings
        # A blank line inside a cue would end the cue in every player, so drop them.
        text_lines = [ln for ln in cue.text.split("\n") if ln.strip()]
        blocks.append(newline.join([str(number), timing, *text_lines]))
    return (newline + newline).join(blocks) + newline if blocks else ""


# ===========================================================================
# MODULE 02 - WebVTT: what changes
# ===========================================================================


@dataclass
class Subtitle:
    cues: list[Cue]
    header: str = "WEBVTT"  # the first block: "WEBVTT" plus optional title/metadata
    # NOTE / STYLE / REGION blocks, each remembered with "how many cues came before it"
    # so that writing the file puts it back where it was.
    extras: list[tuple[int, str]] | None = None


EXTRA_BLOCK = re.compile(r"(NOTE|STYLE|REGION)(?:[ \t]|$)")


def split_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip():
            current.append(line)
        elif current:
            blocks.append(current)
            current = []
    if current:
        blocks.append(current)
    return blocks


def parse_vtt(text: str) -> Subtitle:
    blocks = split_blocks(split_lines(text))
    if not blocks or not blocks[0][0].startswith("WEBVTT"):
        raise ValueError("a WebVTT file must start with the line WEBVTT")
    sub = Subtitle([], header="\n".join(blocks[0]), extras=[])
    assert sub.extras is not None
    for block in blocks[1:]:
        if EXTRA_BLOCK.match(block[0]):
            sub.extras.append((len(sub.cues), "\n".join(block)))
            continue
        at = next((k for k, line in enumerate(block) if TIMING.match(line)), None)
        if at is None:
            raise ValueError(f"block without a timing line: {block[0]!r}")
        m = TIMING.match(block[at])
        assert m is not None
        g = m.groups()
        # In WebVTT the line above the timing line is an optional identifier (any text,
        # not just a number). In SRT it is the index. Same position, different meaning.
        ident = block[at - 1].strip() if at == 1 else None
        sub.cues.append(
            Cue(ts_to_ms(*g[0:4]), ts_to_ms(*g[4:8]), "\n".join(block[at + 1 :]), ident, g[8] or "")
        )
    return sub


def write_vtt(sub: Subtitle, newline: str = "\n") -> str:
    blocks = [sub.header]
    extras = sorted(sub.extras or [], key=lambda e: e[0])
    e = 0
    for i, cue in enumerate(sub.cues):
        while e < len(extras) and extras[e][0] <= i:
            blocks.append(extras[e][1])
            e += 1
        # WebVTT writes a DOT before the milliseconds. Comma-timestamps are invalid.
        timing = f"{ms_to_ts(cue.start, '.')} --> {ms_to_ts(cue.end, '.')}"
        if cue.settings:
            timing += " " + cue.settings
        text_lines = [ln for ln in cue.text.split("\n") if ln.strip()]
        blocks.append("\n".join(([cue.ident] if cue.ident else []) + [timing, *text_lines]))
    blocks += [b for _, b in extras[e:]]
    return (newline + newline).join(b.replace("\n", newline) for b in blocks) + newline


def srt_to_vtt(srt_text: str) -> str:
    return write_vtt(Subtitle(parse_srt(srt_text)))


def vtt_to_srt(vtt_text: str) -> str:
    # SRT has nowhere to put identifiers, settings, NOTE, STYLE or REGION: they are
    # dropped. The real server lists what it dropped; here we just do it.
    cues = parse_vtt(vtt_text).cues
    for cue in cues:
        cue.settings = ""
    return write_srt(cues)


# ===========================================================================
# MODULE 03 - Time arithmetic
# ===========================================================================

# Why integer milliseconds? 0.1 + 0.2 != 0.3 in floating point, and a subtitle
# file is thousands of additions long. Integers are exact, so two tools that
# agree on "ms" agree on every digit.

# NTSC video does not run at 24, 30 or 60 frames per second. It runs at
# 24000/1001, 30000/1001 and 60000/1001: 23.976..., 29.97002997...
# People write 23.976 and 29.97, so we map the common spellings to the exact fractions.
NTSC = [Fraction(n, 1001) for n in (24000, 30000, 48000, 60000, 120000)]


def fps_fraction(fps: float) -> Fraction:
    if fps <= 0:
        raise ValueError(f"fps must be positive, got {fps}")
    for exact in NTSC:
        if abs(fps - float(exact)) < 0.01:
            return exact
    return Fraction(str(fps))  # Fraction("25.0") == 25: parsed as decimal text, no float noise


def parse_time(text: str) -> int:
    """A time typed by a human or an agent: 00:01:02,500 / 00:01:02.5 / 1:02.5 / plain seconds."""
    text = text.strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return round_half_up(Fraction(text) * 1000)
    m = re.fullmatch(TS, text)
    if not m:
        raise ValueError(f"cannot read time {text!r}: use HH:MM:SS,mmm, MM:SS.mmm or seconds")
    return ts_to_ms(*m.groups())


def frames_to_ms(frames: int, fps: float) -> int:
    """How long `frames` frames last, in whole milliseconds, rounded half away from zero."""
    exact = Fraction(frames * 1000) / fps_fraction(fps)
    return -round_half_up(-exact) if exact < 0 else round_half_up(exact)


def shift_cues(cues: list[Cue], offset_ms: int, from_index: int = 0) -> list[Cue]:
    """Return new cues moved by offset_ms, starting at 0-based from_index.
    Refuses to produce a time before 00:00:00 instead of silently clamping it."""
    out = [Cue(c.start, c.end, c.text, c.ident, c.settings) for c in cues]
    for pos in range(from_index, len(out)):
        out[pos].start += offset_ms
        out[pos].end += offset_ms
        if out[pos].start < 0:
            raise ValueError(
                f"cue {pos + 1} would start at {out[pos].start} ms, before 00:00:00; "
                "use a smaller negative offset or shift only from a later cue"
            )
    return out


# ===========================================================================
# MODULE 04 - Resync: a linear fit in exact arithmetic
# ===========================================================================


@dataclass(frozen=True)
class LinearMap:
    """new_time = a * old_time + b.  a is the speed ratio (drift), b the offset.
    Both are Fractions: the line is exact, and rounding to a whole millisecond
    happens exactly once, at the very end, for each time."""

    a: Fraction
    b: Fraction

    def apply(self, t: int) -> int:
        return round_half_up(self.a * t + self.b)


def fit_linear(points: list[tuple[int, int]]) -> LinearMap:
    """Least-squares line through (old, wanted) points. With two points the line
    goes exactly through both; with more it minimises the sum of squared errors.

        a = (n*Sxy - Sx*Sy) / (n*Sxx - Sx^2)       b = (Sy - a*Sx) / n
    """
    n = len(points)
    if n < 2:
        raise ValueError("need at least two anchor points")
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    denominator = n * sxx - sx * sx  # zero when every anchor has the same x
    if denominator == 0:
        raise ValueError("the anchors are all at the same time; pick two different places")
    a = Fraction(n * sxy - sx * sy, denominator)
    b = (Fraction(sy) - a * sx) / n
    return LinearMap(a, b)


def residuals(m: LinearMap, points: list[tuple[int, int]]) -> list[int]:
    """Error left at each anchor after rounding: applied minus wanted, in ms."""
    return [m.apply(x) - y for x, y in points]


def resync_cues(cues: list[Cue], m: LinearMap) -> list[Cue]:
    out = [Cue(m.apply(c.start), m.apply(c.end), c.text, c.ident, c.settings) for c in cues]
    for pos, c in enumerate(out, 1):
        if c.start < 0:
            raise ValueError(f"cue {pos} would start before 00:00:00 (check the anchors)")
    return out


# ===========================================================================
# MODULE 05 - Problem detection and a dry-run fixer
# ===========================================================================

TAG = re.compile(r"</?[A-Za-z][^<>]*>|\{\\[^{}]*\}")  # <i>, <font color="red">, {\an8}


def visible_chars(text: str) -> int:
    """What a viewer has to read: tags and line breaks do not count."""
    return len(TAG.sub("", text).replace("\n", ""))


def cps(cue: Cue) -> float | None:
    duration = cue.end - cue.start
    return None if duration <= 0 else visible_chars(cue.text) * 1000 / duration


def find_problems(cues: list[Cue], max_cps: float = 25.0) -> dict[str, list[int]]:
    """kind -> 1-based cue numbers. Numbers are positions in the file, the same
    numbers a human sees in an editor and the same ones every later tool uses."""
    found: dict[str, list[int]] = {}

    def add(kind: str, number: int) -> None:
        found.setdefault(kind, []).append(number)

    for i, c in enumerate(cues, 1):
        if c.end <= c.start:
            add("bad_duration", i)
        speed = cps(c)
        if speed is not None and speed > max_cps:
            add("reading_speed", i)  # a judgement call: flag it, never "fix" it
    for i, (a, b) in enumerate(zip(cues, cues[1:]), 2):
        if b.start < a.start:
            add("out_of_order", i)
    by_time = sorted(enumerate(cues, 1), key=lambda p: (p[1].start, p[1].end))
    for (_, a), (j, b) in zip(by_time, by_time[1:]):
        if b.start < a.end:
            add("overlap", j)
    return found


def plan_fixes(cues: list[Cue]) -> tuple[list[Cue], list[str]]:
    """Return (repaired cues, one human-readable line per change). Nothing is written:
    the caller decides. This is what makes 'dry run by default' cheap: the dry run IS
    the real run, minus the final file write."""
    log: list[str] = []
    items = list(enumerate([Cue(c.start, c.end, c.text, c.ident, c.settings) for c in cues], 1))

    moved = [i for (_, a), (i, b) in zip(items, items[1:]) if b.start < a.start]
    if moved:
        items.sort(key=lambda p: (p[1].start, p[1].end))  # stable sort keeps equal starts in order
        log.append(f"re-sorted by start time ({len(moved)} cue(s) were out of order)")

    for k, (i, c) in enumerate(items):
        if c.end <= c.start:
            wanted = max(1000, min(7000, round(visible_chars(c.text) * 1000 / 15)))  # ~15 chars/s
            nxt = items[k + 1][1] if k + 1 < len(items) else None
            if nxt is not None and nxt.start > c.start:
                wanted = min(wanted, nxt.start - c.start)  # never run into the next cue
            log.append(f"cue {i}: end {ms_to_ts(c.end)} -> {ms_to_ts(c.start + wanted)}")
            c.end = c.start + wanted

    for (i, a), (j, b) in zip(items, items[1:]):
        if a.end > b.start > a.start:
            log.append(f"cue {i}: end {ms_to_ts(a.end)} -> {ms_to_ts(b.start)} (cue {j} starts)")
            a.end = b.start
    return [c for _, c in items], log


# ===========================================================================
# MODULE 06 - The translation-chunking contract
# ===========================================================================
# The server never translates. The contract between server and AI is:
#   1. chunk_for_translation hands out numbered pieces of text.
#   2. The AI returns {"id": "translated text"} for ALL ids.
#   3. apply_translation checks the mapping against the file and refuses to write
#      anything if it does not fit. Timing is never part of the exchange, so it
#      cannot be damaged.


def make_chunks(cues: list[Cue], max_chars: int) -> list[list[tuple[str, str]]]:
    """Group (id, text) pairs into chunks of at most max_chars of text. The id of a
    cue is its 1-based position: stable, human-checkable, and impossible to confuse
    with a timestamp. A cue longer than max_chars gets a chunk to itself."""
    chunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    size = 0
    for i, cue in enumerate(cues, 1):
        if current and size + len(cue.text) > max_chars:
            chunks.append(current)
            current, size = [], 0
        current.append((str(i), cue.text))
        size += len(cue.text)
    if current:
        chunks.append(current)
    return chunks


def apply_mapping(cues: list[Cue], mapping: dict[str, str]) -> tuple[list[Cue], list[str]]:
    """Replace cue text. Returns (new cues, warnings). Raises if ids do not fit."""
    valid = {str(i) for i in range(1, len(cues) + 1)}
    unknown = sorted(set(mapping) - valid, key=lambda k: (len(k), k))
    if unknown:
        raise ValueError(f"ids that are not cues of this file: {unknown[:10]}")
    missing = [str(i) for i in range(1, len(cues) + 1) if str(i) not in mapping]
    if missing:
        raise ValueError(f"{len(missing)} cue(s) have no translation: ids {missing[:20]}")
    out: list[Cue] = []
    warnings: list[str] = []
    for i, cue in enumerate(cues, 1):
        new = mapping[str(i)]
        old_len, new_len = len(cue.text.replace("\n", "")), len(new.replace("\n", ""))
        if not new.strip() and cue.text.strip():
            warnings.append(f"cue {i}: translation is empty")
        elif old_len >= 12 and not 0.4 <= new_len / old_len <= 1.6:
            warnings.append(f"cue {i}: length changed a lot ({old_len} -> {new_len} characters)")
        if sorted(TAG.findall(cue.text)) != sorted(TAG.findall(new)):
            warnings.append(f"cue {i}: formatting tags differ from the source")
        # Only the text changes: start, end, ident and settings are copied untouched.
        out.append(Cue(cue.start, cue.end, new, cue.ident, cue.settings))
    return out, warnings


# ===========================================================================
# MODULE 07 - The MCP wrapper (and how to test it for real)
# ===========================================================================

mcp = MCPServer(
    "mini-subtitle",
    instructions=(
        "Subtitle toolbox for SRT/WebVTT. subtitle_info first; shift or resync to fix timing; "
        "check_problems for repairs (dry run); chunk_for_translation then apply_translation "
        "to translate - YOU translate, the server only keeps the bookkeeping. Nothing is "
        "overwritten unless overwrite=true."
    ),
)

ALLOWED: list[Path] = []  # set from --dir; empty means unrestricted


def resolve(path: str) -> Path:
    """Sandbox: every path the agent supplies is resolved (.. and symlinks too) and must
    land inside an allowed directory."""
    p = Path(path)
    if not p.is_absolute() and ALLOWED:
        p = ALLOWED[0] / p
    p = p.resolve()
    if ALLOWED and not any(p.is_relative_to(root) for root in ALLOWED):
        raise ValueError(f"{p} is outside the allowed directories")
    if p.suffix.lower() not in (".srt", ".vtt"):
        raise ValueError("only .srt and .vtt files are handled")
    return p


def load(path: str) -> tuple[Path, str, list[Cue] | Subtitle]:
    p = resolve(path)
    if not p.is_file():
        raise ValueError(f"{p} does not exist")
    text = p.read_bytes().decode("utf-8-sig")  # a BOM is allowed; other encodings are the full server's job
    if p.suffix.lower() == ".vtt":
        return p, "vtt", parse_vtt(text)
    return p, "srt", parse_srt(text)


def cues_of(parsed: list[Cue] | Subtitle) -> list[Cue]:
    return parsed.cues if isinstance(parsed, Subtitle) else parsed


def save(p: Path, fmt: str, parsed: list[Cue] | Subtitle, cues: list[Cue], output: str | None, overwrite: bool, suffix: str) -> Path:
    dest = resolve(output) if output else p.with_name(f"{p.stem}.{suffix}{p.suffix}")
    text = write_vtt(Subtitle(cues, parsed.header, parsed.extras)) if isinstance(parsed, Subtitle) else write_srt(cues)
    if dest.exists() and not overwrite:
        raise ValueError(f"{dest} already exists; pass overwrite=true to replace it")
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, dest)  # atomic: readers see the old file or the new one, never half
    return dest


def tool(fn: Any) -> Any:
    """Register a tool. mcp 2.x shows a client only a ToolError's message; any other
    exception becomes a useless 'Error executing tool'. So expected errors are converted
    here, once, at the boundary."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except (ValueError, OSError) as e:
            raise ToolError(str(e)) from e

    mcp.tool()(wrapper)
    return fn


@tool
def subtitle_info(path: str) -> str:
    """Summarise a subtitle file: format, cue count, span, reading speed and problems.
    Run this first. Read-only."""
    _, fmt, parsed = load(path)
    cues = cues_of(parsed)
    speeds = [s for c in cues if (s := cps(c)) is not None]
    info = {
        "format": fmt,
        "cue_count": len(cues),
        "first_start": ms_to_ts(min(c.start for c in cues)),
        "last_end": ms_to_ts(max(c.end for c in cues)),
        "max_chars_per_sec": round(max(speeds), 1) if speeds else None,
        "problems": find_problems(cues),
    }
    return json.dumps(info, indent=2)


@tool
def shift(path: str, offset_ms: int | None = None, frames: int | None = None, fps: float | None = None,
          from_cue: int | None = None, output: str | None = None, overwrite: bool = False) -> str:
    """Move cues by offset_ms, or by `frames` at `fps` (29.97 is exact). Optionally only
    from cue number from_cue onward. Writes a new file next to the original."""
    if (offset_ms is None) == (frames is None):
        raise ValueError("give exactly one of offset_ms or frames (with fps)")
    if frames is not None:
        if fps is None:
            raise ValueError("frames needs fps")
        offset_ms = frames_to_ms(frames, fps)
    assert offset_ms is not None
    p, fmt, parsed = load(path)
    moved = shift_cues(cues_of(parsed), offset_ms, (from_cue or 1) - 1)
    dest = save(p, fmt, parsed, moved, output, overwrite, "shifted")
    return f"Shifted by {offset_ms} ms. Wrote {dest}"


@tool
def resync(path: str, anchors: list[dict[str, Any]], output: str | None = None, overwrite: bool = False) -> str:
    """Fix offset AND drift. anchors: [{"cue": 1, "to": "00:00:12,510"}, {"cue": 4, "to": "01:40:08,500"}]
    (cue = cue number whose start is wrong, to = when it should be). Reports the error at each anchor."""
    p, fmt, parsed = load(path)
    cues = cues_of(parsed)
    points = []
    for a in anchors:
        points.append((cues[int(a["cue"]) - 1].start, parse_time(a["to"])))
    line = fit_linear(points)
    dest = save(p, fmt, parsed, resync_cues(cues, line), output, overwrite, "resynced")
    return (f"new = {float(line.a):.9f} * old + {float(line.b):.3f} ms (a = {line.a}, b = {line.b}); "
            f"error at anchors {residuals(line, points)} ms. Wrote {dest}")


@tool
def check_problems(path: str, apply: bool = False, output: str | None = None, overwrite: bool = False) -> str:
    """List problems and the fixes that would be made. DRY RUN unless apply=true."""
    p, fmt, parsed = load(path)
    fixed, log = plan_fixes(cues_of(parsed))
    lines = [f"found: {find_problems(cues_of(parsed))}", *log]
    if apply:
        lines.append(f"Wrote {save(p, fmt, parsed, fixed, output, overwrite, 'fixed')}")
    else:
        lines.append("Dry run: nothing written. Call again with apply=true.")
    return "\n".join(lines)


@tool
def chunk_for_translation(path: str, max_chars: int = 1500, chunk: int = 1) -> str:
    """Return one batch of cues to translate: [{"id": "1", "text": "..."}]. Translate every
    text yourself, keep the ids, then call apply_translation with {id: translation} for ALL ids."""
    _, _, parsed = load(path)
    chunks = make_chunks(cues_of(parsed), max_chars)
    if not 1 <= chunk <= len(chunks):
        raise ValueError(f"chunk must be between 1 and {len(chunks)}")
    return json.dumps({"chunk": chunk, "chunk_count": len(chunks),
                       "cues": [{"id": i, "text": t} for i, t in chunks[chunk - 1]]}, ensure_ascii=False)


@tool
def apply_translation(path: str, mapping: dict[str, str], output: str | None = None, overwrite: bool = False) -> str:
    """Write the translated file. Every cue id must be in mapping; timing is untouched."""
    p, fmt, parsed = load(path)
    new_cues, warnings = apply_mapping(cues_of(parsed), mapping)
    dest = save(p, fmt, parsed, new_cues, output, overwrite, "translated")
    return f"Wrote {dest}. Warnings: {warnings or 'none'}"


# --- Testing it for real: the same path a real agent takes -------------------------------
# The demo starts THIS file as a subprocess with --serve, speaks MCP to it over
# stdin/stdout, and checks real files on disk.


async def run_session(work: Path) -> None:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    params = StdioServerParameters(
        command=sys.executable, args=[__file__, "--serve", "--dir", str(work)],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        names = {t.name for t in (await session.list_tools()).tools}
        assert names == {"subtitle_info", "shift", "resync", "check_problems",
                         "chunk_for_translation", "apply_translation"}, names

        res = await session.call_tool("resync", {"path": "bad.srt", "anchors": [
            {"cue": 1, "to": "00:00:12,510"}, {"cue": 4, "to": "01:40:08,500"}]})
        assert not res.is_error, res.content
        assert "a = 1001/1000, b = 2500" in res.content[0].text, res.content[0].text
        fixed = (work / "bad.resynced.srt").read_text(encoding="utf-8")
        assert "00:10:03,100 --> 00:10:04,101" in fixed and "01:40:08,500 --> 01:40:09,501" in fixed

        res = await session.call_tool("shift", {"path": "bad.srt", "frames": 24, "fps": 29.97})
        assert "801 ms" in res.content[0].text

        # The error an agent sees must say what to do next, not 'Error executing tool'.
        res = await session.call_tool("shift", {"path": "bad.srt", "offset_ms": -99_999_999})
        assert res.is_error and "before 00:00:00" in res.content[0].text
        res = await session.call_tool("shift", {"path": "../escape.srt", "offset_ms": 1})
        assert res.is_error and "outside the allowed directories" in res.content[0].text
        res = await session.call_tool("shift", {"path": "bad.srt", "offset_ms": 1})
        assert res.is_error and "overwrite=true" in res.content[0].text  # second write refused

        res = await session.call_tool("chunk_for_translation", {"path": "bad.srt"})
        ids = [c["id"] for c in json.loads(res.content[0].text)["cues"]]
        res = await session.call_tool("apply_translation", {"path": "bad.srt", "mapping": {"1": "x"}})
        assert res.is_error and "have no translation" in res.content[0].text
        res = await session.call_tool("apply_translation", {"path": "bad.srt", "mapping": {i: f"T{i}" for i in ids}})
        assert not res.is_error and "T4" in (work / "bad.translated.srt").read_text(encoding="utf-8")


def demo_07() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "bad.srt").write_text(
            "1\n00:00:10,000 --> 00:00:11,000\nline 1\n\n2\n00:10:00,000 --> 00:10:01,000\nline 2\n\n"
            "3\n00:50:00,000 --> 00:50:01,000\nline 3\n\n4\n01:40:00,000 --> 01:40:01,000\nline 4\n",
            encoding="utf-8", newline="\n")
        asyncio.run(run_session(work.resolve()))
    print("module 07 OK: six tools, real stdio session, errors reach the agent")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="run the MCP server on stdio")
    parser.add_argument("--dir", action="append", default=[], help="allowed directory (repeatable)")
    args = parser.parse_args()
    ALLOWED.extend(Path(d).resolve() for d in args.dir)
    if args.serve:
        mcp.run()
    else:
        demo_07()


if __name__ == "__main__":
    main()
