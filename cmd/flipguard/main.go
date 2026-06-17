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
		"ckks_linear": {
			Name:        "ckks_linear",
			Description: "Encrypted CKKS evaluation of the logreg_small linear expression",
			Run:         experiment.RunCKKSLinear,
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
		"ckks_boundary": {
			Name:        "ckks_boundary",
			Description: "Boundary-focused CKKS decision stability evaluation",
			Run:         experiment.RunCKKSBoundary,
		},
		"ckks_boundary_repeat": {
			Name:        "ckks_boundary_repeat",
			Description: "Repeated boundary-focused CKKS decision stability evaluation",
			Run:         experiment.RunCKKSBoundaryRepeat,
		},
		"ckks_boundary_sweep": {
			Name:        "ckks_boundary_sweep",
			Description: "Dense boundary-focused CKKS decision stability sweep",
			Run:         experiment.RunCKKSBoundarySweep,
		},
		"ckks_certificate_audit": {
			Name:        "ckks_certificate_audit",
			Description: "Observed-error decision certificate audit for CKKS boundary sweep",
			Run:         experiment.RunCKKSCertificateAudit,
		},
		"ckks_output_accuracy": {
			Name:        "ckks_output_accuracy",
			Description: "Task-level output accuracy guard for CKKS audit records",
			Run:         experiment.RunCKKSOutputAccuracy,
		},
		"ckks_timing_benchmark": {
			Name:        "ckks_timing_benchmark",
			Description: "Step-level timing benchmark for CKKS encrypted inference",
			Run:         experiment.RunCKKSTimingBenchmark,
		},
		"ckks_profile_benchmark": {
			Name:        "ckks_profile_benchmark",
			Description: "Profile-level timing and accuracy benchmark for CKKS encrypted inference",
			Run:         experiment.RunCKKSProfileBenchmark,
		},
		"ckks_profile_mode_comparison": {
			Name:        "ckks_profile_mode_comparison",
			Description: "Paper-ready comparison across CKKS profiles and evaluation modes",
			Run:         experiment.RunCKKSProfileModeComparison,
		},
		"ckks_policy_comparison": {
			Name:        "ckks_policy_comparison",
			Description: "Combined CKKS observed certificate and simulation policy comparison",
			Run:         experiment.RunCKKSPolicyComparison,
		},
		"ckks_paper_table": {
			Name:        "ckks_paper_table",
			Description: "Compact paper-ready CKKS and simulation policy comparison table export",
			Run:         experiment.RunCKKSPaperTable,
		},
		"ckks_final_check": {
			Name:        "ckks_final_check",
			Description: "Consistency check for tagged CKKS final result artifacts",
			Run:         experiment.RunCKKSFinalCheck,
		},
	}

	defaultOptions := experiment.DefaultRuntimeOptions()

	experimentName := flag.String("experiment", "logreg_small", "experiment name to run")
	listExperiments := flag.Bool("list", false, "list available experiments")

	ckksMinTargetZ := flag.Float64("ckks-min-z", defaultOptions.CKKSMinTargetZ, "minimum target z for CKKS boundary sweep")
	ckksMaxTargetZ := flag.Float64("ckks-max-z", defaultOptions.CKKSMaxTargetZ, "maximum target z for CKKS boundary sweep")
	ckksPoints := flag.Int("ckks-points", defaultOptions.CKKSPoints, "number of target z points for CKKS boundary sweep")
	ckksRepetitions := flag.Int("ckks-repetitions", defaultOptions.CKKSRepetitions, "number of CKKS repetitions")
	ckksSafetyFactor := flag.Float64("ckks-safety-factor", defaultOptions.CKKSSafetyFactor, "decision-margin safety factor for CKKS certificate audit")
	ckksOutputTag := flag.String("ckks-output-tag", defaultOptions.CKKSOutputTag, "optional CKKS result output tag")
	ckksScoreAbsErrorCap := flag.Float64("ckks-score-abs-error-cap", defaultOptions.CKKSScoreAbsErrorCap, "absolute score error cap for CKKS output accuracy guard")
	ckksScoreRelErrorCap := flag.Float64("ckks-score-rel-error-cap", defaultOptions.CKKSScoreRelErrorCap, "relative score error cap for CKKS output accuracy guard")
	ckksTimingWarmupRuns := flag.Int("ckks-timing-warmup-runs", defaultOptions.CKKSTimingWarmupRuns, "warmup runs for CKKS timing benchmark")
	ckksTimingMeasurementRuns := flag.Int("ckks-timing-measurement-runs", defaultOptions.CKKSTimingMeasurementRuns, "measurement runs for CKKS timing benchmark")
	ckksProfileNames := flag.String("ckks-profile-names", defaultOptions.CKKSProfileNames, "comma-separated CKKS profile names")
	ckksProfileName := flag.String("ckks-profile-name", defaultOptions.CKKSProfileName, "single CKKS profile name")
	ckksEvaluationMode := flag.String("ckks-evaluation-mode", defaultOptions.CKKSEvaluationMode, "CKKS evaluation mode")
	ckksNaiveProfileBenchmarkTag := flag.String("ckks-naive-profile-tag", defaultOptions.CKKSNaiveProfileBenchmarkTag, "source tag for naive CKKS profile benchmark")
	ckksRescaleProfileBenchmarkTag := flag.String("ckks-rescale-profile-tag", defaultOptions.CKKSRescaleProfileBenchmarkTag, "source tag for rescale CKKS profile benchmark")

	flag.Parse()

	experiment.SetRuntimeOptions(experiment.RuntimeOptions{
		CKKSMinTargetZ:                 *ckksMinTargetZ,
		CKKSMaxTargetZ:                 *ckksMaxTargetZ,
		CKKSPoints:                     *ckksPoints,
		CKKSRepetitions:                *ckksRepetitions,
		CKKSSafetyFactor:               *ckksSafetyFactor,
		CKKSOutputTag:                  *ckksOutputTag,
		CKKSScoreAbsErrorCap:           *ckksScoreAbsErrorCap,
		CKKSScoreRelErrorCap:           *ckksScoreRelErrorCap,
		CKKSTimingWarmupRuns:           *ckksTimingWarmupRuns,
		CKKSTimingMeasurementRuns:      *ckksTimingMeasurementRuns,
		CKKSProfileNames:               *ckksProfileNames,
		CKKSProfileName:                *ckksProfileName,
		CKKSEvaluationMode:             *ckksEvaluationMode,
		CKKSNaiveProfileBenchmarkTag:   *ckksNaiveProfileBenchmarkTag,
		CKKSRescaleProfileBenchmarkTag: *ckksRescaleProfileBenchmarkTag,
	})

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
	fmt.Printf("Description: %s\n", entry.Description)
	printRuntimeOptions(experiment.GetRuntimeOptions())
	fmt.Println()

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
		fmt.Printf("  %-28s %s\n", entry.Name, entry.Description)
	}
}

func printRuntimeOptions(options experiment.RuntimeOptions) {
	fmt.Printf(
		"Runtime options: ckks_min_z=%.6f ckks_max_z=%.6f ckks_points=%d ckks_repetitions=%d ckks_safety_factor=%.4f ckks_output_tag=%s ckks_score_abs_error_cap=%.10f ckks_score_rel_error_cap=%.10f ckks_timing_warmup_runs=%d ckks_timing_measurement_runs=%d ckks_profile_names=%s ckks_profile_name=%s ckks_evaluation_mode=%s ckks_naive_profile_tag=%s ckks_rescale_profile_tag=%s\n",
		options.CKKSMinTargetZ,
		options.CKKSMaxTargetZ,
		options.CKKSPoints,
		options.CKKSRepetitions,
		options.CKKSSafetyFactor,
		options.CKKSOutputTag,
		options.CKKSScoreAbsErrorCap,
		options.CKKSScoreRelErrorCap,
		options.CKKSTimingWarmupRuns,
		options.CKKSTimingMeasurementRuns,
		options.CKKSProfileNames,
		options.CKKSProfileName,
		options.CKKSEvaluationMode,
		options.CKKSNaiveProfileBenchmarkTag,
		options.CKKSRescaleProfileBenchmarkTag,
	)
}
