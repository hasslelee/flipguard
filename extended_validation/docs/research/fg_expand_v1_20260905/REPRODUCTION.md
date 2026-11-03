# Reproduction and provenance

This package evaluates the final journal paper's existing configuration selector. It is a completed-run evidence package, not a command that may overwrite a completed run. All execution used `/home/ckks2/deciprotect`; no predecessor interpreter, experiment or cache was run in `/home/ckks2/flipguard`.

## Identifiers and source

- Protocol: `protocols/FG_EXPAND_V1.json`, ID `FG_EXPAND_V1_20260905`.
- Run: `results/fg_expand_v1_20260905_run01`.
- Starting repository HEAD: `afd0a603866002de013bb2981b5f14bd8f2b1ee9`, initially clean worktree.
- Final PDF: `baseline/journal_final_20260905.pdf`, SHA-256 `0210899a12ff1025db358e1812159ca4af2b5c6095a79e2b7b19200d7e9f3b85`; existing copy/freeze correspondence is in `PDF_PROVENANCE.json`.
- Reused source: `research/selection_extension/SOURCE_BINDING.json` identifies 279 byte-identical copied files, including all 274 `internal/` files, from `baseline/source` at copied-source HEAD `67251c57ca7be5aa8aeffd746a6a6671685e98c5`. The original training script is separately hash-bound there. The new native command only orchestrates unchanged functions.
- Before encryption, `RUN_LOCK.json` bound source, binary, protocol, models, role CSVs and environment. Two append-only `SOURCE_AMENDMENT_*.json` records correct the Python orchestration reader/classification; original lock and all failed preflight artifacts remain. Native source/binary, data/models and method did not change.
- `plaintext/manifest.json` and each case's `manifest.json` bind source ZIP URL/hash, deduplication, row IDs, split roles, model SHA-256, training warnings/quality and the protocol hash. Source UCI ZIPs remain local; model and exact derived raw-feature CSV inputs are in the new evidence package.

## Commands actually used

The native build ran from `research/selection_extension`:

```bash
GOMAXPROCS=4 go build -o /home/ckks2/deciprotect/bin/fg-expand-case ./cmd/fg-expand-case
```

The new adapter, lock and orchestration ran from `/home/ckks2/deciprotect`:

```bash
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python scripts/build_fg_expand_v1.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_fg_expand_v1.py lock
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_fg_expand_v1.py preflight
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/run_fg_expand_v1.py run
```

These are historical commands, **not instructions to run them again in the frozen output path**. Preflight emitted all four preserved case artifacts before the evidence-reader column-name error; the amended reader then verified those existing artifacts without repeating encryption. One fixed development pair had no applicable input and therefore generated no keys. `PREFLIGHT_VERIFICATION.json` records three executed smoke trials and the fourth static/materialization check. The amendment records give the actual sequence and limitations.

The fourth native preflight failure retains `stage="synthesis"`, the last stage label set by that wrapper before constructing the development-pair contract. The exact error says the validation pair has no certifiable sample above margin floor 0.001. It is not evidence of a failed CKKS encryption or an empty full selection set; the completed static full-selection plan and finite set are preserved beside it.

That preserved failed process's `.resource.json` is the unedited `/usr/bin/time` output: a nonzero-exit diagnostic line followed by one JSON line. It is not a standalone valid JSON document. Main-run resource files contain only JSON because those processes completed successfully. Parse the final JSON line for the failed preflight resource record; do not rewrite the raw file to hide the failure.

Every native invocation, exact model/input/output path, execution order and before/after environment is stored in `preflight/events.jsonl` and `run/events.jsonl`. Native logs and `/usr/bin/time` resource records are beside the case directories. Go 1.25.9, Lattigo 6.2.0 and the independently installed Python environment were used. Native processes ran serially with GOMAXPROCS=4; NumPy/BLAS thread limits were 1. No other large experiment was launched during timing. Desktop activity and existing VM load were not assumed absent.

## Evidence map

Within each main case directory:

| File | Evidence |
|---|---|
| `selection_contract.json`, `initial_plan.json` | Model/input digests, graph, fixed policies, initial parameters |
| `selection.json` | Actual bounded candidate trials, keys and per-input scores/flags |
| `finite_candidates/*.json`, `exhaustive.json` | Entire original finite candidate set; individual wall costs and objective choices |
| `FROZEN_SELECTION_ROLES.json` | Four comparator choices fixed before independent input materialization |
| `independent_contract.json`, `audit_candidates/*.json` | All 256 separate inputs under three new keys per unique chosen candidate |
| `audit_role_bindings.json` | Explicit aliases when comparator roles share an identical candidate audit |
| `paired_latency/keyset_*.json` | Three fresh parameter-compatible keysets per role, setup and all measured row/pass/order records |
| `stage_timing.json` | Materialization, synthesis, bounded selection, finite search and paired timing wall costs |
| `COMPLETED.json` | Durable completion; scientific rejection is not an infrastructure failure |

Key repeats are context labels, not saved secret keys or cryptographically verifiable key fingerprints. The original library creates fresh keys on each context construction; keys are not uploaded. Different parameter arms use separately generated compatible keys. Same candidate IDs share an audit only where the role-binding file explicitly says so; timing retains separate role arms and keys.

The scalar tabular backend processes one input at a time, with one ciphertext per selected feature and repeated scalar slot values. It does not pack 32/256 independent inputs together. It decodes the intermediate scalar and final score as the original implementation does. The PDF inference timer starts before encoding/encryption and ends after decryption/decoding, before decision/error bookkeeping. The small residual beyond the three recorded components is local call/timer overhead, not network cost. Setup includes parameter/context/key preparation and is reported separately. Selection wall cost includes setup, evaluation, checks and orchestration. Finite search and direct selection are executed in fixed sequential stages, so their wall-time ratio is descriptive, not a randomized latency trial.

Timing uses 20 deterministically spaced positions in the sorted 256-row separate set, selected by the unchanged backend. Warmup=1 and measurement=6 for every arm/keyset. Rows, passes and order are recorded. There is no outlier removal. Warmup input calls are counted separately; per-input warmup timing records are not saved by the unchanged backend. The network, service queue and remote transport are unimplemented/unmeasured (`null`), not zero-latency components.

## Read-only recomputation

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/analyze_fg_expand_v1.py --check
```

This verifies the raw manifest and source amendment chain; reconstructs model scores from raw feature rows; checks role disjointness, policy/security identity, trial acceptance, candidate choices, row/key denominators and matched timing; and recomputes the published summary. Missing ignored local binaries in a clean clone skip only the binary-byte check, explicitly recorded in the verifier output structure; source hashes still must match. Float comparison permits only numerical roundoff, while raw files remain byte-hash checked. No CKKS is executed by this command.

`RAW_SHA256SUMS.json` freezes newly produced raw files after all cases finish. Existing baseline/archive payloads are not rehashed by this verification. `candidate_and_audit_results.csv`, `inference_costs.csv` and `summary.json` are derived from those raw observations. Validation, preservation checks and the final changed-file list are in `VALIDATION.json` and `PRESERVATION.json`.

The historical root verifier gained only an optional `--check` mode so CI can compare the recomputed old results to `docs/research/VERIFICATION.json` without rewriting a completed report. Its arithmetic and original default invocation are unchanged. Historical DP checks do not contribute samples or guarantees to the new selector experiment.

A new encrypted repeat requires a new protocol/run ID, source/input binding and an adapter pointing to fresh output paths. The present scripts deliberately refuse existing output roots. Exact CKKS scores need not be bitwise reproducible because fresh keys and encryption randomness are generated. No next dataset/model/queue experiment is started by verification or by completing this run.
