"""Module 02: WebVTT: what changes, and SRT <-> VTT conversion.

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


# --- Run it: SRT <-> WebVTT -----------------------------------------------------------------
VTT = (
    "WEBVTT - demo\n\n"
    "STYLE\n::cue { color: lime }\n\n"
    "NOTE a comment\nover two lines\n\n"
    "intro\n00:01.000 --> 00:03.500 align:start position:10%\n<v Alice>Hello</v>\nsecond row\n\n"
    "00:00:04.000 --> 00:00:06.250\nNo identifier\n"
)


def demo_02() -> None:
    sub = parse_vtt(VTT)
    assert sub.header == "WEBVTT - demo"
    assert sub.extras == [(0, "STYLE\n::cue { color: lime }"), (0, "NOTE a comment\nover two lines")]
    assert (sub.cues[0].ident, sub.cues[0].start, sub.cues[0].settings) == ("intro", 1000, "align:start position:10%")
    # Writing normalises "00:01.000" to "00:00:01.000" and keeps everything else in place.
    assert write_vtt(sub) == VTT.replace("00:01.000 -->", "00:00:01.000 -->").replace("00:03.500", "00:00:03.500")
    assert vtt_to_srt(VTT) == (
        "1\n00:00:01,000 --> 00:00:03,500\n<v Alice>Hello</v>\nsecond row\n\n"
        "2\n00:00:04,000 --> 00:00:06,250\nNo identifier\n")
    assert srt_to_vtt("1\n00:00:01,000 --> 00:00:02,000\nHi\n") == "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi\n"
    try:
        parse_vtt("1\n00:00:01,000 --> 00:00:02,000\nHi\n")
    except ValueError as e:
        print("a missing header is an error, not a guess:", e)
    else:
        raise AssertionError("expected a ValueError")
    print("module 02 OK: WebVTT header, NOTE/STYLE, identifiers, settings, both conversions")


if __name__ == "__main__":
    demo_02()
