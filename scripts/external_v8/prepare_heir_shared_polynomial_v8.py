#!/usr/bin/env python3
"""Materialize HEIR Lattigo/OpenFHE runners for the frozen V8 polynomial."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
HEIR_COMMIT = "cb7a7a30bb4d995b50e33bb5cd82ff7434db3656"
HEIR_OPT_SHA256 = "dccd5b66eaa7c1c2341d50b7245db44f8dcc551e3997cbc38e2d6e58b0aa35d7"
HEIR_TRANSLATE_SHA256 = "c57b257ce97f7d78b844be1a6818b077cec118f2142eb09a9f0a94cdebe6541d"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def run(command: list[str], **kwargs: object) -> None:
    subprocess.run(command, check=True, **kwargs)


def locate_tool(name: str, expected: str) -> Path:
    matches = sorted((ROOT / "external/v7/builds/heir").glob(f"*/execroot/_main/bazel-out/k8-fastbuild/bin/tools/{name}"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one V7 {name}, found {len(matches)}")
    if sha256(matches[0]) != "sha256:" + expected:
        raise RuntimeError(f"INTEGRITY_BLOCK: V7 {name} digest changed")
    return matches[0]


def go_runner() -> str:
    return r'''package main

import (
    "encoding/csv"
    "encoding/json"
    "flag"
    "fmt"
    "math"
    "os"
    "strconv"
    "time"

    "flipguard-v8-heir/sharedpoly"
)

type record struct {
    Provider string `json:"provider"`
    Runtime string `json:"runtime"`
    Role string `json:"role"`
    Context int `json:"context"`
    RowID string `json:"row_id"`
    Plaintext float64 `json:"plaintext"`
    Decrypted float64 `json:"decrypted"`
    AbsoluteError float64 `json:"absolute_error"`
    Margin float64 `json:"margin"`
    NormalizedBudgetUsage float64 `json:"normalized_budget_usage"`
    Certifiable bool `json:"certifiable"`
    PlainDecision bool `json:"plain_decision"`
    CKKSDecision bool `json:"ckks_decision"`
    DecisionFlip bool `json:"decision_flip"`
    ReserveViolation bool `json:"reserve_violation"`
    EncryptMS float64 `json:"encrypt_ms"`
    EvaluateMS float64 `json:"evaluate_ms"`
    DecryptMS float64 `json:"decrypt_ms"`
    TotalMS float64 `json:"total_ms"`
}

func mustFloat(value string) float64 { result, err := strconv.ParseFloat(value, 64); if err != nil { panic(err) }; return result }

func main() {
    input := flag.String("input", "", "frozen input CSV")
    role := flag.String("role", "", "configuration_validation or locked_audit")
    output := flag.String("output", "", "JSONL output")
    contexts := flag.Int("contexts", 3, "fresh key contexts")
    flag.Parse()
    if *input == "" || *output == "" || (*role != "configuration_validation" && *role != "locked_audit") || *contexts != 3 { panic("invalid frozen V8 arguments") }
    file, err := os.Open(*input); if err != nil { panic(err) }; defer file.Close()
    reader := csv.NewReader(file); rows, err := reader.ReadAll(); if err != nil { panic(err) }
    header := map[string]int{}; for index, name := range rows[0] { header[name] = index }
    if len(rows)-1 != 500 { panic(fmt.Sprintf("expected 500 inputs, got %d", len(rows)-1)) }
    out, err := os.OpenFile(*output, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0644); if err != nil { panic(err) }; defer out.Close()
    encoder := json.NewEncoder(out)
    for context := 1; context <= *contexts; context++ {
        evaluator, params, ecd, enc, dec := sharedpoly.Shared_polynomial__configure()
        plains := sharedpoly.Shared_polynomial__preprocessing(params, ecd)
        for _, row := range rows[1:] {
            totalStart := time.Now()
            start := time.Now()
            x0 := sharedpoly.Shared_polynomial__encrypt__arg0(evaluator, params, ecd, enc, float32(mustFloat(row[header["x_0"]])))
            x1 := sharedpoly.Shared_polynomial__encrypt__arg1(evaluator, params, ecd, enc, float32(mustFloat(row[header["x_1"]])))
            x2 := sharedpoly.Shared_polynomial__encrypt__arg2(evaluator, params, ecd, enc, float32(mustFloat(row[header["x_2"]])))
            encryptMS := float64(time.Since(start).Nanoseconds()) / 1e6
            start = time.Now(); ct := sharedpoly.Shared_polynomial__preprocessed(evaluator, params, ecd, x0, x1, x2, plains); evaluateMS := float64(time.Since(start).Nanoseconds()) / 1e6
            start = time.Now(); actual := float64(sharedpoly.Shared_polynomial__decrypt__result0(evaluator, params, ecd, dec, ct)); decryptMS := float64(time.Since(start).Nanoseconds()) / 1e6
            expected := mustFloat(row[header["polynomial_score"]]); margin := math.Abs(expected-0.5); budget := 0.5*margin; absolute := math.Abs(actual-expected)
            certifiable := margin > 0.001; plainDecision := expected >= 0.5; ckksDecision := actual >= 0.5
            item := record{"Google HEIR", "Lattigo-v6.2.0-translation", *role, context, row[header["row_id"]], expected, actual, absolute, margin, absolute/budget, certifiable, plainDecision, ckksDecision, certifiable && plainDecision != ckksDecision, certifiable && absolute >= budget, encryptMS, evaluateMS, decryptMS, float64(time.Since(totalStart).Nanoseconds())/1e6}
            if err := encoder.Encode(item); err != nil { panic(err) }
        }
    }
}
'''


def cpp_runner() -> str:
    return r'''#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include "tests/Examples/openfhe/ckks/shared_polynomial_v8/shared_polynomial_lib.h"

std::vector<std::string> split(const std::string& line) {
  std::vector<std::string> out; std::stringstream stream(line); std::string value;
  while (std::getline(stream, value, ',')) out.push_back(value); return out;
}

int main(int argc, char** argv) {
  if (argc != 5 || std::string(argv[1]).empty()) return 2;
  std::ifstream input(argv[1]); std::ofstream output(argv[3], std::ios::out | std::ios::trunc);
  if (!input || !output || std::stoi(argv[4]) != 3) return 3;
  std::string line; std::getline(input, line); auto names = split(line);
  int row_id=-1, score=-1, x0=-1, x1=-1, x2=-1;
  for (int i=0; i<static_cast<int>(names.size()); ++i) { if(names[i]=="row_id")row_id=i; if(names[i]=="polynomial_score")score=i; if(names[i]=="x_0")x0=i; if(names[i]=="x_1")x1=i; if(names[i]=="x_2")x2=i; }
  std::vector<std::vector<std::string>> rows; while(std::getline(input,line)) rows.push_back(split(line));
  if (rows.size()!=500 || row_id<0 || score<0 || x0<0 || x1<0 || x2<0) return 4;
  output << "provider,runtime,role,context,row_id,plaintext,decrypted,absolute_error,margin,normalized_budget_usage,certifiable,plaintext_decision,ckks_decision,decision_flip,reserve_violation\n";
  for (int context=1; context<=3; ++context) {
    auto cc = shared_polynomial__generate_crypto_context(); auto keys=cc->KeyGen(); cc=shared_polynomial__configure_crypto_context(cc, keys.secretKey);
    for (const auto& row: rows) {
      double expected=std::stod(row[score]);
      auto a=shared_polynomial__encrypt__arg0(cc, static_cast<float>(std::stod(row[x0])), keys.publicKey);
      auto b=shared_polynomial__encrypt__arg1(cc, static_cast<float>(std::stod(row[x1])), keys.publicKey);
      auto c=shared_polynomial__encrypt__arg2(cc, static_cast<float>(std::stod(row[x2])), keys.publicKey);
      auto encrypted=shared_polynomial(cc,a,b,c); double actual=shared_polynomial__decrypt__result0(cc, encrypted, keys.secretKey);
      double error=std::abs(actual-expected), margin=std::abs(expected-0.5), budget=0.5*margin; bool cert=margin>0.001, pd=expected>=0.5, cd=actual>=0.5;
      output << "Google HEIR,OpenFHE," << argv[2] << ',' << context << ',' << row[row_id] << ',' << std::setprecision(17) << expected << ',' << actual << ',' << error << ',' << margin << ',' << error/budget << ',' << cert << ',' << pd << ',' << cd << ',' << (cert && pd!=cd) << ',' << (cert && error>=budget) << '\n';
    }
  }
  return 0;
}
'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_root.resolve()
    if output.exists():
        if (output / "manifest.json").is_file():
            common_package = ROOT / "external/v8/generated/sharedpoly"
            common_package.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                output / "lattigo_v6_2/sharedpoly/shared_polynomial.go",
                common_package / "shared_polynomial.go",
            )
            runner = ROOT / "external/v8/sources/heir/tests/Examples/openfhe/ckks/shared_polynomial_v8/runner.cpp"
            if runner.is_file():
                runner.write_text(cpp_runner(), encoding="utf-8")
                manifest_path = output / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["openfhe_runner_sha256"] = sha256(runner)
                manifest_partial = manifest_path.with_suffix(".json.partial")
                manifest_partial.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                manifest_partial.replace(manifest_path)
            print((output / "manifest.json").read_text(), end="")
            return 0
        raise FileExistsError(f"refusing incomplete HEIR translation root: {output}")
    heir_opt = locate_tool("heir-opt", HEIR_OPT_SHA256)
    heir_translate = locate_tool("heir-translate", HEIR_TRANSLATE_SHA256)
    graph = ROOT / "docs/evidence/focused_external_comparison_v8/workload_contracts/shared_polynomial_threshold_v8.mlir"
    output.mkdir(parents=True)
    lattigo_mlir = output / "shared_polynomial_lattigo.mlir"
    openfhe_mlir = output / "shared_polynomial_openfhe.mlir"
    run([str(heir_opt), str(graph), "--annotate-module=backend=lattigo scheme=ckks", "--mlir-to-ckks=min-slot-count=2048", "--scheme-to-lattigo", "-o", str(lattigo_mlir)])
    run([str(heir_opt), str(graph), "--annotate-module=backend=openfhe scheme=ckks", "--mlir-to-ckks=min-slot-count=1024", "--scheme-to-openfhe", "-o", str(openfhe_mlir)])

    go_root = output / "lattigo_v6_2"
    package = go_root / "sharedpoly"
    package.mkdir(parents=True)
    with (package / "shared_polynomial.go").open("w", encoding="utf-8") as handle:
        run([str(heir_translate), str(lattigo_mlir), "--emit-lattigo", "--package-name=sharedpoly"], stdout=handle)
    common_package = ROOT / "external/v8/generated/sharedpoly"
    common_package.mkdir(parents=True, exist_ok=True)
    shutil.copy2(package / "shared_polynomial.go", common_package / "shared_polynomial.go")
    (go_root / "go.mod").write_text("module flipguard-v8-heir\n\ngo 1.25.9\n\nrequire github.com/tuneinsight/lattigo/v6 v6.2.0\n", encoding="utf-8")
    (go_root / "main.go").write_text(go_runner(), encoding="utf-8")

    source = ROOT / "external/v7/sources/heir"
    clone = ROOT / "external/v8/sources/heir"
    clone.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--local", "--no-hardlinks", str(source), str(clone)])
    run(["git", "checkout", "--detach", HEIR_COMMIT], cwd=clone)
    package_root = clone / "tests/Examples/openfhe/ckks/shared_polynomial_v8"
    package_root.mkdir(parents=True)
    shutil.copy2(graph, package_root / "shared_polynomial.mlir")
    (package_root / "runner.cpp").write_text(cpp_runner(), encoding="utf-8")
    (package_root / "BUILD").write_text('''load("@heir//bazel/openfhe:copts.bzl", "OPENMP_COPTS", "OPENMP_LINKOPTS")
load("@heir//tools:heir-openfhe.bzl", "openfhe_lib")
load("@rules_cc//cc:cc_binary.bzl", "cc_binary")

openfhe_lib(
    name = "shared_polynomial",
    mlir_src = "shared_polynomial.mlir",
    generated_lib_header = "shared_polynomial_lib.h",
    cc_lib_target_name = "shared_polynomial_cc_lib",
    heir_opt_flags = ["--annotate-module=backend=openfhe scheme=ckks", "--mlir-to-ckks=min-slot-count=1024", "--scheme-to-openfhe"],
)

cc_binary(
    name = "runner",
    srcs = ["runner.cpp"],
    deps = [":shared_polynomial_cc_lib", "@openfhe//:pke", "@openfhe//:core"],
    copts = OPENMP_COPTS,
    linkopts = OPENMP_LINKOPTS,
)
''', encoding="utf-8")
    manifest = {
        "schema_version": "flipguard_focused_external_v8_heir_translation_v1",
        "status": "PASS", "heir_commit": HEIR_COMMIT,
        "graph_sha256": sha256(graph), "heir_opt_sha256": sha256(heir_opt), "heir_translate_sha256": sha256(heir_translate),
        "lattigo_mlir_sha256": sha256(lattigo_mlir), "openfhe_mlir_sha256": sha256(openfhe_mlir),
        "generated_lattigo_go_sha256": sha256(package / "shared_polynomial.go"),
        "openfhe_runner_sha256": sha256(package_root / "runner.cpp"),
        "lattigo_runtime_version": "v6.2.0", "source_semantics_modified": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
