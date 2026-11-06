# Module 04: Resync, a Linear Fit in Exact Arithmetic

A subtitle that is a constant 2 seconds late is a **shift**. A subtitle that is in sync at the start
and 7 seconds off at the end has a different problem: it was timed for a video at a different frame
rate, or it was cut from a different edit, so the error **grows** with time. Both are the same
equation:

```
new_time = a * old_time + b
```

`b` is the offset (module 03's shift is `a = 1`). `a` is the speed ratio; `a = 1.001` means "every
second of the file should last 1.001 seconds". Fixing a file means finding `a` and `b`.

## Anchors

You do not know `a` and `b`. You know that a certain line, say cue 12 at 00:06:41,000 in the file,
is actually spoken at 00:06:43,500 in your video. That is one anchor point `(old, wanted)`. Two
anchors, one near the start and one near the end, determine the line exactly:

```
a = (y2 - y1) / (x2 - x1)        b = y1 - a * x1
```

With three or more anchors that do not agree perfectly (you misjudged one by a few hundred
milliseconds), there is no line through all of them. The **least-squares** line minimises the sum of
squared vertical errors, and `fit_linear` implements the closed form in `main.py`:

```
a = (n*Sxy - Sx*Sy) / (n*Sxx - Sx^2)        b = (Sy - a*Sx) / n
```

The two-anchor case is just `n = 2` of the same formula, so there is one code path. If the denominator
is zero, every anchor has the same `x` and no line exists; the code says so and tells you to choose
anchors in different places.

## Exactness

`a` and `b` are `Fraction`s. The fit is exact: anchors `(1_000_000, 1_003_500)` and
`(5_000_000, 5_007_500)` give exactly `a = 1001/1000`, `b = 2500`, and the cue between them lands
exactly on its true time. Each output time is rounded **once**, at the very end (`LinearMap.apply`).
If you rounded `a` early instead, the error would grow with the file: a relative error of `1e-6` in
`a` is 7 ms by the end of a two-hour film, and every cue would carry a different share of it.

## The residual

A tool that fits a line and says "done" is asking to be trusted. `residuals` reports, at each anchor,
`applied - wanted` in whole milliseconds. Two anchors always give `[0, 0]`. Three anchors that
disagree by 100 ms give `[-17, 33, -17]` (checked by hand in `demo_04`), which tells the user "your
middle anchor is about 33 ms off the best line; recheck it." The residual turns a black box into a
check.

## Sanity checks

`resync_cues` raises if any cue would land before 00:00:00. In the full server a fitted `a <= 0`
(the anchors imply time running backwards) is also an error. Those are the signs of an anchor that
belongs to the wrong cue.

## Frame-rate conversion is the same thing

A file timed for 25 fps shown on a 23.976 video: frame `n` is at `n/25` in the file and `n/23.976`
in the video, so `a = 25 / (24000/1001) = 25025/24000` and `b = 0`. No anchors needed, just a
`LinearMap` (the full server's `fps_from`/`fps_to`).

Next: [Module 05](../05-problem-detection/) — finding what is wrong without being asked.
