# Break It: Module 07

1. **Forget the decorator's translation.** Make `tool` re-raise errors unchanged. Run the
   check. What does the agent see now instead of "outside the allowed directories"?
2. **`print` in a tool.** Add `print("debug")` inside `shift`. Run the check. Why does the session fail
   and not just print a line? (stdout is the protocol channel.)
3. **Check before resolving.** Change `resolve()` to test `".." in path` and only then resolve. Find a path
   that escapes anyway (hint: an absolute path, or a symlink inside the allowed folder).
4. **Skip the atomic replace.** Write straight to the destination and kill the process half-way
   (simulate with an exception after writing half the bytes). What is left on disk?
5. **A race.** Two clients call `shift` with the same output name at the same moment. Both pass `dest.exists()`. What
   happens? Fix it with `os.open(dest, os.O_CREAT | os.O_EXCL)` the way the full server does.
6. **A tool description that lies.** Delete `shift`'s docstring. What does `list_tools` return, and how would
   an agent decide when to call it?
7. **Add a tool.** Add `read_cues(path, start_cue, end_cue)` and extend the check. Which parts of the
   guard rails does it inherit for free from `load()`?
