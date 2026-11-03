# Policy and margin-utilization sensitivity

Invariance in the tested range is not evidence that rho=0.5 is optimal.

| Quantity | Result | Interpretation |
| --- | --- | --- |
| rho grid | 0.1, 0.25, 0.5, 0.75, 0.9 | predeclared sensitivity |
| candidate-state changes | 0 | tested primary range |
| bounded-oracle changes | 0 | tested primary range |
| direct initial literal changes | 0 | minimum synthesis floor dominance |
| theorem | e_c(x) < m(x) | sufficient decision preservation |
| operational policy | e_c(x) < 0.5*m(x) | 50% margin utilization cap |
