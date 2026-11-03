func.func @shared_polynomial(%x0: f32 {secret.secret}, %x1: f32 {secret.secret}, %x2: f32 {secret.secret}) -> f32 {
  %c08 = arith.constant 8.000000e-01 : f32
  %cn05 = arith.constant -5.000000e-01 : f32
  %c12 = arith.constant 1.200000e+00 : f32
  %cn03 = arith.constant -3.000000e-01 : f32
  %c05 = arith.constant 5.000000e-01 : f32
  %c0197 = arith.constant 1.970000e-01 : f32
  %c0004 = arith.constant 4.000000e-03 : f32
  %a0 = arith.mulf %c08, %x0 : f32
  %a1 = arith.mulf %cn05, %x1 : f32
  %s0 = arith.addf %a0, %a1 : f32
  %a2 = arith.mulf %c12, %x2 : f32
  %s1 = arith.addf %s0, %a2 : f32
  %z = arith.addf %s1, %cn03 : f32
  %z2 = arith.mulf %z, %z : f32
  %z3 = arith.mulf %z2, %z : f32
  %linear = arith.mulf %c0197, %z : f32
  %cubic = arith.mulf %c0004, %z3 : f32
  %offset = arith.addf %c05, %linear : f32
  %neg_cubic = arith.negf %cubic : f32
  %score = arith.addf %offset, %neg_cubic : f32
  return %score : f32
}
