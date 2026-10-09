# 0005 — Homebrew libomp + single-process OpenMP smoke test

**Date:** 2026-10-10 · **Status:** Accepted

## Context
`otool` on the installed wheels shows that LightGBM 4.7.0's `lib_lightgbm.dylib` links
`@rpath/libomp.dylib` with rpath `/opt/homebrew/opt/libomp/lib`, while scikit-learn 1.9.1
bundles its own `sklearn/.dylibs/libomp.dylib`. Two OpenMP runtimes in one process can
abort with "OMP: Error #15" (see the LightGBM FAQ).

## Decision
Install keg-only Homebrew `libomp` (no symlinks, no LDFLAGS changes). `sepsiscope doctor`
and `tests/test_smoke.py` fit scikit-learn **and** LightGBM in the **same** process.
The suite is run three times in a row to catch intermittent crashes.

## Alternatives
`KMP_DUPLICATE_LIB_OK=TRUE`: rejected, it hides the problem and Intel warns it can give
wrong results. Compiling LightGBM from source: unnecessary.

## Consequences
If a future upgrade causes the clash, the smoke test fails loudly before any real work.

## Sources
[LightGBM FAQ](https://lightgbm.readthedocs.io/en/stable/FAQ.html) ·
[libomp formula](https://formulae.brew.sh/formula/libomp)
