package ckksplanner

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
)

const (
	SecurityPolicyV2ID     = "security_guidelines_cic2025_table5_2_ternary_128_v2"
	LegacySecurityPolicyID = "he_security_guidelines_2024_ternary_classical_128"

	SecurityAdmissionPass = "PASS"
	SecurityAdmissionFail = "FAIL"
)

// RuntimeDistribution records the concrete Lattigo distribution and its
// canonical parameters without claiming that it is identical to the table's
// sigma=3.19 model.
type RuntimeDistribution struct {
	ConcreteType string  `json:"concrete_type"`
	P            float64 `json:"p,omitempty"`
	Sigma        float64 `json:"sigma,omitempty"`
	Bound        float64 `json:"bound,omitempty"`
}

// ModulusSemantics defines which modulus is checked for each runtime object.
type ModulusSemantics struct {
	CiphertextObject    string `json:"ciphertext_object"`
	EvaluationKeyObject string `json:"evaluation_key_object"`
	FinalAdmission      string `json:"final_admission"`
}

// LegacySecurityEnvelope reproduces the policy attached to pre-V2 evidence.
func LegacySecurityEnvelope() SecurityEnvelope {
	return SecurityEnvelope{
		ID:                 LegacySecurityPolicyID,
		SchemaVersion:      1,
		PolicyVersion:      "v1",
		Source:             "https://doi.org/10.62056/anxra69p1",
		SecurityBits:       128,
		SecretDistribution: "uniform_ternary",
		ErrorSigma:         3.2,
		Limits: []SecurityLimit{
			{LogN: 12, MaxLogQPBits: 108},
			{LogN: 13, MaxLogQPBits: 217},
			{LogN: 14, MaxLogQPBits: 438},
			{LogN: 15, MaxLogQPBits: 881},
		},
	}
}

// SecurityPolicyDigest returns the digest of the canonical JSON encoding.
func SecurityPolicyDigest(policy SecurityEnvelope) (string, error) {
	encoded, err := canonicalPolicyJSON(policy)
	if err != nil {
		return "", fmt.Errorf("marshal security policy: %w", err)
	}
	sum := sha256.Sum256(encoded)
	return "sha256:" + hex.EncodeToString(sum[:]), nil
}

// AssessSecurity applies the policy independently to ciphertext-Q and
// evaluation-key-QP, then requires both object checks to pass.
func AssessSecurity(
	spec CKKSParameterLiteralSpec,
	targetBits int,
	policy SecurityEnvelope,
) (SecurityAssessment, error) {
	limit, ok := securityLimitForLogN(policy, spec.LogN)
	if !ok {
		return SecurityAssessment{}, fmt.Errorf(
			"security policy %s has no LogN=%d limit",
			policy.ID,
			spec.LogN,
		)
	}

	logQ := sumInts(spec.LogQ)
	logP := sumInts(spec.LogP)
	logQP := logQ + logP
	qHeadroom := limit.MaxLogQPBits - logQ
	qpHeadroom := limit.MaxLogQPBits - logQP
	qAdmission := SecurityAdmissionPass
	if qHeadroom < 0 {
		qAdmission = SecurityAdmissionFail
	}
	qpAdmission := SecurityAdmissionPass
	if qpHeadroom < 0 {
		qpAdmission = SecurityAdmissionFail
	}
	finalAdmission := SecurityAdmissionPass
	if qAdmission != SecurityAdmissionPass ||
		qpAdmission != SecurityAdmissionPass {
		finalAdmission = SecurityAdmissionFail
	}

	reason := "ciphertext Q and evaluation-key QP are within the conservative Table 5.2 cap"
	if finalAdmission == SecurityAdmissionFail {
		reason = "at least one required runtime object exceeds the conservative Table 5.2 cap"
	}

	return SecurityAssessment{
		EnvelopeID:      policy.ID,
		TargetBits:      targetBits,
		DeclaredLogQP:   logQP,
		MaxAllowedLogQP: limit.MaxLogQPBits,
		HeadroomBits:    qpHeadroom,
		AdmissionStatus: finalAdmission,

		LogQ:                      logQ,
		LogP:                      logP,
		LogQP:                     logQP,
		CiphertextQAdmission:      qAdmission,
		EvaluationKeyQPAdmission:  qpAdmission,
		FinalAdmission:            finalAdmission,
		CiphertextHeadroomBits:    qHeadroom,
		EvaluationKeyHeadroomBits: qpHeadroom,
		AdmissionReason:           reason,
	}, nil
}

func securityLimitForLogN(
	policy SecurityEnvelope,
	logN int,
) (SecurityLimit, bool) {
	for _, limit := range policy.Limits {
		if limit.LogN == logN {
			return limit, true
		}
	}
	return SecurityLimit{}, false
}
