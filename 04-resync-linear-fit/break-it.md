# Break It: Module 04

1. **Round `a`.** In `fit_linear`, replace `a` with `Fraction(round(float(a), 6))` before computing
   `b`. Resync the 100-minute example. How far off is the last cue?
2. **Swap the anchors.** Pass them in reverse order. Why does the result not change?
3. **Same-time anchors.** Pass `(5, 7)` and `(5, 9)`. Without the `denominator == 0` check, which
   exception would Python raise, and what would the agent see?
4. **A wrong anchor.** Give three good anchors and one that belongs to the wrong cue (off by 30 s).
   Look at `residuals`. Which anchor does the least-squares fit blame, and does it blame the right one?
   Write a "drop the worst anchor and refit" loop. When is that wise, and when does it hide a mistake?
5. **Negative result.** Pick anchors that make early cues land before zero. Where is the error
   raised, and why is it better raised before any output file is written?
6. **Piecewise.** A film with a scene cut in the middle is not one line; it is two. How would you
   resync it with this module's tools only? (Hint: module 03's `from_index`.)
