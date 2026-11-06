# Module 05: Problem Detection and a Dry-Run Fixer

Before an agent changes a file, it should know what is wrong with it. And before it changes a file it
cannot easily get back, it should be able to look at the exact edits first.

## Detect: numbers a human can check

`find_problems` returns `kind -> [cue numbers]`. The numbers are **positions in the file**, 1-based,
the same numbers every other tool in the course uses. An agent that reads "overlap: [3, 2]" can open
exactly those cues with `read_cues`. Never return indices that mean something only inside your
program.

What it checks:

- **bad_duration**: `end <= start`. Players show nothing or flash the cue.
- **out_of_order**: a cue starts before the one above it. Players that stream the file (most of them)
  show cues late or never.
- **overlap**: a cue starts before the previous one (in time order, not file order) ends. Two cues
  on screen at once, usually a timing slip.
- **reading_speed**: more than `max_cps` characters per second. Tags and line breaks do not count
  (`visible_chars`); the viewer does not read `<i>`. 25 chars/s is the default flag, since subtitles
  above roughly 17-21 are hard to read and 25+ is a problem.

## Fix: a plan, not an action

`plan_fixes` returns `(repaired cues, log)` and **does not write**. Both the dry run and the real run
call it; the real run additionally saves. That structure is what makes "dry run by default" almost
free, and it removes a whole class of bug: the preview can never disagree with the action, because
there is only one code path.

The fixes, in order, and why the order matters:

1. **Sort** by start time (stable, so equal starts keep their order). Everything after this assumes
   neighbours in the list are neighbours in time.
2. **Give bad durations a readable one**: the time needed at ~15 chars/s, clamped to 1-7 seconds,
   never running into the next cue. Done after sorting, because "the next cue" has to mean the next in time.
3. **Trim overlaps** to the next cue's start. Done last, after durations, because the new end of a
   repaired cue might overlap too.

Each change appends a line such as `cue 2: end 00:00:03,500 -> 00:00:04,633`. The log is the dry run's output.

## Flag, never fix, the judgement calls

A reading speed of 110 chars/s means someone must cut the text or extend the timing. A tool cannot
decide which, so `plan_fixes` ignores it and `find_problems` reports it. After the fix the demo asserts
`{"reading_speed": [4]}` is the **only** problem left, which is the honest end state. A fixer that
"resolved" it by extending the cue into the next one would trade one problem for another, silently.

## Idempotence

Run the fixer on its own output and it should find nothing to do. The check in `demo_05` verifies the
problem list after fixing. Idempotence is the cheapest property test you can write for a repair tool.

Next: [Module 06](../06-translation-chunking-contract/) — letting the AI do the translating.
