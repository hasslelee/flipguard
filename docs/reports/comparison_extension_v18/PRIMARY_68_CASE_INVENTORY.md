# Primary 68 Case Inventory

Status: `PRIMARY_68_INVENTORY_VERIFIED`

## Unit definition

An evaluation case fixes one dataset, model or computation graph, and split or
training condition, then asks the method to select one CKKS configuration. A
candidate evaluation is a different unit: it executes one candidate over the
case's complete configuration-selection inputs and three independent key sets.
The 68 primary cases therefore do not mean 68 candidate pools or 68 distinct
parameter literals.

## Exact accounting

- Unique primary evaluation cases: **68**
- Gate-off candidate evaluations: **68**
- Full-method candidate evaluations: **89**
- Finite-reference candidate evaluations: **537**
- Changed configurations: **21**
- Exactly one additional candidate evaluation: **21**
- Two or more additional evaluations: **0**
- Scale +4 bit changes: **21**
- Q-prime additions: **0**
- LogN changes: **0**
- Q-chain-length changes: **0**
- Full-method separate-input PASS: **68/68**
- Formal-latency row bindings: **68/68**
- Overall / primary unique parameter literals: **16 / 7**

## Model-family composition

| Internal model ID | Paper-facing family | Cases |
|---|---|---:|
| `linear_poly3` | linear body with cubic output | 25 |
| `mlp_square2_linear_score` | two-hidden-layer square MLP | 15 |
| `mlp_square_linear_score` | one-hidden-layer square MLP | 25 |
| `mnist_lenet5_small_square_v1` | FHE-compatible LeNet-5-small | 1 |
| `mnist_mlp_square_784_100_10_v1` | MNIST MLP-100 | 1 |
| `packed_cnn_lite_binary01_v17` | packed CNN-lite | 1 |

## Dataset-model composition

| Dataset | Model ID | Cases |
|---|---|---:|
| `banknote` | `linear_poly3` | 5 |
| `banknote` | `mlp_square2_linear_score` | 5 |
| `banknote` | `mlp_square_linear_score` | 5 |
| `digits_binary` | `linear_poly3` | 5 |
| `digits_binary` | `mlp_square_linear_score` | 5 |
| `iris_binary` | `linear_poly3` | 5 |
| `iris_binary` | `mlp_square_linear_score` | 5 |
| `mnist_10class` | `mnist_lenet5_small_square_v1` | 1 |
| `mnist_10class` | `mnist_mlp_square_784_100_10_v1` | 1 |
| `mnist_binary01` | `packed_cnn_lite_binary01_v17` | 1 |
| `mnist_pool16` | `linear_poly3` | 5 |
| `mnist_pool16` | `mlp_square2_linear_score` | 5 |
| `mnist_pool16` | `mlp_square_linear_score` | 5 |
| `wdbc` | `linear_poly3` | 5 |
| `wdbc` | `mlp_square2_linear_score` | 5 |
| `wdbc` | `mlp_square_linear_score` | 5 |

## Split composition

| Split or fixed evaluation condition | Cases |
|---|---:|
| `mnist_sha_rank_validation_500_v1` | 2 |
| `outer_fold_0_training_seed_0` | 13 |
| `outer_fold_1_training_seed_0` | 13 |
| `outer_fold_2_training_seed_0` | 13 |
| `outer_fold_3_training_seed_0` | 13 |
| `outer_fold_4_training_seed_0` | 13 |
| `v17_p6_packed_cnn_lite` | 1 |

## Binding

- V18 package payload SHA-256: `884d979087b62a1f4e2ca066902f4deb603589dbff6fd5349c57bead5539aded`
- Case ledger SHA-256: `ffadd57877e8d579ac00445eb702595a1b432225f3ac4b9859882517e7e6ac19`
- V17 selected-configuration table SHA-256: `5c9757d4dd2b8d48e113b633b65ed99b5e21e153d4819cae28b02a26bc38c0cb`
- V17 formal-latency table SHA-256: `a3558bc912ee9f228a46c1243e8270f9fbbcb5a5a44aa67a5a19925eca63ec12`

Every exact case ID, before/after candidate identity, selected literal,
selection result, separate-input outcome, and formal-latency record binding is
preserved in `PRIMARY_68_CASE_INVENTORY.csv`.
