"""Module 01: SRT: the format, and a parser that survives real files.

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


# --- Run it: a deliberately messy file ------------------------------------------------------
MESSY = (
    "﻿1\r\n00:00:01,000 --> 00:00:03,000\r\nGünaydın.\r\n\r\n"
    "7\n00:00:03,500 --> 00:00:05,000\nSecond cue,\n\nwith a blank line inside it\n\n"
    "00:00:10.250 --> 00:00:12.500\nNo index, and a dot before the milliseconds\n\n"
    "9\n100:00:00,000 --> 100:00:02,000\nHour one hundred\n"
)


def demo_01() -> None:
    cues = parse_srt(MESSY)
    for c in cues:
        print(f"{ms_to_ts(c.start)} --> {ms_to_ts(c.end)}  {c.text!r}")
    assert [(c.start, c.end) for c in cues] == [
        (1000, 3000), (3500, 5000), (10250, 12500), (360_000_000, 360_002_000)]
    assert cues[0].text == "Günaydın."
    assert cues[1].text == "Second cue,\n\nwith a blank line inside it"  # the parser keeps it...
    clean = write_srt(cues)
    assert "Second cue,\nwith a blank line inside it\n" in clean  # ...the writer removes it
    assert parse_srt(clean) == [  # what we write, we can read back unchanged
        Cue(c.start, c.end, "\n".join(ln for ln in c.text.split("\n") if ln.strip())) for c in cues]
    assert clean.endswith("4\n100:00:00,000 --> 100:00:02,000\nHour one hundred\n")
    assert ts_to_ms(None, "0", "0", "0005") == 1  # 0.5 ms rounds up, it does not vanish
    print("module 01 OK: messy SRT parsed, cleaned, and round-tripped")


if __name__ == "__main__":
    demo_01()
