# Executed source and later reporting source

The parent checkpoint is `b64fa9c100f4f13789e3012a8e2258a48034f5d0`.
New experiment source was not yet committed at execution time; exact source and
binary SHA-256 values are therefore authoritative alongside that parent, not a
claim that the new code was already contained in the parent commit.

`TRAINING_SOURCE_LOCK.json` was captured before training. Its full file list
also included unrelated planner packages. `TRAINING_LOCK_SCOPE_CHECK.json`
identifies two later changes to `internal/ckksplanner/contract.go` and
`multiclass_contract.go` made while completing the Fashion contract connection
before the main source lock. The trainer command, compiled trainer, original
`journalmnist/mlp.go`, and optimizer match the training lock. The trainer's
local import graph contains only the command and `journalmnist`, not those
planner packages (`TRAINER_DEPENDENCY_CHECK.json`). No claim is made that every
file in the broader training-time directory still has the old hash.

The literal seed 1 `--source-commit` argument contains a duplicated substring.
`SOURCE_ID_CORRECTION.json` records the typo and actual parent. The descriptive
field in the model was preserved, as were all weights and training observations.
It does not identify a different training run or silently repaired artifact.

`MAIN_SOURCE_LOCK.json` binds the native binaries, copied source, protocols,
models, quality thresholds, input CSVs, and initial Python runner. Subsequent
amendments are append-only:

1. `MAIN_SOURCE_AMENDMENT_01.json` records a serial-execution guard after a new
   Fashion attempt overlapped the separately authorized external comparison.
   Only that new Fashion process was interrupted. It produced no completed key
   checkpoint. The attempted command and its cost are retained. The external
   selection timing is diagnostic because part of it overlapped.
2. `MAIN_SOURCE_AMENDMENT_02.json` corrects the Python numerical reader from
   `plain_logits` to the native field `plaintext_logits`. Already completed
   encrypted candidates were reused. The already loaded amendment-01 process
   was allowed to finish the seed 0 finite candidates and then stopped at the
   expected reader exception; `READER_RECOVERY.json` records the bounded resume.

The intermediate runner source was copied before amendment 02. The initial
runner snapshot was reconstructed from that source and verified against the
original lock's exact SHA-256 before being saved; it is not claimed to be a
separately timestamped file capture from the initial launch. Python traceback
source lines can reflect the newer file on disk while the old loaded code
raises the exception. These source snapshots explain that otherwise confusing
field-name display without replacing the original error log.

The native CKKS executable and policies did not change across these two Python
amendments. The independent analysis/report scripts were completed as evidence
became available and have their own publication hashes. They do not alter the
selected configurations, native ciphertext computation, thresholds, or raw
observations. `ANALYSIS_TIME_BOUNDARIES.json` was recorded before audit/paired
execution to retain both the native total and the final PDF's three-component
inference-time definition.

The exact already-executed EVA helper is published under the new module's
`external/` directory and hash-matches the independently copied work helper.
The official provider binary remains ignored/local; its source commit, build
origin, runtime hashes and image identity are preserved in the external source
bindings. No predecessor interpreter or original working tree was used to run
these experiments.
