# Break It: Module 02

1. **Comma timestamps in VTT.** Change `write_vtt` to use `,`. Convert a file and paste it into a
   browser `<track>` test page or run `ffmpeg -i out.vtt out.srt`. What happens?
2. **A header without a blank line.** `WEBVTT\n00:00:01.000 --> 00:00:02.000\nHi`. The tutorial
   parser raises. The full server accepts it and notes a warning. Make `parse_vtt` do the same.
3. **A cue split by a blank line.** In WebVTT a blank line really ends the cue, so the leftover text
   is not part of any cue. What should a parser do with it: drop it, attach it to the previous cue,
   or raise? (The full server attaches it and warns. Argue the other options.)
4. **Where did the NOTE go?** Put a `NOTE` between two cues, convert VTT to SRT and back to VTT.
   Where is it? Where could it have been kept, and what would that cost?
5. **An identifier that looks like a block keyword.** Give a cue the identifier `NOTES`.
   What does `EXTRA_BLOCK` do? Remove the `(?:[ \t]|$)` part of the pattern and see.
6. **Settings are not free text.** `align:start position:10%` is copied verbatim. Write a validator
   for `align`, `line`, `position`, `size`, `vertical` and `region`. Is it worth shipping?
