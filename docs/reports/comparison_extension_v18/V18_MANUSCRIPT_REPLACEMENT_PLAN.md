# V18 Manuscript Replacement Plan

1. Replace any finite-reference-as-practical-baseline wording with “offline
   finite reference for missed feasibility and selection-quality measurement.”
2. Lead the result section with the 47/0/1/20 gate cross table. State that the
   union contains 21 cases and list the case-level CSV as artifact support.
3. Follow with the 68-versus-89 evaluation cost and 21/21 one-step recovery.
4. State that scale increased by four bits in 21 cases, but Q-prime count,
   Q-chain length, and LogN did not change. Do not describe this as +1 Q prime.
5. Label full/gate-off candidate latency as selection-stage observational.
   Formal gate-off/full selection wall-clock and formal inference latency are
   not available.
6. Report gate-off separate-input results as 47 PASS and 21 NOT_EVALUATED. Do
   not combine NOT_EVALUATED with REJECTED or FAILED.
7. Use the traditional-objective diagnostic to show 18 unstable fastest
   candidates and 28 unstable Pareto candidates, while disclosing that the
   minimum-error candidate was stable in all 68 cases.
8. Put HEIR and EVA in separate exact/output-comparable rows. Keep the HEIR
   latency as blocked diagnostic and EVA latency native-runtime-only.
9. Report both normalized regret and absolute median-total difference. Explain
   that absolute milliseconds are heterogeneous across model families.
10. Conclude with near-reference selection quality; do not claim superiority,
    global optimality, or improvement over all CKKS tuners.

No V17/V18 number is replaced in-place by this plan. Manuscript editing consumes
the locked JSON and CSV overlay in a later stage.
