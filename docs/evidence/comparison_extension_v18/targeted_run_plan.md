# V18 Targeted Run Plan

Status: `OFFLINE_COMPARISON_COMPLETE_NO_NEW_ENCRYPTED_RUN_REQUIRED`

No exact external comparison cell is missing. The existing V8 HEIR
shared-polynomial arm is portable-exact, the EVA arm is output-comparable, and
the CoreLab rows are explicitly numerical-only. Repeating any of those records
would not increase comparator eligibility.

The decision-gate selection replay is complete for 68/68 primary cases. A
different question, the candidate-specific separate-input behavior of the 21
gate-off literals rejected during selection, is unavailable because V17 did not
promote those literals to that stage. V18 reports the observed 47/68
intersection and marks 21 outcomes `NOT_EVALUATED`. It does not impute them.
Running all 21 would exceed the fast-extension limit of 12 cases, and such an
internal counterfactual run is not one of the protocol's permitted exact
external targeted executions.

Planned new atomic cases: **0**. Planned new encrypted candidate evaluations:
**0**. Existing V17 and V8 encrypted records remain byte-identical.
