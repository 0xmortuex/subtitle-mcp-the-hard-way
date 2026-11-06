# Break It: Module 01

1. **The lone number.** Add a cue whose last text line is just `1984`, followed by a cue with no
   index. What does `parse_srt` do with `1984`? Why is this ambiguous even for a human? (Hint: the
   rule "the line above the next timing line, if digits, is an index" cannot tell a year from an
   index. The full server only applies it when no blank line separates them, and treats a lone
   digit block followed by a timing block as an index. Try to write that rule.)
2. **Index and timing split by a blank line.** `5`, blank line, `00:00:06,000 --> ...`. The
   tutorial parser leaves the `5` in the previous cue's text. Fix it without breaking challenge 1.
3. **Two cues glued together.** Remove the blank line between two cues. Does it still parse? Why?
4. **Fraction digits.** Parse `00:00:01,5`, `00:00:01,50`, `00:00:01,500`, `00:00:01,5004`,
   `00:00:01,5005`. Predict each in milliseconds before running it.
5. **The Unicode trap.** Put `U+2028` inside a cue's text. Swap `split_lines` for
   `str.splitlines()`. What changes, and why is that a data-loss bug?
6. **A float.** Replace `Fraction` with `round(float(...) * 1000)` in `ts_to_ms`. Find a fraction
   where the answer is off by one millisecond. (`round(0.5)` is already enough.)
