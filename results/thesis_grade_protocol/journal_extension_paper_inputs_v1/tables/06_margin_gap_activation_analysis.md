# Natural top-two-gap activation analysis

| Study | Result | Literal changed | MLP graph-only | LeNet graph-only | Claim boundary |
| --- | --- | --- | --- | --- | --- |
| natural_data_margin_literal_effect | A_LITERAL_EFFECT_SUPPORTED | True | SAFE | PLAN_UNSUPPORTED_SECURITY_ENVELOPE | MNIST MLP 784-100-square-10 configuration-validation rows only |

| Model | Role | Gap bin | Unique samples | Key observations | Flips | Reserve rejects | Min gap | Max gap | Max cap required |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lenet5_small | configuration_validation | 1 | 100 | 300 | 0 | 0 | 0.019203927749238403 | 9.7172808216168551 | 8.9320504796847806e-07 |
| lenet5_small | configuration_validation | 2 | 100 | 300 | 0 | 0 | 9.7557645193887517 | 14.808019533521611 | 5.0368093004257502e-09 |
| lenet5_small | configuration_validation | 3 | 100 | 300 | 0 | 0 | 14.814201086842942 | 20.20724596255717 | 6.0025204220738236e-09 |
| lenet5_small | configuration_validation | 4 | 100 | 300 | 0 | 0 | 20.304280615944499 | 28.382984961761927 | 3.2844503282527147e-09 |
| lenet5_small | configuration_validation | 5 | 100 | 300 | 0 | 0 | 28.45668277629531 | 62.000131048226692 | 3.0715763809468462e-09 |
| lenet5_small | locked_audit | 1 | 118 | 354 | 0 | 0 | 0.36079731807418303 | 9.7352368738957544 | 3.1632967056565881e-08 |
| lenet5_small | locked_audit | 2 | 108 | 324 | 0 | 0 | 9.7634448562717218 | 14.808725379207548 | 6.3682172841716518e-09 |
| lenet5_small | locked_audit | 3 | 90 | 270 | 0 | 0 | 14.87479591692118 | 20.182665040382883 | 4.1449973845965703e-09 |
| lenet5_small | locked_audit | 4 | 83 | 249 | 0 | 0 | 20.267436209419444 | 28.284680001428786 | 3.4927283614987135e-09 |
| lenet5_small | locked_audit | 5 | 101 | 303 | 0 | 0 | 28.573139086544728 | 84.443916357702605 | 3.5245783615074059e-09 |
| mlp_100 | configuration_validation | 1 | 100 | 300 | 0 | 0 | 0.042498195165657116 | 7.2213641755655624 | 0.0018313528165830159 |
| mlp_100 | configuration_validation | 2 | 100 | 300 | 0 | 0 | 7.232831498858916 | 10.565880261886502 | 3.369672822033873e-05 |
| mlp_100 | configuration_validation | 3 | 100 | 300 | 0 | 0 | 10.624206311276389 | 15.216304998358616 | 1.8602746311815759e-05 |
| mlp_100 | configuration_validation | 4 | 100 | 300 | 0 | 0 | 15.225706650551137 | 22.015026582911048 | 1.7523556874231832e-05 |
| mlp_100 | configuration_validation | 5 | 100 | 300 | 0 | 0 | 22.047234793427801 | 58.965385342865808 | 1.2267303771479789e-05 |
| mlp_100 | locked_audit | 1 | 99 | 297 | 0 | 0 | 0.012545230086129955 | 7.2202916180179626 | 0.0029057998080674629 |
| mlp_100 | locked_audit | 2 | 91 | 273 | 0 | 0 | 7.227685153823451 | 10.512526004739735 | 2.4198752086014364e-05 |
| mlp_100 | locked_audit | 3 | 111 | 333 | 0 | 0 | 10.598107448334854 | 15.078770946049396 | 1.709123533856808e-05 |
| mlp_100 | locked_audit | 4 | 94 | 282 | 0 | 0 | 15.225316492964337 | 22.015357547683994 | 1.9937284236706704e-05 |
| mlp_100 | locked_audit | 5 | 105 | 315 | 0 | 0 | 22.152420101704731 | 47.57540568670899 | 1.3764682184559224e-05 |
