package externaladapter

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const testOrionConfig = `comment: test
ckks_params:
  LogN: 13
  LogQ: [29, 26, 26, 26, 26, 26]
  LogP: [29, 29]
  LogScale: 26
  H: 8192
  RingType: ConjugateInvariant
orion:
  margin: 2
  embedding_method: hybrid
  backend: lattigo
  fuse_modules: true
  debug: false
  diags_path: ""
  keys_path: ""
  io_mode: none
`

func TestAuditOrionConfigBlocksSemanticMismatch(t *testing.T) {
	path := filepath.Join(t.TempDir(), "mlp.yml")
	if err := os.WriteFile(path, []byte(testOrionConfig), 0o600); err != nil {
		t.Fatal(err)
	}
	report, err := AuditOrionConfig(path, OrionAdapterInput{
		Source: ExternalSourceBinding{
			RepositoryURL: "https://github.com/baahl-nyu/orion",
			Commit:        strings.Repeat("a", 40),
			Path:          "configs/mlp.yml",
			SHA256:        digestBytes([]byte(testOrionConfig)),
		},
		Backend: OrionBackendBinding{
			Module:  "github.com/baahl-nyu/lattigo/v6",
			Version: "v6.2.0",
			Commit:  strings.Repeat("b", 40),
		},
	})
	if err != nil {
		t.Fatalf("AuditOrionConfig failed: %v", err)
	}
	if report.Status != OrionImportBlocked ||
		report.EncryptedExecution ||
		report.CandidateRequestEmitted ||
		report.PolicyModification != 0 {
		t.Fatalf("unexpected report gate: %+v", report)
	}
	wantReasons := []string{
		"RING_TYPE_MISMATCH",
		"SECRET_DISTRIBUTION_MISMATCH",
		"ERROR_DISTRIBUTION_NOT_SERIALIZED",
		"BACKEND_IMPLEMENTATION_NOT_IDENTICAL",
		"SECURITY_V2_INADMISSIBLE",
	}
	for _, want := range wantReasons {
		if !contains(report.BlockReasons, want) {
			t.Fatalf("missing reason %s: %v", want, report.BlockReasons)
		}
	}
	if report.SecurityAssessment == nil ||
		report.SecurityAssessment.LogQP != 217 ||
		report.SecurityAssessment.HeadroomBits != -3 {
		t.Fatalf(
			"unexpected security assessment: %+v",
			report.SecurityAssessment,
		)
	}
}

func TestAuditOrionConfigRejectsDigestMutation(t *testing.T) {
	path := filepath.Join(t.TempDir(), "mlp.yml")
	if err := os.WriteFile(path, []byte(testOrionConfig), 0o600); err != nil {
		t.Fatal(err)
	}
	_, err := AuditOrionConfig(path, OrionAdapterInput{
		Source: ExternalSourceBinding{
			RepositoryURL: "https://github.com/baahl-nyu/orion",
			Commit:        strings.Repeat("a", 40),
			Path:          "configs/mlp.yml",
			SHA256:        "sha256:" + strings.Repeat("0", 64),
		},
		Backend: OrionBackendBinding{
			Module:  "github.com/baahl-nyu/lattigo/v6",
			Version: "v6.2.0",
			Commit:  strings.Repeat("b", 40),
		},
	})
	if err == nil || !strings.Contains(err.Error(), "digest mismatch") {
		t.Fatalf("expected digest mismatch, got %v", err)
	}
}

func TestAuditOrionConfigRejectsUnknownField(t *testing.T) {
	path := filepath.Join(t.TempDir(), "mlp.yml")
	data := []byte(testOrionConfig + "unknown: true\n")
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatal(err)
	}
	_, err := AuditOrionConfig(path, OrionAdapterInput{
		Source: ExternalSourceBinding{
			RepositoryURL: "https://github.com/baahl-nyu/orion",
			Commit:        strings.Repeat("a", 40),
			Path:          "configs/mlp.yml",
			SHA256:        digestBytes(data),
		},
		Backend: OrionBackendBinding{
			Module:  "github.com/baahl-nyu/lattigo/v6",
			Version: "v6.2.0",
			Commit:  strings.Repeat("b", 40),
		},
	})
	if err == nil || !strings.Contains(err.Error(), "field unknown") {
		t.Fatalf("expected strict YAML failure, got %v", err)
	}
}

func contains(values []string, target string) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}
