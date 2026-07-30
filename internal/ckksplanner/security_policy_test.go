package ckksplanner

import "testing"

func TestSecurityPolicyV2PublishedCapsAndRuntimeDistributions(t *testing.T) {
	policy := DefaultSecurityEnvelope()
	if policy.ID != SecurityPolicyV2ID ||
		policy.TableNumber != "Table 5.2" ||
		policy.TableErrorSigma != 3.19 {
		t.Fatalf("unexpected V2 policy metadata: %+v", policy)
	}
	expected := map[int]int{12: 106, 13: 214, 14: 430, 15: 868}
	for _, limit := range policy.Limits {
		if expected[limit.LogN] != limit.MaxLogQPBits {
			t.Fatalf("unexpected LogN=%d cap: %+v", limit.LogN, limit)
		}
		delete(expected, limit.LogN)
	}
	if len(expected) != 0 {
		t.Fatalf("missing caps: %+v", expected)
	}
	if policy.RuntimeXs.ConcreteType != "ring.Ternary" ||
		policy.RuntimeXs.P != 2.0/3.0 ||
		policy.RuntimeXe.ConcreteType != "ring.DiscreteGaussian" ||
		policy.RuntimeXe.Sigma != 3.2 ||
		policy.RuntimeXe.Bound != 19.2 {
		t.Fatalf("unexpected runtime distributions: %+v %+v", policy.RuntimeXs, policy.RuntimeXe)
	}
}

func TestAssessSecuritySeparatesCiphertextAndEvaluationKeyObjects(t *testing.T) {
	spec := CKKSParameterLiteralSpec{
		LogN: 13,
		LogQ: []int{60, 60, 60},
		LogP: []int{60},
	}
	assessment, err := AssessSecurity(spec, 128, DefaultSecurityEnvelope())
	if err != nil {
		t.Fatalf("assess security: %v", err)
	}
	if assessment.CiphertextQAdmission != SecurityAdmissionPass ||
		assessment.EvaluationKeyQPAdmission != SecurityAdmissionFail ||
		assessment.FinalAdmission != SecurityAdmissionFail {
		t.Fatalf("unexpected object admissions: %+v", assessment)
	}
	if assessment.CiphertextHeadroomBits != 34 ||
		assessment.EvaluationKeyHeadroomBits != -26 {
		t.Fatalf("unexpected headroom: %+v", assessment)
	}
}

func TestAssessSecurityUsesConcreteModulusProductBits(t *testing.T) {
	spec := CKKSParameterLiteralSpec{
		LogN: 14,
		Q: []uint64{
			1152921504606748673,
			1146881,
			1179649,
			786433,
			1376257,
			557057,
			1769473,
		},
		P:               []uint64{2305843009211662337},
		LogDefaultScale: 20,
	}
	assessment, err := AssessConcreteSecurity(
		spec,
		128,
		DefaultSecurityEnvelope(),
	)
	if err != nil {
		t.Fatalf("assess concrete security: %v", err)
	}
	if assessment.LogQ != 181 ||
		assessment.LogP != 61 ||
		assessment.LogQP != 242 ||
		assessment.EvaluationKeyHeadroomBits != 188 ||
		assessment.Measurement !=
			"ceil_log2_concrete_modulus_product" ||
		assessment.FinalAdmission != SecurityAdmissionPass {
		t.Fatalf("unexpected concrete assessment: %+v", assessment)
	}
}

func TestAssessSecurityRejectsMixedModulusRepresentations(t *testing.T) {
	_, err := AssessConcreteSecurity(
		CKKSParameterLiteralSpec{
			LogN: 14,
			LogQ: []int{60},
			LogP: []int{61},
			Q:    []uint64{1152921504606748673},
			P:    []uint64{2305843009211662337},
		},
		128,
		DefaultSecurityEnvelope(),
	)
	if err == nil {
		t.Fatal("expected mixed modulus representation rejection")
	}
}

func TestDirectSynthesisPolicyV2DigestIsStable(t *testing.T) {
	policy := DefaultDirectSynthesisPolicyContract()
	if policy.MaxEncryptedTrials != 4 ||
		policy.PrimaryMarginFloor != 0.001 ||
		policy.PrimaryAlpha != 0.5 ||
		policy.SecurityPolicyID != SecurityPolicyV2ID {
		t.Fatalf("unexpected direct policy: %+v", policy)
	}
	first, err := DirectSynthesisPolicyDigest(policy)
	if err != nil {
		t.Fatal(err)
	}
	second, err := DirectSynthesisPolicyDigest(
		DefaultDirectSynthesisPolicyContract(),
	)
	if err != nil {
		t.Fatal(err)
	}
	if first != second || first == "" {
		t.Fatalf("unstable direct policy digest: %q != %q", first, second)
	}
}
