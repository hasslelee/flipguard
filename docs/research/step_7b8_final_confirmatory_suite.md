# Step 7B.8 Final Confirmatory Suite

Status: STATIC PREFLIGHT IMPLEMENTED; ENCRYPTED CONTINUATION BLOCKED on
2026-07-29.

## Purpose

The final evidence cannot be assembled by running independent commands against
different working-tree states. This suite binds all remaining confirmatory
experiments to one immutable source commit and freezes each result through its
independent verifier.

The suite runs, in order:

1. Security Policy V2 static re-attestation;
2. security-compliant bounded-oracle re-summarization;
3. clean direct-policy freeze commit and push;
4. final suite `--preflight-only`;
5. clean-source primary delta-0.001 direct selection;
6. clean-source no-retuning locked audit, with seeds 1-4 formal and seed 0
   descriptive;
7. confirmatory `NO_SAFE` controls;
8. full `mlp_square_poly3` structural holdout;
9. final paired latency over V2-frozen arms;
10. independent training/model-seed extension;
11. at least one non-tabular image/CNN graph;
12. final evidence freeze and deterministic verification;
13. `FINAL_ADMISSIBLE` paper artifact build.

The confirmatory `NO_SAFE` pack preserves the original retrospective
finite-domain result separately from its disjoint locked-audit rerun. The
suite succeeds only if the declared two-candidate audit domain contains no
SAFE candidate on all 50 workloads; a completed falsification remains in the
result directory as `control_result=FAIL`.

## Clean-Source Gate

The command refuses any modified or untracked file under:

```text
cmd/
internal/
scripts/
go.mod
go.sum
```

Generated results and evidence directories are outside this source gate. Every
clean-run protocol records `git rev-parse HEAD`, exact source-file hashes, and
a composite source digest. Challenger and structural freezers reject a
protocol whose commit, file hashes, or composite digest differ from the
declared evidence commit.

The 50 baseline and 25 structural workload-partition instances use
`--materialize-model-input` for both selection and locked audit. Each
partition binds the source split CSV, recomputed canonical CSV, preprocessing
contract, and `source_replay_verified=true`. Their evidence packs snapshot
the model artifact, upstream source test CSV, and all four source/prepared
partition CSVs. Model and source-test snapshots are deduplicated across split
seeds. The final paper builder rejects any of these three packs when even one
workload lacks either replay chain.
Audit materialization only recomputes plaintext score/decision provenance; it
does not invoke synthesis, repair, or parameter selection, so the no-retuning
contract is unchanged.

On resume, an existing evidence pack is accepted only when its recorded source
commit equals the suite's current commit. A stale pack requires an explicit
`--force` rerun.

## Commands

Check source cleanliness and all prerequisite evidence without starting
encrypted workloads:

```bash
scripts/run_thesis_final_confirmatory_suite.sh --preflight-only
```

Run or safely resume the final suite:

```bash
scripts/run_thesis_final_confirmatory_suite.sh --resume
```

Rerun valid workload artifacts and replace all four confirmatory evidence
packs:

```bash
scripts/run_thesis_final_confirmatory_suite.sh --force
```

`--skip-regression` is available only for resuming after the same source
commit has already passed the full regression phase. It does not bypass any
experiment-level semantic verifier.

## Expected Evidence

```text
docs/evidence/direct_locked_audit_final_source_v1/
docs/evidence/no_safe_controls_confirmatory_v1/
docs/evidence/structural_extension_v1/
docs/evidence/paired_latency_final_v1/
```

The suite returns success only after every required final pack passes its
verifier.
The selection/audit packs record `evidence_stage=confirmatory`;
checkpoint or non-replayed input evidence cannot receive that stage.
Individual experiment completion is not equivalent to suite completion.

The suite then runs the V2 paper artifact builder in its fail-closed final
profile and independently verifies:

```text
results/thesis_grade_protocol/paper_artifacts_v2/current/
```

Its manifest must report `FINAL_ADMISSIBLE`. A partial or mixed-commit
evidence set cannot produce final paper tables and figures.

## Paper Update Rule

Final paper values must be read from verified evidence manifests and summary
snapshots, never from console output or an intermediate `results/` file.

- Keep primary margin floor `0.001`. Margin floor `0.0005` is secondary
  sensitivity only and its audit cannot select the primary policy.
- Report the confirmatory `NO_SAFE` outcome even if it differs from the
  predeclared exact map; such a mismatch makes the control fail.
- Require the disjoint finite-domain audit to complete 300 fresh-key attempts
  with zero unexpected execution failures and `NO_SAFE=50/50`.
- Promote the deeper-graph pilot only after 25 selections and 25 locked audits
  pass with normalized budget usage below one.
- Report a scoped direct-latency advantage only when the final paired pack
  sets `paper_latency_claim_allowed=true`.

Any failed gate remains a reported result. The suite must not delete,
relabel, or replace it with a successful pilot.
