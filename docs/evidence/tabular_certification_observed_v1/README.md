# Tabular Certification Evidence — Observed Validation v1

## Identity

- Source commit: `f113cddc16a02cb62bbcd29abcd1a04cfa2b15d6`
- Source commit time: `2026-07-16T14:46:13+09:00`
- Experiment: `ckks_tabular_certification`
- Structural summary SHA-256: `49e7436454e96a2230f7889c4ba1586aa9784e146f236ce6906fa8b33a1583b6`
- Source run-status SHA-256: `720321c15ef793e5fa74072ec71899077d75de080b4038936db779995237a42a`

## Scope

- Datasets: `5`
- Models per dataset: `2`
- Workloads: `10`
- Candidates per workload: `22`
- Repetitions per candidate: `3`
- Latest run tags: `660`
- Margin floor: `0.001`
- Safety factor: `0.5`
- Assurance: `OBSERVED_VALIDATION`

## Official Result

- Selected SAFE workloads: `10/10`
- Candidate certificates: `220`
- SAFE: `150`
- REJECTED: `60`
- FAILED: `10`
- AMBIGUOUS candidates: `0`
- Validation samples: `2706`
- V_cert: `2645`
- V_amb: `61`
- Selected-candidate V_cert flips: `0`
- Selected-candidate V_cert violations: `0`
- Workloads where latency-only selected a non-SAFE candidate: `10/10`

## Selected Configurations

| Workload | Candidate | Path | Assurance | Mean total ms | Speedup vs reference | V_cert | V_amb |
|---|---|---|---|---:|---:|---:|---:|
| banknote__linear_poly3 | default__rescale_aware | rescale_aware | OBSERVED_VALIDATION | 119.330279396 | 1 | 412 | 0 |
| banknote__mlp_square_linear_score | short_chain_6_scale40__baseline_non_rescale | baseline_non_rescale | OBSERVED_VALIDATION | 170.193720447 | 1.20666487121 | 412 | 0 |
| digits_binary__linear_poly3 | default__rescale_aware | rescale_aware | OBSERVED_VALIDATION | 176.299848346 | 1 | 530 | 10 |
| digits_binary__mlp_square_linear_score | short_chain_6_scale38__baseline_non_rescale | baseline_non_rescale | OBSERVED_VALIDATION | 227.277474201 | 1.18851593561 | 505 | 35 |
| iris_binary__linear_poly3 | default__rescale_aware | rescale_aware | OBSERVED_VALIDATION | 120.027799378 | 1 | 30 | 0 |
| iris_binary__mlp_square_linear_score | short_chain_6_scale42__baseline_non_rescale | baseline_non_rescale | OBSERVED_VALIDATION | 169.097464467 | 1.20604394144 | 30 | 0 |
| mnist_pool16__linear_poly3 | default__rescale_aware | rescale_aware | OBSERVED_VALIDATION | 312.71718244 | 1 | 195 | 5 |
| mnist_pool16__mlp_square_linear_score | short_chain_6_scale42__baseline_non_rescale | baseline_non_rescale | OBSERVED_VALIDATION | 349.33005016 | 1.18769071427 | 197 | 3 |
| wdbc__linear_poly3 | default__rescale_aware | rescale_aware | OBSERVED_VALIDATION | 182.713050938 | 1 | 169 | 2 |
| wdbc__mlp_square_linear_score | short_chain_6_scale38__baseline_non_rescale | baseline_non_rescale | OBSERVED_VALIDATION | 230.95318537 | 1.29520842882 | 165 | 6 |

## Files

- `manifest.json`: machine-readable provenance and scope
- `source_run_status.csv`: exact ignored status source used for reconstruction
- `outputs/certificates.csv`: all 220 candidate certificates
- `outputs/workload_summary.csv`: workload-level outcomes
- `outputs/selected_configurations.csv`: selected SAFE configurations
- `outputs/validation_coverage.csv`: V_cert and V_amb scopes
- `outputs/report.md`: generated certification report
- `SHA256SUMS`: snapshot integrity hashes

## Claim Boundary

A `SAFE` certificate in this snapshot is limited to the recorded validation
split and its `V_cert` subset. It means that the candidate completed all
required executions and exhibited no decision flip or protected error-budget
violation on that subset.

It does not cover `V_amb`, unseen inputs, arbitrary models, arbitrary datasets,
or configurations outside the recorded matrix. No analytical error bound is
included in this evidence version.
