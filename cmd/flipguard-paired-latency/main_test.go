package main

import (
	"testing"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
)

func TestParseCatalogCandidate(t *testing.T) {
	profile, mode, err := parseCatalogCandidate(
		"short_chain_6_scale40__baseline_non_rescale",
	)
	if err != nil {
		t.Fatalf("parse candidate: %v", err)
	}
	if profile != "short_chain_6_scale40" ||
		mode != ckksbackend.CKKSEvaluationModeNaive {
		t.Fatalf(
			"unexpected candidate parse profile=%s mode=%s",
			profile,
			mode,
		)
	}

	profile, mode, err = parseCatalogCandidate(
		"default__rescale_aware",
	)
	if err != nil {
		t.Fatalf("parse rescale candidate: %v", err)
	}
	if profile != "default" ||
		mode != ckksbackend.CKKSEvaluationModeRescale {
		t.Fatalf(
			"unexpected rescale parse profile=%s mode=%s",
			profile,
			mode,
		)
	}
}

func TestParseCatalogCandidateRejectsUnknownPath(t *testing.T) {
	if _, _, err := parseCatalogCandidate("default__unknown"); err == nil {
		t.Fatal("expected unknown path error")
	}
}
