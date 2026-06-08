package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"sort"

	"github.com/hasslelee/flipguard/internal/experiment"
)

type experimentEntry struct {
	Name        string
	Description string
	Run         func() error
}

func main() {
	experiments := map[string]experimentEntry{
		"logreg_small": {
			Name:        "logreg_small",
			Description: "Boundary-focused polynomial logistic-style decision-stability simulation",
			Run:         experiment.RunLogRegSmall,
		},
		"ckks_roundtrip": {
			Name:        "ckks_roundtrip",
			Description: "Minimal Lattigo CKKS encode-encrypt-decrypt-decode probe",
			Run:         experiment.RunCKKSRoundTrip,
		},
		"ckks_linear": {
			Name:        "ckks_linear",
			Description: "Encrypted CKKS evaluation of the logreg_small linear expression",
			Run:         experiment.RunCKKSLinear,
		},
		"ckks_scale_probe": {
			Name:        "ckks_scale_probe",
			Description: "Diagnostic probe for CKKS scalar multiplication scale behavior",
			Run:         experiment.RunCKKSScaleProbe,
		},
		"ckks_bias_probe": {
			Name:        "ckks_bias_probe",
			Description: "Diagnostic probe comparing scalar-bias and plaintext-bias CKKS addition",
			Run:         experiment.RunCKKSBiasProbe,
		},
		"ckks_mul_probe": {
			Name:        "ckks_mul_probe",
			Description: "Diagnostic probe for CKKS ciphertext-ciphertext multiplication",
			Run:         experiment.RunCKKSMulProbe,
		},
		"ckks_cubic_probe": {
			Name:        "ckks_cubic_probe",
			Description: "Diagnostic probe for CKKS encrypted cubic evaluation",
			Run:         experiment.RunCKKSCubicProbe,
		},
		"ckks_polynomial": {
			Name:        "ckks_polynomial",
			Description: "Encrypted CKKS evaluation of the logreg_small polynomial output",
			Run:         experiment.RunCKKSPolynomial,
		},
		"ckks_full_logreg": {
			Name:        "ckks_full_logreg",
			Description: "End-to-end encrypted CKKS evaluation of logreg_small",
			Run:         experiment.RunCKKSFullLogReg,
		},
	}

	experimentName := flag.String("experiment", "logreg_small", "experiment name to run")
	listExperiments := flag.Bool("list", false, "list available experiments")
	flag.Parse()

	if *listExperiments {
		printExperiments(experiments)
		return
	}

	entry, ok := experiments[*experimentName]
	if !ok {
		fmt.Fprintf(os.Stderr, "unknown experiment: %s\n\n", *experimentName)
		printExperiments(experiments)
		os.Exit(2)
	}

	fmt.Printf("Running experiment: %s\n", entry.Name)
	fmt.Printf("Description: %s\n\n", entry.Description)

	if err := entry.Run(); err != nil {
		log.Fatalf("flipguard experiment %s failed: %v", entry.Name, err)
	}
}

func printExperiments(experiments map[string]experimentEntry) {
	names := make([]string, 0, len(experiments))
	for name := range experiments {
		names = append(names, name)
	}
	sort.Strings(names)

	fmt.Println("Available experiments:")
	for _, name := range names {
		entry := experiments[name]
		fmt.Printf("  %-18s %s\n", entry.Name, entry.Description)
	}
}
