# Selection Wall-Clock Scope Note

## Common Population

The final primary table contains 68 rows. Direct selection wall-clock is
available for 66 rows. The two excluded rows are:

1. `mnist_mlp_square_784_100_10_v1`: predecessor-frozen direct selection
2. `mnist_lenet5_small_square_v1`: predecessor-frozen direct selection

Their V17 exhaustive wall clocks exist, but their direct wall clocks do not.
They are excluded from both sides of the common-case analysis.

| Statistic | Value |
|---|---:|
| Common cases | 66 |
| Direct total | 13,754,260.638 ms |
| Exhaustive total | 167,825,454.593 ms |
| Matched aggregate exhaustive/direct | 12.201706730010272 |
| Per-case minimum | 3.6215641715122606 |
| Per-case IQR | [7.493242059725233, 14.95910619899486] |
| Per-case median | 12.398599026421792 |
| Per-case P90 | 16.75655132437581 |
| Per-case maximum | 17.711344385738283 |

Direct missingness is 2/68; exhaustive missingness is 0/68. Units are
milliseconds, verified from the JSON schema, stage-timing records, and Go timer
conversion from microseconds to milliseconds.

## Measurement Boundary

For 65 tabular cases, direct selection timing starts before direct synthesis
and ends after the durable selection result is written. It includes synthesis,
candidate parameter materialization and encrypted execution, fresh-key
generation inside candidate evaluation, encoding/encryption, homomorphic
evaluation, decryption/decoding, decision validation, and any bounded repair
between candidate trials. Input preparation and contract construction occur
before the timer. Independent evaluation is outside it.

For the packed CNN case, contract construction and direct plan synthesis occur
before its selection timer; the timer includes adaptive encrypted candidate
selection and durable output writing. Exhaustive timing for the common cases
includes finite-set construction, all finite candidate executions, and durable
output writing. The P6 direct boundary therefore differs slightly from the 65
tabular rows, which is an additional limitation.

## Historical Ratio

The preserved `13.844078722408751` is:

```text
190,415,067.041 ms exhaustive over 68 rows
------------------------------------------------ = 13.844078722408751
 13,754,260.638 ms direct over 66 rows
```

It is not a median and not a matched-case comparison. It may appear only as a
qualified historical aggregate. It is unsuitable as the primary headline.

## Paper Recommendation

Use candidate evaluations (89 vs 537) as the primary search-efficiency result.
If selection time is reported, use the 66-case per-case median
`12.3985990264` with IQR `[7.4932420597, 14.9591061990]`, and provide the
matched aggregate `12.2017067300` as total-time accounting. State the timer
boundary caveat. Do not use `13.8441` without its unequal 68/66 population.
