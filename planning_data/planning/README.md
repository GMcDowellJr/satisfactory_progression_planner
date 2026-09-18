# Planning Layer

This layer is downstream of game reference and world analysis. It should answer **what to build, how much, where, when, and why** rather than reproduce machine-count solvers.

- `model/` defines reusable semantics.
- `plans/` contains geography-specific planning inputs/reference plans.
- `strategies/` contains build-style and progression preferences.
- `playthroughs/` contains mutable save/run state.
- `templates/` contains reusable table shapes.
- `legacy/` contains transitional inputs from the pre-world-socket architecture.

Rocky Desert remains the primary reference implementation and validation case, not a source of canonical world facts.
