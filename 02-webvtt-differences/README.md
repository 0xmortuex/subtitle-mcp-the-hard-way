# Module 02: WebVTT, What Changes

WebVTT is the web's subtitle format (`<track>` in HTML). It resembles SRT closely enough that
people treat it as "SRT with dots", and that is how you end up with files no browser accepts.

```
WEBVTT - Optional title
Kind: captions

STYLE
::cue { color: lime }

NOTE This is a comment

intro
00:01.000 --> 00:03.500 align:start position:10%
<v Alice>Hello</v>
second row
```

| | SRT | WebVTT |
|---|---|---|
| First line | the first cue's number | `WEBVTT` (required), plus optional metadata until a blank line |
| Time separator | `,` | `.` |
| Hours | required | optional: `00:01.000` is one second |
| Line above the timing | index, a number | identifier, **any text**, optional |
| After the timestamps | screen coordinates (rare extension) | **cue settings**: `align:start position:10%` |
| Extra blocks | none | `NOTE`, `STYLE`, `REGION` |
| Inline markup | whatever the player supports | `<v Name>`, `<c.class>`, `<i> <b> <u>`, and inline timestamps `<00:00:05.000>` |

## Same shape, different meaning

The line above a timing line is the **index** in SRT and the **identifier** in WebVTT. Both
modules parse it from the same place; they only store it differently. In this tutorial `Cue` has
`ident` and `settings` fields for the WebVTT side, and SRT simply never uses them (and the writer
drops the index it parsed, because it renumbers).

## NOTE, STYLE and REGION

These are blocks with no timing line. A parser that insists on timing lines would fail on them
or, worse, glue a `NOTE` onto the previous cue. The fix is to recognise them by their first word
(`EXTRA_BLOCK`) and keep them as opaque text together with **how many cues came before them**.
That number is how `write_vtt` puts each block back where it was. This is a general trick for round
trips: when you cannot model something, preserve it verbatim with its position.

## Strict header, strict writer

`parse_vtt` raises if the first block does not start with `WEBVTT`. SRT has no marker at all, so a
parser can be generous there. For WebVTT the header **is** the format identifier, and guessing
would make "is this VTT or SRT?" depend on luck. The full server sniffs by content (header, then ASS
sections, then timing lines) and says which format it found.

## Conversion is lossy and should say so

`srt_to_vtt` loses nothing but gains a header and dots. `vtt_to_srt` loses the identifier, the
cue settings and every NOTE/STYLE/REGION block, because SRT cannot express them. This tutorial drops
them quietly; **the real server lists what was dropped in its answer.** A tool that changes your
data and stays quiet about it is a bug even when the change is unavoidable.

Run `python main.py`: the check proves `write_vtt(parse_vtt(x))` reproduces a complex file
(normalising only the short `00:01.000` form), and converts in both directions with exact
expected output.

Next: [Module 03](../03-time-arithmetic/) — what a time actually is.
