package ckksplanner

import "github.com/hasslelee/flipguard/internal/ckksbackend"

// Instrumentation only. Keys themselves are never persisted; the caller binds
// each freshly generated context to its run/trial/key ordinal.
type TabularKeyRunEvidence struct {
	KeyRun      int                                      `json:"key_run"`
	CandidateID string                                   `json:"candidate_id"`
	Records     []ckksbackend.CKKSTabularInferenceRecord `json:"records"`
	Summary     ckksbackend.CKKSTabularInferenceSummary  `json:"summary"`
	ParameterMS float64                                  `json:"parameter_ms"`
	BackendMS   float64                                  `json:"backend_ms"`
	Q           []uint64                                 `json:"q"`
	P           []uint64                                 `json:"p"`
}
