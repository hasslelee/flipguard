package certify

// MarginUtilizationPolicyView is a paper-facing interpretation of the legacy
// SafetyFactor field. It does not change certification or selection behavior.
type MarginUtilizationPolicyView struct {
	MarginUtilizationCap   float64 `json:"margin_utilization_cap"`
	ReservedMarginFraction float64 `json:"reserved_margin_fraction"`
	LegacyField            string  `json:"legacy_field"`
	LegacyValue            float64 `json:"legacy_value"`
}

// InterpretSafetyFactor maps the backward-compatible execution field to its
// paper-facing operational meaning.
func InterpretSafetyFactor(safetyFactor float64) MarginUtilizationPolicyView {
	return MarginUtilizationPolicyView{
		MarginUtilizationCap:   safetyFactor,
		ReservedMarginFraction: 1 - safetyFactor,
		LegacyField:            "SafetyFactor",
		LegacyValue:            safetyFactor,
	}
}

// OperationalAcceptanceBudget returns rho*m for the supplied decision margin.
// The strict decision-preservation theorem itself uses error < margin.
func OperationalAcceptanceBudget(
	margin float64,
	view MarginUtilizationPolicyView,
) float64 {
	return view.MarginUtilizationCap * margin
}
