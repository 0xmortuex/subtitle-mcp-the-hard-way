# Module 01: SRT Format and Parsing

An SRT file is a list of blocks separated by blank lines:

```
1
00:00:01,000 --> 00:00:03,000
Hello there.
Second row.

2
00:00:04,000 --> 00:00:06,000
Next cue.
```

Number, timing line, one or more text lines, blank line. The spec is a convention, not a
standard, and the files in the wild break every part of it. Run `python main.py` to see the
sample the module uses: a BOM, mixed CRLF and LF, an index that is not 2, a blank line **inside**
a cue, a cue with no index and a dot before the milliseconds, and a cue at hour 100.

## The idea: anchor on the timing line

The obvious parser splits on blank lines and reads "number, timing, text" from each block. That
works on clean files and falls over on everything else: a missing number shifts every field by one;
a blank line inside a cue cuts the cue in two; a number separated from its timing by a blank line
orphans it.

`parse_srt` does the opposite. The timing line is the only line that is unmistakable (two
timestamps and an arrow), so it finds all of them first, then reads outward:

- a cue's text runs until the next timing line;
- the line directly above the next timing line, if it is only digits, is that cue's index and not
  our text;
- trailing blank lines are separators and are trimmed.

Blank lines in the middle of the text stay in the text. Missing, duplicate and out-of-order indices
do not matter at all, because **the index is never used** for anything: the writer renumbers 1..N.
The less your parser depends on the parts of the format people get wrong, the more files it reads.

## The timestamp pattern

```python
TS = r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d+))?"
```

Hours are optional and have any number of digits (`100:00:00,000` is real). The separator is `.`
or `,`. The fraction has any number of digits, and it is a decimal fraction of a second: `,5` is 500 ms,
not 5 ms. More than three digits are rounded to the nearest millisecond, **half up**
(`round_half_up` uses `Fraction`; Python's `round` rounds halves to even and would make `0.5` ms
disappear). The arrow is `-+>` so `->` and `--->` are accepted.

## Lines, not `splitlines()`

`split_lines` uses a regex on `\r\n | \r | \n`. `str.splitlines()` also splits on U+2028, U+0085 and
a few other characters that can legitimately appear in subtitle text, and would silently cut a cue
in two.

## Two policies worth stating out loud

- The **parser is generous** (it accepts what players accept) and **the writer is strict** (one
  well-formed output). Blank lines inside a cue are dropped on write because every player ends
  the cue at the blank line.
- **Times are integer milliseconds.** `ms_to_ts` raises on a negative value instead of printing
  `-00:00:01,000`, which no player reads. Module 03 explains the integers.

## Run it

```bash
python main.py
```

The check parses the messy sample, asserts every start and end, asserts the writer cleans the
blank line, and asserts that `parse_srt(write_srt(x)) == x` on what it wrote.

Next: [Module 02](../02-webvtt-differences/) — WebVTT looks like SRT and is not.
