package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"

	"github.com/hasslelee/flipguard/research/decisionactivation"
)

func main() {
	output := flag.String("output", "", "new output directory")
	sourceCommit := flag.String(
		"source-commit",
		"",
		"source commit used for the frozen control",
	)
	flag.Parse()
	if flag.NArg() != 0 ||
		strings.TrimSpace(*output) == "" ||
		strings.TrimSpace(*sourceCommit) == "" {
		fmt.Fprintln(
			os.Stderr,
			"--output and --source-commit are required; positional arguments are forbidden",
		)
		os.Exit(2)
	}
	analysis, err := decisionactivation.WriteAndAnalyze(
		*output,
		*sourceCommit,
	)
	if err != nil {
		fmt.Fprintf(os.Stderr, "decision activation control: %v\n", err)
		os.Exit(1)
	}
	encoded, err := json.Marshal(analysis)
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal analysis: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf(
		"decision_contract_activation=%s output=%s digest_input_bytes=%d\n",
		analysis.StaticClaimState,
		*output,
		len(encoded),
	)
}
