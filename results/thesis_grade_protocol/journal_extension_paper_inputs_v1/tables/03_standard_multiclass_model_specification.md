# Standard multiclass model specification and controlled graph scale

| Model | Architecture | Plaintext test accuracy | Packing scope | Activation | Claim boundary |
| --- | --- | --- | --- | --- | --- |
| MLP-100 | 784 -> 100 -> square -> 10 | 0.9776 | feature ciphertext sample slots | square | no packed-production claim |
| LeNet-5-small | conv6 -> avgpool -> conv16 -> avgpool -> FC120 -> FC64 -> 10 | 0.9891 | feature ciphertext sample slots | square after conv/FC | FHE-compatible disclosed adapter |

## Controlled graph-scale points

| Scale point | Input | Hidden | Outputs | Add ops | Mul ops | Rescales | Depth | LogN | Q | Scale | Trials | Repairs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Primary MLP-4 | 4/8/16 | 4 | 1 | 20-68 | 24-72 | 1 | 1 | 13 | 6 | 20 | 1 | 0 |
| MNIST MLP-100 | 784 | 100 | 10 | 79400 | 79500 | 1 | 1 | 13 | 5 | 29 | 1 | 0 |
| MNIST LeNet-5-small | 784 | conv6/16; FC120/64 | 10 | 418648 | 421984 | 4 | 4 | 15 | 18 | 44 | 1 | 0 |
