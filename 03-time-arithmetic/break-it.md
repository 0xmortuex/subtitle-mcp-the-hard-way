# Break It: Module 03

1. **Use the float.** In `frames_to_ms` replace `fps_fraction(fps)` with the float `fps`. How many
   frames at "29.97" does it take before the answer differs from the exact one by a whole
   millisecond? Write a loop that finds out.
2. **Banker's rounding.** Replace `round_half_up` with the built-in `round`. Which of the checks in
   `demo_01` and `demo_03` fail first?
3. **Clamp instead of refuse.** Make `shift_cues` clamp negative starts to 0. Shift a file by
   `-5000` ms and look at the first three cues. Now explain why the error is the better design.
4. **A shift that preserves duration.** If you clamp only the start and not the end, the cue gets
   longer. If you clamp both, it may become zero length. What invariant do you want?
5. **23.976 vs 24.** A subtitle made for a 24 fps film is played on a 23.976 video. Over a two-hour
   film, how far off is the last cue? (Answer: 24/23.976 is 1.001, so about 7.2 seconds.)
   Module 04 fixes it with `fps_from`/`fps_to`.
6. **`parse_time("1:02")`.** Is that one minute two seconds, or one hour two minutes? Read the regex
   and decide, then decide whether the ambiguity matters.
