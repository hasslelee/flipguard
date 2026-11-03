module @"traced/LinearRegression.mlir" {
  func.func @_hecate_LinearRegression(%arg0: tensor<1x!ckks.poly<2 * 0>>, %arg1: tensor<1x!ckks.poly<2 * 0>>) -> (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) attributes {arg_level = array<i64: 4, 4>, arg_scale = array<i64: 18, 18>, init_level = 4 : i64, res_level = array<i64: 2, 2>, res_scale = array<i64: 72, 54>} {
    %0 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %1 = "ckks.negatec"(%0, %arg1) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %2 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %3 = "ckks.addcc"(%2, %arg0, %1) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %4 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %5 = "ckks.mulcc"(%4, %3, %arg0) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %6 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %7 = "ckks.encode"(%6) {level = 4 : i64, scale = 18 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
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
    %58 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %59 = "ckks.encode"(%58) {level = 3 : i64, scale = 18 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %60 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %61 = "ckks.modswitchc"(%60, %3) {downFactor = 1 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %62 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %63 = "ckks.encode"(%62) {level = 3 : i64, scale = 18 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %64 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %65 = "ckks.mulcp"(%64, %61, %63) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %66 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %67 = "ckks.rotatec"(%66, %65) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %68 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %69 = "ckks.addcc"(%68, %65, %67) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %70 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %71 = "ckks.rotatec"(%70, %69) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %72 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %73 = "ckks.addcc"(%72, %69, %71) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %74 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %75 = "ckks.rotatec"(%74, %73) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %76 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %77 = "ckks.addcc"(%76, %73, %75) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %78 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %79 = "ckks.rotatec"(%78, %77) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %80 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %81 = "ckks.addcc"(%80, %77, %79) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %82 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %83 = "ckks.rotatec"(%82, %81) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %84 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %85 = "ckks.addcc"(%84, %81, %83) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %86 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %87 = "ckks.rotatec"(%86, %85) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %88 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %89 = "ckks.addcc"(%88, %85, %87) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %90 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %91 = "ckks.rotatec"(%90, %89) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %92 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %93 = "ckks.addcc"(%92, %89, %91) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %94 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %95 = "ckks.rotatec"(%94, %93) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %96 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %97 = "ckks.addcc"(%96, %93, %95) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %98 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %99 = "ckks.rotatec"(%98, %97) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %100 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %101 = "ckks.addcc"(%100, %97, %99) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %102 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %103 = "ckks.rotatec"(%102, %101) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %104 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %105 = "ckks.addcc"(%104, %101, %103) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %106 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %107 = "ckks.rotatec"(%106, %105) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %108 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %109 = "ckks.addcc"(%108, %105, %107) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %110 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %111 = "ckks.rotatec"(%110, %109) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %112 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %113 = "ckks.addcc"(%112, %109, %111) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %114 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %115 = "ckks.encode"(%114) {level = 4 : i64, scale = 18 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %116 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %117 = "ckks.mulcp"(%116, %57, %115) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %118 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %119 = "ckks.encode"(%118) {level = 3 : i64, scale = 18 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %120 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %121 = "ckks.encode"(%120) {level = 3 : i64, scale = 18 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %122 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %123 = "ckks.mulcp"(%122, %113, %121) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %124 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %125 = "ckks.encode"(%124) {level = 4 : i64, scale = 72 : i64, value = 0 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %126 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %127 = "ckks.addcp"(%126, %117, %125) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %128 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %129 = "ckks.mulcc"(%128, %arg0, %127) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %130 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %131 = "ckks.rescalec"(%130, %129) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %132 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %133 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %134 = "ckks.encode"(%133) {level = 3 : i64, scale = 24 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %135 = "ckks.mulcp"(%132, %131, %134) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %136 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %137 = "ckks.addcc"(%136, %135, %123) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %138 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %139 = "ckks.modswitchc"(%138, %1) {downFactor = 1 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %140 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %141 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %142 = "ckks.encode"(%141) {level = 3 : i64, scale = 36 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %143 = "ckks.mulcp"(%140, %139, %142) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %144 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %145 = "ckks.addcc"(%144, %137, %143) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %146 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %147 = "ckks.modswitchc"(%146, %arg0) {downFactor = 1 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %148 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %149 = "ckks.mulcc"(%148, %145, %147) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %150 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %151 = "ckks.mulcp"(%150, %149, %59) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %152 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %153 = "ckks.rescalec"(%152, %151) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %154 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %155 = "ckks.rotatec"(%154, %153) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %156 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %157 = "ckks.addcc"(%156, %153, %155) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %158 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %159 = "ckks.rotatec"(%158, %157) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %160 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %161 = "ckks.addcc"(%160, %157, %159) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %162 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %163 = "ckks.rotatec"(%162, %161) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %164 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %165 = "ckks.addcc"(%164, %161, %163) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %166 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %167 = "ckks.rotatec"(%166, %165) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %168 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %169 = "ckks.addcc"(%168, %165, %167) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %170 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %171 = "ckks.rotatec"(%170, %169) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %172 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %173 = "ckks.addcc"(%172, %169, %171) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %174 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %175 = "ckks.rotatec"(%174, %173) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %176 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %177 = "ckks.addcc"(%176, %173, %175) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %178 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %179 = "ckks.rotatec"(%178, %177) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %180 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %181 = "ckks.addcc"(%180, %177, %179) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %182 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %183 = "ckks.rotatec"(%182, %181) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %184 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %185 = "ckks.addcc"(%184, %181, %183) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %186 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %187 = "ckks.rotatec"(%186, %185) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %188 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %189 = "ckks.addcc"(%188, %185, %187) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %190 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %191 = "ckks.rotatec"(%190, %189) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %192 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %193 = "ckks.addcc"(%192, %189, %191) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %194 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %195 = "ckks.rotatec"(%194, %193) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %196 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %197 = "ckks.addcc"(%196, %193, %195) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %198 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %199 = "ckks.rotatec"(%198, %197) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %200 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %201 = "ckks.addcc"(%200, %197, %199) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %202 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %203 = "ckks.mulcp"(%202, %145, %59) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %204 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %205 = "ckks.rotatec"(%204, %203) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %206 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %207 = "ckks.addcc"(%206, %203, %205) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %208 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %209 = "ckks.rotatec"(%208, %207) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %210 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %211 = "ckks.addcc"(%210, %207, %209) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %212 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %213 = "ckks.rotatec"(%212, %211) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %214 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %215 = "ckks.addcc"(%214, %211, %213) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %216 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %217 = "ckks.rotatec"(%216, %215) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %218 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %219 = "ckks.addcc"(%218, %215, %217) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %220 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %221 = "ckks.rotatec"(%220, %219) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %222 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %223 = "ckks.addcc"(%222, %219, %221) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %224 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %225 = "ckks.rotatec"(%224, %223) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %226 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %227 = "ckks.addcc"(%226, %223, %225) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %228 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %229 = "ckks.rotatec"(%228, %227) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %230 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %231 = "ckks.addcc"(%230, %227, %229) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %232 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %233 = "ckks.rotatec"(%232, %231) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %234 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %235 = "ckks.addcc"(%234, %231, %233) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %236 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %237 = "ckks.rotatec"(%236, %235) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %238 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %239 = "ckks.addcc"(%238, %235, %237) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %240 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %241 = "ckks.rotatec"(%240, %239) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %242 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %243 = "ckks.addcc"(%242, %239, %241) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %244 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %245 = "ckks.rotatec"(%244, %243) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %246 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %247 = "ckks.addcc"(%246, %243, %245) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %248 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %249 = "ckks.rotatec"(%248, %247) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %250 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %251 = "ckks.addcc"(%250, %247, %249) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %252 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %253 = "ckks.encode"(%252) {level = 2 : i64, scale = 18 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %254 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %255 = "ckks.mulcp"(%254, %201, %253) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %256 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %257 = "ckks.mulcp"(%256, %251, %119) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %258 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %259 = "ckks.rescalec"(%258, %257) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %260 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %261 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %262 = "ckks.encode"(%261) {level = 2 : i64, scale = 24 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %263 = "ckks.mulcp"(%260, %255, %262) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %264 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %265 = "ckks.modswitchc"(%264, %127) {downFactor = 2 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %266 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %267 = "ckks.addcc"(%266, %265, %263) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %268 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %269 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %270 = "ckks.encode"(%269) {level = 2 : i64, scale = 24 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %271 = "ckks.mulcp"(%268, %259, %270) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %272 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %273 = "ckks.modswitchc"(%272, %123) {downFactor = 1 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %274 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %275 = "ckks.addcc"(%274, %273, %271) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    return %267, %275 : tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>
  }
}

