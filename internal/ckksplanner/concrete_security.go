package ckksplanner

import (
	"fmt"
	"math/big"
)

// AssessConcreteSecurity applies the frozen policy caps to actual ordered
// modulus primes. It is separate from AssessSecurity so historical
// logarithmic-literal evidence retains its source binding and byte semantics.
func AssessConcreteSecurity(
	spec CKKSParameterLiteralSpec,
	targetBits int,
	policy SecurityEnvelope,
) (SecurityAssessment, error) {
	if len(spec.LogQ) > 0 || len(spec.LogP) > 0 {
		return SecurityAssessment{}, fmt.Errorf(
			"concrete CKKS literal includes logarithmic moduli",
		)
	}
	if len(spec.Q) == 0 || len(spec.P) == 0 {
		return SecurityAssessment{}, fmt.Errorf(
			"concrete CKKS literal requires both Q and P",
		)
	}
	limit, ok := securityLimitForLogN(policy, spec.LogN)
	if !ok {
		return SecurityAssessment{}, fmt.Errorf(
			"security policy %s has no LogN=%d limit",
			policy.ID,
			spec.LogN,
		)
	}

	qProduct, err := concreteModulusProduct(spec.Q)
	if err != nil {
		return SecurityAssessment{}, fmt.Errorf("concrete Q: %w", err)
	}
	pProduct, err := concreteModulusProduct(spec.P)
	if err != nil {
		return SecurityAssessment{}, fmt.Errorf("concrete P: %w", err)
	}
	qpProduct := new(big.Int).Mul(
		new(big.Int).Set(qProduct),
		pProduct,
	)
	logQ := qProduct.BitLen()
	logP := pProduct.BitLen()
	logQP := qpProduct.BitLen()
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

	reason := "concrete ciphertext Q and evaluation-key QP products are within the conservative Table 5.2 cap"
	if finalAdmission == SecurityAdmissionFail {
		reason = "at least one concrete runtime-object modulus product exceeds the conservative Table 5.2 cap"
	}
	return SecurityAssessment{
		EnvelopeID:      policy.ID,
		TargetBits:      targetBits,
		DeclaredLogQP:   logQP,
		MaxAllowedLogQP: limit.MaxLogQPBits,
		HeadroomBits:    qpHeadroom,
		AdmissionStatus: finalAdmission,
		Measurement:     "ceil_log2_concrete_modulus_product",

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

func concreteModulusProduct(values []uint64) (*big.Int, error) {
	product := big.NewInt(1)
	for index, value := range values {
		if value <= 1 {
			return nil, fmt.Errorf(
				"modulus[%d] must be greater than one",
				index,
			)
		}
		product.Mul(product, new(big.Int).SetUint64(value))
	}
	return product, nil
}
