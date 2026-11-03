package certify

import (
	"fmt"
	"math"
)

const (
	// MulticlassDecisionContractSchemaV2 extends the binary threshold contract
	// without changing its evidence schema or execution behavior.
	MulticlassDecisionContractSchemaV2 = "decision_integrity_contract_v2"
	DeterministicLowestIndexTieBreak   = "lowest_class_index"
)

// MulticlassBoundCertificate evaluates the sufficient argmax-preservation
// proposition against declared non-negative per-logit error bounds.
type MulticlassBoundCertificate struct {
	SchemaVersion string `json:"schema_version"`
	TieBreak      string `json:"tie_break"`

	PlainClass int `json:"plain_class"`
	RunnerUp   int `json:"runner_up"`

	TopTwoGap       float64 `json:"top_two_gap"`
	MinimumGapSlack float64 `json:"minimum_gap_slack"`
	MinimumCap      float64 `json:"minimum_cap_required"`

	PlainTie       bool `json:"plain_tie"`
	StrictlyProved bool `json:"strictly_proved"`
}

// MulticlassObservedSample binds one plaintext logit vector to one vector per
// successful fresh-key execution. ApproxLogits is indexed by key run.
type MulticlassObservedSample struct {
	ID string

	PlainLogits  []float64
	ApproxLogits [][]float64
}

// MulticlassSampleObservation is the per-image, per-key evidence row used by
// journal-extension reports and locked-audit replay.
type MulticlassSampleObservation struct {
	SampleID string `json:"sample_id"`
	KeyRun   int    `json:"key_run"`

	PlainLogits []float64 `json:"plain_logits"`
	CKKSLogits  []float64 `json:"ckks_logits"`
	AbsErrors   []float64 `json:"per_logit_absolute_error"`

	PlainTop1 int `json:"plaintext_top_1"`
	PlainTop2 int `json:"plaintext_top_2"`
	CKKSTop1  int `json:"ckks_top_1"`

	TopTwoGap              float64 `json:"top_two_gap"`
	PairwiseDecisionBudget float64 `json:"pairwise_decision_budget"`
	MinimumCapRequired     float64 `json:"minimum_cap_required"`

	Certifiable       bool `json:"certifiable"`
	PlainTie          bool `json:"plaintext_tie"`
	ArgmaxFlip        bool `json:"argmax_flip"`
	ReservePolicyPass bool `json:"reserve_policy_pass"`
	ReserveViolation  bool `json:"reserve_policy_violation"`
}

// MulticlassObservedAggregation summarizes finite encrypted observations. A
// REJECTED result can preserve every observed argmax while still violating the
// predeclared reserve policy.
type MulticlassObservedAggregation struct {
	SchemaVersion string          `json:"schema_version"`
	Status        CandidateStatus `json:"status"`
	Reason        string          `json:"reason"`

	MarginFloor          float64 `json:"margin_floor"`
	MarginUtilizationCap float64 `json:"margin_utilization_cap"`

	VCert int `json:"v_cert"`
	VAmb  int `json:"v_amb"`

	SuccessRuns int `json:"success_runs"`
	FailedRuns  int `json:"failed_runs"`

	TotalObservations     int `json:"total_observations"`
	CertifiedObservations int `json:"certified_observations"`
	AmbiguousObservations int `json:"ambiguous_observations"`

	ArgmaxFlips       int `json:"argmax_flips"`
	ReserveViolations int `json:"reserve_policy_violations"`

	MaxLogitAbsoluteError float64 `json:"max_logit_absolute_error"`
	MaxCapRequired        float64 `json:"max_cap_required"`

	Observations []MulticlassSampleObservation `json:"observations"`
}

// CertifyMulticlassArgmaxBounds applies the proposition
//
//	z_c* - z_j > B_c* + B_j  for every j != c*.
//
// Equality is not accepted: it establishes only a non-negative approximate
// gap, so a tie and the deterministic class-index rule could change the class.
func CertifyMulticlassArgmaxBounds(
	plainLogits []float64,
	errorBounds []float64,
) (MulticlassBoundCertificate, error) {
	if err := validateLogitVector("plaintext", plainLogits); err != nil {
		return MulticlassBoundCertificate{}, err
	}
	if len(errorBounds) != len(plainLogits) {
		return MulticlassBoundCertificate{}, fmt.Errorf(
			"error-bound count %d does not match class count %d",
			len(errorBounds),
			len(plainLogits),
		)
	}
	for index, bound := range errorBounds {
		if !isNonNegativeFinite(bound) {
			return MulticlassBoundCertificate{}, fmt.Errorf(
				"error bound %d must be finite and non-negative",
				index,
			)
		}
	}
	top, runnerUp, gap, tied := topTwoClasses(plainLogits)
	certificate := MulticlassBoundCertificate{
		SchemaVersion:   MulticlassDecisionContractSchemaV2,
		TieBreak:        DeterministicLowestIndexTieBreak,
		PlainClass:      top,
		RunnerUp:        runnerUp,
		TopTwoGap:       gap,
		PlainTie:        tied,
		StrictlyProved:  !tied,
		MinimumGapSlack: math.Inf(1),
	}
	if tied {
		certificate.StrictlyProved = false
		certificate.MinimumGapSlack = 0
		// MinimumCap is not applicable to a zero-gap plaintext tie. Keep the
		// numeric evidence JSON-safe and use PlainTie as the fail-closed state.
		certificate.MinimumCap = 0
		return certificate, nil
	}
	for classIndex := range plainLogits {
		if classIndex == top {
			continue
		}
		classGap := plainLogits[top] - plainLogits[classIndex]
		boundSum := errorBounds[top] + errorBounds[classIndex]
		slack := classGap - boundSum
		certificate.MinimumGapSlack = math.Min(
			certificate.MinimumGapSlack,
			slack,
		)
		certificate.MinimumCap = math.Max(
			certificate.MinimumCap,
			boundSum/classGap,
		)
		if !(classGap > boundSum) {
			certificate.StrictlyProved = false
		}
	}
	return certificate, nil
}

// CertifyMulticlassUniformBound is the uniform-bound corollary 2B < g(x).
func CertifyMulticlassUniformBound(
	plainLogits []float64,
	bound float64,
) (MulticlassBoundCertificate, error) {
	if !isNonNegativeFinite(bound) {
		return MulticlassBoundCertificate{}, fmt.Errorf(
			"uniform error bound must be finite and non-negative",
		)
	}
	bounds := make([]float64, len(plainLogits))
	for index := range bounds {
		bounds[index] = bound
	}
	return CertifyMulticlassArgmaxBounds(plainLogits, bounds)
}

// AggregateObservedMulticlassCandidate applies the rho-utilization policy to
// finite encrypted observations. Samples with a plaintext top-two gap no
// larger than marginFloor are V_amb and excluded from the finite SAFE claim.
func AggregateObservedMulticlassCandidate(
	samples []MulticlassObservedSample,
	failedRuns int,
	marginFloor float64,
	marginUtilizationCap float64,
) (MulticlassObservedAggregation, error) {
	if len(samples) == 0 {
		return MulticlassObservedAggregation{}, fmt.Errorf(
			"multiclass candidate has no validation samples",
		)
	}
	if failedRuns < 0 {
		return MulticlassObservedAggregation{}, fmt.Errorf(
			"failed runs must be non-negative",
		)
	}
	if !isFinite(marginFloor) || marginFloor < 0 {
		return MulticlassObservedAggregation{}, fmt.Errorf(
			"margin floor must be finite and non-negative",
		)
	}
	if !isFinite(marginUtilizationCap) ||
		marginUtilizationCap <= 0 || marginUtilizationCap > 1 {
		return MulticlassObservedAggregation{}, fmt.Errorf(
			"margin utilization cap must be in (0, 1]",
		)
	}

	successRuns := len(samples[0].ApproxLogits)
	if successRuns == 0 {
		return MulticlassObservedAggregation{}, fmt.Errorf(
			"multiclass candidate has no successful key runs",
		)
	}
	aggregation := MulticlassObservedAggregation{
		SchemaVersion:        MulticlassDecisionContractSchemaV2,
		MarginFloor:          marginFloor,
		MarginUtilizationCap: marginUtilizationCap,
		SuccessRuns:          successRuns,
		FailedRuns:           failedRuns,
		Observations: make(
			[]MulticlassSampleObservation,
			0,
			len(samples)*successRuns,
		),
	}
	seen := make(map[string]struct{}, len(samples))
	for sampleIndex, sample := range samples {
		if sample.ID == "" {
			return MulticlassObservedAggregation{}, fmt.Errorf(
				"multiclass sample %d has an empty ID",
				sampleIndex,
			)
		}
		if _, exists := seen[sample.ID]; exists {
			return MulticlassObservedAggregation{}, fmt.Errorf(
				"duplicate multiclass sample ID %q",
				sample.ID,
			)
		}
		seen[sample.ID] = struct{}{}
		if err := validateLogitVector("plaintext", sample.PlainLogits); err != nil {
			return MulticlassObservedAggregation{}, fmt.Errorf(
				"sample %q: %w",
				sample.ID,
				err,
			)
		}
		if len(sample.ApproxLogits) != successRuns {
			return MulticlassObservedAggregation{}, fmt.Errorf(
				"sample %q has %d key runs; expected %d",
				sample.ID,
				len(sample.ApproxLogits),
				successRuns,
			)
		}
		plainTop, plainRunnerUp, gap, tied := topTwoClasses(
			sample.PlainLogits,
		)
		certifiable := !tied && gap > marginFloor
		if certifiable {
			aggregation.VCert++
		} else {
			aggregation.VAmb++
		}
		for keyRunIndex, approximate := range sample.ApproxLogits {
			if err := validateLogitVector("CKKS", approximate); err != nil {
				return MulticlassObservedAggregation{}, fmt.Errorf(
					"sample %q key run %d: %w",
					sample.ID,
					keyRunIndex+1,
					err,
				)
			}
			if len(approximate) != len(sample.PlainLogits) {
				return MulticlassObservedAggregation{}, fmt.Errorf(
					"sample %q key run %d class count %d; expected %d",
					sample.ID,
					keyRunIndex+1,
					len(approximate),
					len(sample.PlainLogits),
				)
			}
			approxTop, _, _, _ := topTwoClasses(approximate)
			errors := make([]float64, len(approximate))
			for classIndex := range approximate {
				errors[classIndex] = math.Abs(
					approximate[classIndex] - sample.PlainLogits[classIndex],
				)
				aggregation.MaxLogitAbsoluteError = math.Max(
					aggregation.MaxLogitAbsoluteError,
					errors[classIndex],
				)
			}
			boundCertificate, err := CertifyMulticlassArgmaxBounds(
				sample.PlainLogits,
				errors,
			)
			if err != nil {
				return MulticlassObservedAggregation{}, err
			}
			reservePass := false
			minimumCap := boundCertificate.MinimumCap
			if certifiable {
				reservePass = minimumCap < marginUtilizationCap
				aggregation.MaxCapRequired = math.Max(
					aggregation.MaxCapRequired,
					minimumCap,
				)
			}
			flip := approxTop != plainTop
			violation := certifiable && !reservePass
			if certifiable && flip {
				aggregation.ArgmaxFlips++
			}
			if violation {
				aggregation.ReserveViolations++
			}
			observation := MulticlassSampleObservation{
				SampleID: sample.ID,
				KeyRun:   keyRunIndex + 1,
				PlainLogits: append(
					[]float64(nil),
					sample.PlainLogits...,
				),
				CKKSLogits:             append([]float64(nil), approximate...),
				AbsErrors:              errors,
				PlainTop1:              plainTop,
				PlainTop2:              plainRunnerUp,
				CKKSTop1:               approxTop,
				TopTwoGap:              gap,
				PairwiseDecisionBudget: marginUtilizationCap * gap,
				MinimumCapRequired:     minimumCap,
				Certifiable:            certifiable,
				PlainTie:               tied,
				ArgmaxFlip:             flip,
				ReservePolicyPass:      reservePass,
				ReserveViolation:       violation,
			}
			aggregation.Observations = append(
				aggregation.Observations,
				observation,
			)
		}
	}
	aggregation.TotalObservations = len(aggregation.Observations)
	aggregation.CertifiedObservations = aggregation.VCert * successRuns
	aggregation.AmbiguousObservations = aggregation.VAmb * successRuns
	switch {
	case failedRuns > 0:
		aggregation.Status = StatusFailed
		aggregation.Reason = "one or more declared fresh-key runs failed"
	case aggregation.VCert == 0:
		aggregation.Status = StatusAmbiguous
		aggregation.Reason = "no sample has a strict top-two gap above the margin floor"
	case aggregation.ArgmaxFlips > 0 || aggregation.ReserveViolations > 0:
		aggregation.Status = StatusRejected
		aggregation.Reason = fmt.Sprintf(
			"rejected on V_cert: argmax_flips=%d reserve_policy_violations=%d",
			aggregation.ArgmaxFlips,
			aggregation.ReserveViolations,
		)
	default:
		aggregation.Status = StatusSafe
		aggregation.Reason = fmt.Sprintf(
			"zero argmax flips and zero reserve-policy violations on V_cert=%d",
			aggregation.VCert,
		)
	}
	return aggregation, nil
}

func validateLogitVector(label string, logits []float64) error {
	if len(logits) < 2 {
		return fmt.Errorf("%s logits require at least two classes", label)
	}
	for index, value := range logits {
		if !isFinite(value) {
			return fmt.Errorf(
				"%s logit %d must be finite",
				label,
				index,
			)
		}
	}
	return nil
}

// topTwoClasses returns the deterministic lowest-index top class and runner-up.
// tied reports any equality at the maximum plaintext value.
func topTwoClasses(logits []float64) (
	top int,
	runnerUp int,
	gap float64,
	tied bool,
) {
	top = 0
	for index := 1; index < len(logits); index++ {
		if logits[index] > logits[top] {
			top = index
		}
	}
	runnerUp = -1
	for index := range logits {
		if index == top {
			continue
		}
		if runnerUp == -1 || logits[index] > logits[runnerUp] {
			runnerUp = index
		}
	}
	gap = logits[top] - logits[runnerUp]
	for index := range logits {
		if index != top && logits[index] == logits[top] {
			tied = true
			break
		}
	}
	return top, runnerUp, gap, tied
}
