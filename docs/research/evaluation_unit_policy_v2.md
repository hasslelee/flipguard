# Evaluation Unit and Seed-Role Policy V2

Status: FROZEN FOR THE V2 CONFIRMATORY PROTOCOL

## Official terminology

The tabular matrix contains:

- 10 dataset-model workloads;
- five deterministic repeated partitions of each fixed held-out artifact;
- 50 workload-partition instances in total.

The protocol must not describe these observations as independent dataset
splits, independent models, or independent workloads.

## Partition roles

- Partition seed 0 is the development and ablation partition.
- Partition seeds 1-4 are post-freeze repeated-partition evaluation.
- Every partition audit is a no-retuning locked audit.
- Seed 0 is reported separately as descriptive development evidence.
- Formal confirmatory summaries center on seeds 1-4.

The repeated partitions do not establish training-seed, model-training, or
data-generation generalization. The 50 rows are not independent inferential
samples. Interval estimates and comparisons must cluster at the dataset-model
workload level or use an explicitly documented hierarchical summary.

## Independent-seed extension

An independent training/data-split extension remains required for stronger
generalization evidence. It will use at least three independent training or
data-split seeds on two or three representative datasets and will run the
frozen direct selection plus no-retuning locked audit only. It does not repeat
the 1,100-execution bounded catalog.
