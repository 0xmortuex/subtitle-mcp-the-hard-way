# Module 03: Time Arithmetic

Everything a subtitle tool does to a file is arithmetic on times. Get the representation wrong
and every later module inherits the error.

## Integer milliseconds

Floats cannot hold 0.1 exactly, and a subtitle file is thousands of additions. If two tools disagree
by 1 ms on cue 800, you get a resynced file that does not match its own anchors. Integers add and
subtract exactly, and a millisecond is finer than any player renders. The rule: **parse to integers
at the edge, format from integers at the edge, never keep a float in between.**

## Rounding, once

Sometimes a conversion produces a half millisecond: `0.5`, `1.5`, `2.5`. `round()` in Python rounds
halves to the nearest even number (`round(0.5) == 0`, `round(1.5) == 2`), which is statistically fine
and visibly wrong for "this should round up". `round_half_up(Fraction)` does what a person expects.
Negative frame counts use the mirror rule (half away from zero), so `-24` frames is exactly the
negative of `+24`.

## Why 29.97 is 30000/1001

NTSC colour television shifted the frame rate by a factor of 1000/1001 to avoid interference. The rates
are 24000/1001 (written 23.976), 30000/1001 (29.97), 60000/1001 (59.94). If you compute with the float
29.97, 30000 frames last `30000 / 29.97 = 1001.001...` seconds instead of exactly 1001. That is
about 1 ms of error, small on its own, but it is a relative error of 1e-6 that grows with the length of the film
(about 3.6 ms per hour) and it is free to avoid.

`fps_fraction` maps the human spellings (anything within 0.01 of an NTSC value) to the exact
fraction, and everything else (`25`, `24`, `29.97003`) goes through `Fraction(str(x))`, which parses
decimal **text**, not the binary float: `Fraction("25.0") == 25`.

```python
frames_to_ms(30000, 29.97) == 1_001_000   # exact
frames_to_ms(24, 29.97)    == 801         # 800.8 rounds to 801
frames_to_ms(1, 25)        == 40
```

## Human input

`parse_time` accepts what people and agents type: `00:01:02,500`, `00:01:02.5`, `1:02.5`, or plain
seconds `62.5`. Anything else raises with an example of what is accepted. An error message for a tool
should contain the fix.

## A shift that refuses

`shift_cues` returns **new** cues (the input is never modified) and raises if a start would go below
zero. The tempting alternative, clamping to zero, silently squashes the first cues together and
destroys timing information you cannot get back. The error names the cue and the two ways out. The
optional `from_index` is for files where the first half is in sync and the second is not (a missing
scene, a CD1/CD2 split).

Run `python main.py`: the check proves the exactness claims above and the refusal.

Next: [Module 04](../04-resync-linear-fit/) — offset and drift.
