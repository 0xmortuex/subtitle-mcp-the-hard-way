"""Module 03: Time: exact milliseconds, exact NTSC frame rates, safe shifting.

Standalone: this file contains everything from the earlier modules (marked by
banner comments) plus this module's new code and a runnable check at the bottom.

    python main.py
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from fractions import Fraction

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


# --- Run it: time arithmetic ----------------------------------------------------------------
def demo_03() -> None:
    assert parse_time("00:01:02,500") == parse_time("1:02.5") == parse_time("62.5") == 62_500
    assert parse_time("100:00:00,000") == 360_000_000
    assert fps_fraction(29.97) == Fraction(30000, 1001)
    # 30000 frames at "29.97" last exactly 1001 seconds. With the float 29.97 you would be
    # about 1 ms off already.
    assert frames_to_ms(30000, 29.97) == 1_001_000
    assert 30000 * 1000 / 29.97 != 1_001_000  # the float answer is not exact
    assert frames_to_ms(24, 29.97) == 801 and frames_to_ms(-24, 29.97) == -801
    assert frames_to_ms(1, 25) == 40
    cues = [Cue(1000, 3000, "a"), Cue(4000, 6000, "b"), Cue(10_000, 12_000, "c")]
    assert [c.start for c in shift_cues(cues, 1500)] == [2500, 5500, 11_500]
    assert [c.start for c in shift_cues(cues, -500, from_index=1)] == [1000, 3500, 9500]
    try:
        shift_cues(cues, -2000)
    except ValueError as e:
        print("refused:", e)
    else:
        raise AssertionError("expected a ValueError")
    assert cues[0].start == 1000  # the input list is never modified
    print("module 03 OK: exact milliseconds, exact NTSC frame rates, safe shifting")


if __name__ == "__main__":
    demo_03()
