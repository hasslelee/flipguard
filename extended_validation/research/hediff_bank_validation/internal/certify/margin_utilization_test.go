package certify

import "testing"

func TestInterpretSafetyFactorAsMarginUtilization(t *testing.T) {
	view := InterpretSafetyFactor(0.5)
	if view.MarginUtilizationCap != 0.5 {
		t.Fatalf("unexpected utilization cap %.12g", view.MarginUtilizationCap)
	}
	if view.ReservedMarginFraction != 0.5 {
		t.Fatalf(
			"unexpected reserved fraction %.12g",
			view.ReservedMarginFraction,
		)
	}
	if view.LegacyField != "SafetyFactor" || view.LegacyValue != 0.5 {
		t.Fatalf("legacy alias was not preserved: %+v", view)
	}
	if got := OperationalAcceptanceBudget(0.02, view); got != 0.01 {
		t.Fatalf("unexpected operational budget %.12g", got)
	}
}
