# Break It: Module 05

1. **Skip the sort.** Remove step 1 of `plan_fixes`. Which later log lines become wrong?
2. **Fix order.** Swap the overlap trim and the duration repair. Construct a file where the
   result still has an overlap.
3. **Compare adjacent cues in file order.** In `find_problems`, replace the sorted overlap loop with
   `zip(cues, cues[1:])`. Which overlap is missed in the demo data?
4. **A fixer for reading speed.** Write one that extends a fast cue's end up to the next cue's start.
   Run `find_problems` after it. What did you create? (Hint: overlap with 0 gap, or a cue on screen for
   20 seconds. Why is "flag only" the right default?)
5. **Idempotence.** Run `plan_fixes` on its own output. Assert the log is empty. Then find an input where it is not
   (hint: cues starting at the same time).
6. **The cue that is nothing but tags.** `<i></i>` has `visible_chars == 0`. What speed does it
   have, and should it be removed? (The full server removes empty cues and says so.)
