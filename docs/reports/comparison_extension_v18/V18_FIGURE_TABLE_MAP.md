# V18 Figure and Table Map

| Manuscript item | Locked source | Main message | Required qualification |
|---|---|---|---|
| Gate cross table | `V18_GATE_EFFECT_TABLE.csv` | 47 neither, 0 flip-only, 1 violation-only, 20 both | case is the statistical unit |
| Stability cost table | `V18_STABILITY_COST_TABLE.csv` | 68 vs 89; 21 one-step recoveries; literal before/after | candidate latency is selection-stage observational |
| Traditional objective table | `V18_TRADITIONAL_OBJECTIVE_DIAGNOSTICS.csv` | 18 unstable fastest; 28 unstable Pareto candidates | minimum-error is stable 68/68 |
| External comparator table | `V18_EXTERNAL_COMPARISON_TABLE.csv` | exact/output/numerical/related-work separation | no raw cross-runtime speed ranking |
| Figure: gate-state composition | `V18_GATE_EFFECT_TABLE.csv` | union=21 | do not plot raw flip events as independent samples |
| Figure: configuration delta | `V18_STABILITY_COST_TABLE.csv` | scale +4; prime count/LogN unchanged | distinguish Q bit-width from Q-prime count |
| Figure: candidate objective plane | existing `figure_error_latency_decision_overlay.csv` plus locked diagnostics | unstable fastest/Pareto candidates | diagnostic, not named-system emulation |
| Figure: finite-reference quality | existing `figure_proposed_vs_finite_latency_gap.csv` plus locked JSON | near-reference regret and CI | no superiority claim |

All headline values must be read from `PAPER_FACTS_V18_LOCKED.json`; prose may
round only after retaining the ratio direction and statistical unit.
