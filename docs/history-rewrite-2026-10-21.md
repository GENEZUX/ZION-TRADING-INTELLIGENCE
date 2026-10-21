# History rewrite — 2026-10-21

## What happened

During Phase 01 setup, the repository's history was rewritten twice using
`git checkout --orphan`:

1. First rewrite created root commit `276349a`.
2. Second rewrite created root commit `d939ad9`, which is the current `master`.

The original three-commit history — `809da2a`, `1b304cb`, `2012420` — is no
longer on any branch. It remains recoverable via `git reflog` for approximately
90 days from 2026-10-21.

## Recovery

    git -C /e/SAION/ZION-TRADING-INTELLIGENCE reflog
    # find 2012420 in the output
    git -C /e/SAION/ZION-TRADING-INTELLIGENCE branch old-history 2012420

## Current state

- `master` = `d939ad9` — "Phase 01: ... (v1.2)"
- Single root commit
- 16 files versioned at time of rewrite
