# FlipGuard Repository Instructions

FlipGuard long-running autonomous execution uses claim-level fail-closed
semantics and pipeline-level continuation. Scientific negative results
(`REJECTED`, `NO_SAFE`, locked-audit violation) are preserved and lower the
corresponding claim but do not stop independent downstream stages.

Normal pause occurs only after the configured autonomous work window.
Immediate stop is reserved for integrity, security, destructive, or
unrecoverable infrastructure failures. `PAUSE_AT_FIRST_STAGE_FAILURE` applies
only to an `INTEGRITY_BLOCK` or an infrastructure failure that remains
unrecoverable after the declared retry budget.

Never retune the frozen Direct Policy V2 or Security Policy V2 from
confirmatory or locked-audit results. Never overwrite an existing frozen
evidence pack.
