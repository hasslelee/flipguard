# Fairness limitations

- Native EVA/SEAL, HEIR/OpenFHE, and CoreLab/SEAL timings are runtime-specific panels; no cross-runtime speed ratio is admitted.
- The common Lattigo harness links HEIR's generated evaluator without changing its schedule and interleaves it with FlipGuard direct/catalog arms, but the arms necessarily use parameter-compatible independent keys. Eight decision flips on one near-threshold input in the direct arm make all common-harness latency ratios diagnostic only.
- CoreLab's official LinearRegression graph has no natural frozen threshold output, so it contributes numerical multi-input evidence rather than a decision-integrity claim. Seventy plans completed; `elasm_36` and `elasm_41` failed before producing rows.
- `PORTABLE_EXACT` applies only to the frozen HEIR-generated Lattigo arm on the exact shared polynomial; it is not a general compiler-portability claim.
- All safety observations are finite-scope validation and locked-audit results, not distribution-wide or analytical guarantees.
