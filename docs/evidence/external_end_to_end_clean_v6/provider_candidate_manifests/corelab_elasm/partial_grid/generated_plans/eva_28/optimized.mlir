module @"traced/LinearRegression.mlir" {
  func.func @_hecate_LinearRegression(%arg0: tensor<1x!ckks.poly<2 * 0>>, %arg1: tensor<1x!ckks.poly<2 * 0>>) -> (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) attributes {arg_level = array<i64: 5, 5>, arg_scale = array<i64: 28, 28>, init_level = 5 : i64, res_level = array<i64: 2, 2>, res_scale = array<i64: 52, 84>} {
    %0 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %1 = "ckks.negatec"(%0, %arg1) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %2 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %3 = "ckks.addcc"(%2, %arg0, %1) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %4 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %5 = "ckks.mulcc"(%4, %3, %arg0) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %6 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %7 = "ckks.encode"(%6) {level = 5 : i64, scale = 28 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %8 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %9 = "ckks.mulcp"(%8, %5, %7) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %10 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %11 = "ckks.rotatec"(%10, %9) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %12 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %13 = "ckks.addcc"(%12, %9, %11) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %14 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %15 = "ckks.rotatec"(%14, %13) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %16 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %17 = "ckks.addcc"(%16, %13, %15) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %18 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %19 = "ckks.rotatec"(%18, %17) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %20 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %21 = "ckks.addcc"(%20, %17, %19) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %22 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %23 = "ckks.rotatec"(%22, %21) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %24 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %25 = "ckks.addcc"(%24, %21, %23) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %26 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %27 = "ckks.rotatec"(%26, %25) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %28 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %29 = "ckks.addcc"(%28, %25, %27) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %30 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %31 = "ckks.rotatec"(%30, %29) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %32 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %33 = "ckks.addcc"(%32, %29, %31) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %34 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %35 = "ckks.rotatec"(%34, %33) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %36 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %37 = "ckks.addcc"(%36, %33, %35) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %38 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %39 = "ckks.rotatec"(%38, %37) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %40 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %41 = "ckks.addcc"(%40, %37, %39) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %42 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %43 = "ckks.rotatec"(%42, %41) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %44 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %45 = "ckks.addcc"(%44, %41, %43) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %46 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %47 = "ckks.rotatec"(%46, %45) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %48 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %49 = "ckks.addcc"(%48, %45, %47) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %50 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %51 = "ckks.rotatec"(%50, %49) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %52 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %53 = "ckks.addcc"(%52, %49, %51) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %54 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %55 = "ckks.rotatec"(%54, %53) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %56 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %57 = "ckks.addcc"(%56, %53, %55) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %58 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %59 = "ckks.modswitchc"(%58, %3) {downFactor = 1 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %60 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %61 = "ckks.encode"(%60) {level = 4 : i64, scale = 28 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %62 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %63 = "ckks.mulcp"(%62, %59, %61) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %64 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %65 = "ckks.rotatec"(%64, %63) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %66 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %67 = "ckks.addcc"(%66, %63, %65) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %68 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %69 = "ckks.rotatec"(%68, %67) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %70 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %71 = "ckks.addcc"(%70, %67, %69) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %72 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %73 = "ckks.rotatec"(%72, %71) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %74 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %75 = "ckks.addcc"(%74, %71, %73) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %76 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %77 = "ckks.rotatec"(%76, %75) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %78 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %79 = "ckks.addcc"(%78, %75, %77) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %80 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %81 = "ckks.rotatec"(%80, %79) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %82 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %83 = "ckks.addcc"(%82, %79, %81) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %84 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %85 = "ckks.rotatec"(%84, %83) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %86 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %87 = "ckks.addcc"(%86, %83, %85) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %88 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %89 = "ckks.rotatec"(%88, %87) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %90 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %91 = "ckks.addcc"(%90, %87, %89) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %92 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %93 = "ckks.rotatec"(%92, %91) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %94 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %95 = "ckks.addcc"(%94, %91, %93) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %96 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %97 = "ckks.rotatec"(%96, %95) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %98 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %99 = "ckks.addcc"(%98, %95, %97) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %100 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %101 = "ckks.rotatec"(%100, %99) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %102 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %103 = "ckks.addcc"(%102, %99, %101) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %104 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %105 = "ckks.rotatec"(%104, %103) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %106 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %107 = "ckks.addcc"(%106, %103, %105) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %108 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %109 = "ckks.rotatec"(%108, %107) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %110 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %111 = "ckks.addcc"(%110, %107, %109) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %112 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %113 = "ckks.encode"(%112) {level = 5 : i64, scale = 28 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %114 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %115 = "ckks.mulcp"(%114, %57, %113) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %116 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %117 = "ckks.rescalec"(%116, %115) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %118 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %119 = "ckks.encode"(%118) {level = 4 : i64, scale = 28 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %120 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %121 = "ckks.mulcp"(%120, %111, %119) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %122 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %123 = "ckks.encode"(%122) {level = 4 : i64, scale = 52 : i64, value = 0 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %124 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %125 = "ckks.addcp"(%124, %117, %123) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %126 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %127 = "ckks.modswitchc"(%126, %arg0) {downFactor = 1 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %128 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %129 = "ckks.mulcc"(%128, %127, %125) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %130 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %131 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %132 = "ckks.encode"(%131) {level = 4 : i64, scale = 4 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %133 = "ckks.mulcp"(%130, %129, %132) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %134 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %135 = "ckks.addcc"(%134, %133, %121) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %136 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %137 = "ckks.modswitchc"(%136, %1) {downFactor = 1 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %138 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %139 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %140 = "ckks.encode"(%139) {level = 4 : i64, scale = 56 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %141 = "ckks.mulcp"(%138, %137, %140) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %142 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %143 = "ckks.addcc"(%142, %135, %141) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %144 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %145 = "ckks.mulcc"(%144, %143, %127) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %146 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %147 = "ckks.rescalec"(%146, %145) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %148 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %149 = "ckks.encode"(%148) {level = 3 : i64, scale = 28 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %150 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %151 = "ckks.mulcp"(%150, %147, %149) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %152 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %153 = "ckks.rotatec"(%152, %151) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %154 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %155 = "ckks.addcc"(%154, %151, %153) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %156 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %157 = "ckks.rotatec"(%156, %155) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %158 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %159 = "ckks.addcc"(%158, %155, %157) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %160 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %161 = "ckks.rotatec"(%160, %159) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %162 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %163 = "ckks.addcc"(%162, %159, %161) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %164 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %165 = "ckks.rotatec"(%164, %163) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %166 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %167 = "ckks.addcc"(%166, %163, %165) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %168 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %169 = "ckks.rotatec"(%168, %167) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %170 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %171 = "ckks.addcc"(%170, %167, %169) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %172 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %173 = "ckks.rotatec"(%172, %171) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %174 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %175 = "ckks.addcc"(%174, %171, %173) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %176 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %177 = "ckks.rotatec"(%176, %175) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %178 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %179 = "ckks.addcc"(%178, %175, %177) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %180 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %181 = "ckks.rotatec"(%180, %179) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %182 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %183 = "ckks.addcc"(%182, %179, %181) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %184 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %185 = "ckks.rotatec"(%184, %183) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %186 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %187 = "ckks.addcc"(%186, %183, %185) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %188 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %189 = "ckks.rotatec"(%188, %187) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %190 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %191 = "ckks.addcc"(%190, %187, %189) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %192 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %193 = "ckks.rotatec"(%192, %191) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %194 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %195 = "ckks.addcc"(%194, %191, %193) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %196 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %197 = "ckks.rotatec"(%196, %195) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %198 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %199 = "ckks.addcc"(%198, %195, %197) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %200 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %201 = "ckks.modswitchc"(%200, %143) {downFactor = 1 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %202 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %203 = "ckks.encode"(%202) {level = 3 : i64, scale = 28 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %204 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %205 = "ckks.mulcp"(%204, %201, %203) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %206 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %207 = "ckks.rescalec"(%206, %205) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %208 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %209 = "ckks.rotatec"(%208, %207) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %210 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %211 = "ckks.addcc"(%210, %207, %209) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %212 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %213 = "ckks.rotatec"(%212, %211) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %214 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %215 = "ckks.addcc"(%214, %211, %213) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %216 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %217 = "ckks.rotatec"(%216, %215) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %218 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %219 = "ckks.addcc"(%218, %215, %217) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %220 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %221 = "ckks.rotatec"(%220, %219) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %222 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %223 = "ckks.addcc"(%222, %219, %221) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %224 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %225 = "ckks.rotatec"(%224, %223) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %226 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %227 = "ckks.addcc"(%226, %223, %225) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %228 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %229 = "ckks.rotatec"(%228, %227) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %230 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %231 = "ckks.addcc"(%230, %227, %229) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %232 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %233 = "ckks.rotatec"(%232, %231) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %234 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %235 = "ckks.addcc"(%234, %231, %233) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %236 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %237 = "ckks.rotatec"(%236, %235) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %238 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %239 = "ckks.addcc"(%238, %235, %237) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %240 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %241 = "ckks.rotatec"(%240, %239) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %242 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %243 = "ckks.addcc"(%242, %239, %241) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %244 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %245 = "ckks.rotatec"(%244, %243) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %246 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %247 = "ckks.addcc"(%246, %243, %245) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %248 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %249 = "ckks.rotatec"(%248, %247) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %250 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %251 = "ckks.addcc"(%250, %247, %249) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %252 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %253 = "ckks.rotatec"(%252, %251) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %254 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %255 = "ckks.addcc"(%254, %251, %253) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %256 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %257 = "ckks.encode"(%256) {level = 3 : i64, scale = 28 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %258 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %259 = "ckks.mulcp"(%258, %199, %257) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %260 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %261 = "ckks.rescalec"(%260, %259) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %262 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %263 = "ckks.encode"(%262) {level = 2 : i64, scale = 28 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %264 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %265 = "ckks.mulcp"(%264, %255, %263) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %266 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %267 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %268 = "ckks.encode"(%267) {level = 2 : i64, scale = 4 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %269 = "ckks.mulcp"(%266, %261, %268) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %270 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %271 = "ckks.modswitchc"(%270, %125) {downFactor = 2 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %272 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %273 = "ckks.addcc"(%272, %271, %269) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %274 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %275 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %276 = "ckks.encode"(%275) {level = 2 : i64, scale = 4 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %277 = "ckks.mulcp"(%274, %265, %276) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %278 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %279 = "ckks.modswitchc"(%278, %121) {downFactor = 2 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %280 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %281 = "ckks.addcc"(%280, %279, %277) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    return %273, %281 : tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>
  }
}

