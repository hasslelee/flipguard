# FlipGuard Tabular Certification Report

## Reconstruction

- Run-status source: `results/ckks_tabular_profile_sweep_repeated/run_status.csv`
- Raw status rows: `684`
- Latest unique run tags: `660`
- Duplicate tags resolved by last-row semantics: `24`
- Workloads: `10`

## Aggregate Outcome

- Workloads with a selected SAFE configuration: `10/10`
- Workloads with NO_SAFE: `0`
- Candidates: `220` (`SAFE=150`, `REJECTED=60`, `FAILED=10`, `AMBIGUOUS=0`)
- Validation coverage totals: `V_cert=2645`, `V_amb=61`
- Workloads where latency-only would choose a non-SAFE candidate: `10`

## Workload Results

| Workload | Outcome | V_cert | V_amb | SAFE | REJECTED | FAILED | Selected | Path | Mean total ms | Speedup vs reference | Latency-only status |
|---|---|---:|---:|---:|---:|---:|---|---|---:|---:|---|
| banknote__linear_poly3 | SELECTED | 412 | 0 | 12 | 8 | 2 | default__rescale_aware | rescale_aware | 119.330279396 | 1 | REJECTED |
| banknote__mlp_square_linear_score | SELECTED | 412 | 0 | 18 | 4 | 0 | short_chain_6_scale40__baseline_non_rescale | baseline_non_rescale | 170.193720447 | 1.20666487121 | REJECTED |
| digits_binary__linear_poly3 | SELECTED | 530 | 10 | 12 | 8 | 2 | default__rescale_aware | rescale_aware | 176.299848346 | 1 | REJECTED |
| digits_binary__mlp_square_linear_score | SELECTED | 505 | 35 | 18 | 4 | 0 | short_chain_6_scale38__baseline_non_rescale | baseline_non_rescale | 227.277474201 | 1.18851593561 | REJECTED |
| iris_binary__linear_poly3 | SELECTED | 30 | 0 | 12 | 8 | 2 | default__rescale_aware | rescale_aware | 120.027799378 | 1 | REJECTED |
| iris_binary__mlp_square_linear_score | SELECTED | 30 | 0 | 18 | 4 | 0 | short_chain_6_scale42__baseline_non_rescale | baseline_non_rescale | 169.097464467 | 1.20604394144 | REJECTED |
| mnist_pool16__linear_poly3 | SELECTED | 195 | 5 | 12 | 8 | 2 | default__rescale_aware | rescale_aware | 312.71718244 | 1 | REJECTED |
| mnist_pool16__mlp_square_linear_score | SELECTED | 197 | 3 | 18 | 4 | 0 | short_chain_6_scale42__baseline_non_rescale | baseline_non_rescale | 349.33005016 | 1.18769071427 | REJECTED |
| wdbc__linear_poly3 | SELECTED | 169 | 2 | 12 | 8 | 2 | default__rescale_aware | rescale_aware | 182.713050938 | 1 | REJECTED |
| wdbc__mlp_square_linear_score | SELECTED | 165 | 6 | 18 | 4 | 0 | short_chain_6_scale38__baseline_non_rescale | baseline_non_rescale | 230.95318537 | 1.29520842882 | REJECTED |

## Claim Boundary

Every SAFE result is an observed-validation certificate restricted to the recorded validation split and its `V_cert` subset. Samples with margin less than or equal to the configured margin floor belong to `V_amb` and are not covered by the decision-stability claim.
