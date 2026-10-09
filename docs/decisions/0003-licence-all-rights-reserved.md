# 0003 — No open-source licence during evaluation

**Date:** 2026-10-10 · **Status:** Accepted

## Context
This is assessed coursework. The author keeps all rights while it is being evaluated.

## Decision
No `LICENSE` file. The README carries the copyright notice (all rights reserved).
Third-party material keeps its own licence in `third_party/` (for example the official
PhysioNet evaluation code, BSD-2-Clause). Data attribution: PhysioNet/CinC Challenge
2019, CC BY 4.0.

## Alternatives
MIT or Apache-2.0 now: rejected until evaluation ends (it can be added later).

## Consequences
Without a licence, others may view the code once it is public but have no right to
reuse it. CC BY 4.0 requires attribution for the data, which the README gives.

## Sources
[GitHub: licensing a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) ·
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) ·
[evaluation-2019 (BSD-2-Clause)](https://github.com/physionetchallenges/evaluation-2019)
