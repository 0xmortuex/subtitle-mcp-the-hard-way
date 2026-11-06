# Break It: Module 06

1. **Send timestamps.** Make `make_chunks` include `start --> end` in each text. Ask a model (or yourself)
   to "translate" it. What can go wrong that the contract was designed to prevent?
2. **Content-addressed ids.** Replace the position with a hash of the text. Two cues say "Yes."
   What breaks? (Duplicate ids.) Add the position into the hash. What did you gain over the plain position?
3. **A partial mapping.** Add `partial: bool` to `apply_mapping`. Where do the untranslated cues
   go, and what must the answer say so the agent does not believe the job is finished?
4. **Tag drift.** The source has `{\an8}Top line`; the translation is `Ust satir` (without it).
   The warning fires. Now write a helper that re-attaches the leading tag automatically. Is that too clever?
   Whose job is it to decide?
5. **Merge order.** The agent translates chunks 1-3 in parallel and sends the mappings back
   in the wrong order. Does `apply_mapping` care? Why not?
6. **A mapping for the wrong file.** Apply a 300-cue mapping to a 200-cue file. Read the error.
   Would the agent know what to do from it alone?
