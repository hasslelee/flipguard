# Workload, model, and input scope

Scopes are finite and adapter-specific.

| Evidence family | Declared scope | Inference unit |
| --- | --- | --- |
| Primary tabular | 5 datasets x 2 models x 5 partitions | 10 dataset-model clusters |
| Structural polynomial | mlp_square_poly3; 5 datasets x 5 partitions | 25 workload-partition instances |
| Sobel | BSDS500 finite single-patch scalar-replicated inputs | 50 image clusters per role |
| Harris | BSDS500 finite single-window scalar-replicated inputs | 50 image clusters per role |
| CNN-lite | MNIST digit-0-vs-1 scalar-replicated graph | 250 images per role |
| Independent training seed | 3 datasets x 3 training/data seeds | trained model instance grouped by dataset |
