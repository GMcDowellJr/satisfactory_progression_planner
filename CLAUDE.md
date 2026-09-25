# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- **Session artefacts** go in `Claude outputs/`: design notes and session
  handoffs, named `<topic>-<YYYY-MM-DD>[-HHMM].md`. The directory is in
  `.gitignore`, but its existing files are tracked. Add a new file with
  `git add -f` only when Greg wants it on the record.
- **Handoffs:** the file with the newest timestamp in its name is the current
  one. Never edit a handoff after it's written; a revision is a new file.
  Write it last, after commit and push, and record the HEAD you read from
  `.git`, not the one you expected. Keep it self-contained, list at most five
  ranked next actions, and make the part above the fold readable in two
  minutes.
- **In a cloud container** the full suite runs (`uv run pytest -q`), and the
  manifests can be regenerated there (see Manifests above). Report the suite
  result as `Container: N passed, M skipped`. That's not the same measurement
  as a run on Greg's machine.
- Keep scratch work (one-off drivers, recompute models) in the session
  scratchpad or `scratchpad/` (gitignored), never in `tools/`, until it has a
  test and a decision behind it.
