module @"traced/LinearRegression.mlir" {
  func.func @_hecate_LinearRegression(%arg0: tensor<1x!ckks.poly<2 * 0>>, %arg1: tensor<1x!ckks.poly<2 * 0>>) -> (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) attributes {arg_level = array<i64: 7, 7>, arg_scale = array<i64: 46, 46>, init_level = 7 : i64, res_level = array<i64: 2, 2>, res_scale = array<i64: 96, 78>} {
    %0 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %1 = "ckks.negatec"(%0, %arg1) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %2 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %3 = "ckks.addcc"(%2, %arg0, %1) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %4 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %5 = "ckks.mulcc"(%4, %3, %arg0) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %6 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %7 = "ckks.encode"(%6) {level = 7 : i64, scale = 46 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %8 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %9 = "ckks.mulcp"(%8, %5, %7) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %10 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %11 = "ckks.rescalec"(%10, %9) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %12 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %13 = "ckks.rotatec"(%12, %11) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %14 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %15 = "ckks.addcc"(%14, %11, %13) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %16 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %17 = "ckks.rotatec"(%16, %15) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %18 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %19 = "ckks.addcc"(%18, %15, %17) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %20 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %21 = "ckks.rotatec"(%20, %19) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %22 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %23 = "ckks.addcc"(%22, %19, %21) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %24 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %25 = "ckks.rotatec"(%24, %23) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %26 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %27 = "ckks.addcc"(%26, %23, %25) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %28 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %29 = "ckks.rotatec"(%28, %27) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %30 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %31 = "ckks.addcc"(%30, %27, %29) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %32 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %33 = "ckks.rotatec"(%32, %31) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %34 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %35 = "ckks.addcc"(%34, %31, %33) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %36 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %37 = "ckks.rotatec"(%36, %35) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %38 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %39 = "ckks.addcc"(%38, %35, %37) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %40 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %41 = "ckks.rotatec"(%40, %39) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %42 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %43 = "ckks.addcc"(%42, %39, %41) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %44 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %45 = "ckks.rotatec"(%44, %43) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %46 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %47 = "ckks.addcc"(%46, %43, %45) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %48 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %49 = "ckks.rotatec"(%48, %47) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %50 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %51 = "ckks.addcc"(%50, %47, %49) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %52 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %53 = "ckks.rotatec"(%52, %51) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %54 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %55 = "ckks.addcc"(%54, %51, %53) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %56 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %57 = "ckks.rotatec"(%56, %55) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %58 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %59 = "ckks.addcc"(%58, %55, %57) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %60 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %61 = "ckks.modswitchc"(%60, %3) {downFactor = 2 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %62 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %63 = "ckks.encode"(%62) {level = 5 : i64, scale = 46 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
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
    %115 = "ckks.encode"(%114) {level = 6 : i64, scale = 46 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %116 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %117 = "ckks.mulcp"(%116, %59, %115) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %118 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %119 = "ckks.rescalec"(%118, %117) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %120 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %121 = "ckks.encode"(%120) {level = 5 : i64, scale = 46 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %122 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %123 = "ckks.mulcp"(%122, %113, %121) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %124 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %125 = "ckks.rescalec"(%124, %123) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %126 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %127 = "ckks.encode"(%126) {level = 5 : i64, scale = 64 : i64, value = 0 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %128 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %129 = "ckks.addcp"(%128, %119, %127) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %130 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %131 = "ckks.modswitchc"(%130, %arg0) {downFactor = 2 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %132 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %133 = "ckks.mulcc"(%132, %131, %129) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %134 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %135 = "ckks.rescalec"(%134, %133) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %136 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %137 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %138 = "ckks.encode"(%137) {level = 4 : i64, scale = 28 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %139 = "ckks.mulcp"(%136, %135, %138) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %140 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %141 = "ckks.addcc"(%140, %139, %125) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %142 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %143 = "ckks.modswitchc"(%142, %1) {downFactor = 3 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %144 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %145 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %146 = "ckks.encode"(%145) {level = 4 : i64, scale = 32 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %147 = "ckks.mulcp"(%144, %143, %146) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %148 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %149 = "ckks.addcc"(%148, %141, %147) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %150 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %151 = "ckks.modswitchc"(%150, %arg0) {downFactor = 3 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %152 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %153 = "ckks.mulcc"(%152, %149, %151) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %154 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %155 = "ckks.rescalec"(%154, %153) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %156 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %157 = "ckks.encode"(%156) {level = 3 : i64, scale = 46 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %158 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %159 = "ckks.mulcp"(%158, %155, %157) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %160 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %161 = "ckks.rescalec"(%160, %159) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %162 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %163 = "ckks.rotatec"(%162, %161) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %164 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %165 = "ckks.addcc"(%164, %161, %163) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %166 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %167 = "ckks.rotatec"(%166, %165) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %168 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %169 = "ckks.addcc"(%168, %165, %167) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %170 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %171 = "ckks.rotatec"(%170, %169) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %172 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %173 = "ckks.addcc"(%172, %169, %171) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %174 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %175 = "ckks.rotatec"(%174, %173) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %176 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %177 = "ckks.addcc"(%176, %173, %175) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %178 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %179 = "ckks.rotatec"(%178, %177) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %180 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %181 = "ckks.addcc"(%180, %177, %179) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %182 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %183 = "ckks.rotatec"(%182, %181) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %184 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %185 = "ckks.addcc"(%184, %181, %183) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %186 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %187 = "ckks.rotatec"(%186, %185) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %188 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %189 = "ckks.addcc"(%188, %185, %187) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %190 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %191 = "ckks.rotatec"(%190, %189) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %192 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %193 = "ckks.addcc"(%192, %189, %191) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %194 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %195 = "ckks.rotatec"(%194, %193) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %196 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %197 = "ckks.addcc"(%196, %193, %195) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %198 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %199 = "ckks.rotatec"(%198, %197) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %200 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %201 = "ckks.addcc"(%200, %197, %199) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %202 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %203 = "ckks.rotatec"(%202, %201) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %204 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %205 = "ckks.addcc"(%204, %201, %203) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %206 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %207 = "ckks.rotatec"(%206, %205) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %208 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %209 = "ckks.addcc"(%208, %205, %207) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %210 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %211 = "ckks.encode"(%210) {level = 4 : i64, scale = 46 : i64, value = 2 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %212 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %213 = "ckks.mulcp"(%212, %149, %211) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %214 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %215 = "ckks.rescalec"(%214, %213) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %216 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %217 = "ckks.rotatec"(%216, %215) {offset = array<i64: 2048>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %218 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %219 = "ckks.addcc"(%218, %215, %217) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %220 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %221 = "ckks.rotatec"(%220, %219) {offset = array<i64: 1024>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %222 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %223 = "ckks.addcc"(%222, %219, %221) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %224 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %225 = "ckks.rotatec"(%224, %223) {offset = array<i64: 512>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %226 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %227 = "ckks.addcc"(%226, %223, %225) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %228 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %229 = "ckks.rotatec"(%228, %227) {offset = array<i64: 256>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %230 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %231 = "ckks.addcc"(%230, %227, %229) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %232 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %233 = "ckks.rotatec"(%232, %231) {offset = array<i64: 128>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %234 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %235 = "ckks.addcc"(%234, %231, %233) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %236 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %237 = "ckks.rotatec"(%236, %235) {offset = array<i64: 64>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %238 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %239 = "ckks.addcc"(%238, %235, %237) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %240 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %241 = "ckks.rotatec"(%240, %239) {offset = array<i64: 32>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %242 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %243 = "ckks.addcc"(%242, %239, %241) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %244 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %245 = "ckks.rotatec"(%244, %243) {offset = array<i64: 16>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %246 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %247 = "ckks.addcc"(%246, %243, %245) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %248 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %249 = "ckks.rotatec"(%248, %247) {offset = array<i64: 8>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %250 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %251 = "ckks.addcc"(%250, %247, %249) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %252 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %253 = "ckks.rotatec"(%252, %251) {offset = array<i64: 4>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %254 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %255 = "ckks.addcc"(%254, %251, %253) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %256 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %257 = "ckks.rotatec"(%256, %255) {offset = array<i64: 2>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %258 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %259 = "ckks.addcc"(%258, %255, %257) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %260 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %261 = "ckks.rotatec"(%260, %259) {offset = array<i64: 1>} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %262 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %263 = "ckks.addcc"(%262, %259, %261) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %264 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %265 = "ckks.encode"(%264) {level = 2 : i64, scale = 46 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %266 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %267 = "ckks.mulcp"(%266, %209, %265) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %268 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %269 = "ckks.encode"(%268) {level = 3 : i64, scale = 46 : i64, value = 1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %270 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %271 = "ckks.mulcp"(%270, %263, %269) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %272 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %273 = "ckks.rescalec"(%272, %271) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %274 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %275 = "ckks.modswitchc"(%274, %129) {downFactor = 3 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %276 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %277 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %278 = "ckks.encode"(%277) {level = 2 : i64, scale = 32 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %279 = "ckks.mulcp"(%276, %275, %278) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %280 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %281 = "ckks.addcc"(%280, %279, %267) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %282 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %283 = tensor.empty() : tensor<1x!ckks.poly<1 * 0>>
    %284 = "ckks.encode"(%283) {level = 2 : i64, scale = 28 : i64, value = -1 : i64} : (tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<1 * 0>>
    %285 = "ckks.mulcp"(%282, %273, %284) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<1 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %286 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %287 = "ckks.modswitchc"(%286, %125) {downFactor = 2 : i64} : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    %288 = tensor.empty() : tensor<1x!ckks.poly<2 * 0>>
    %289 = "ckks.addcc"(%288, %287, %285) : (tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>) -> tensor<1x!ckks.poly<2 * 0>>
    return %281, %289 : tensor<1x!ckks.poly<2 * 0>>, tensor<1x!ckks.poly<2 * 0>>
  }
}

