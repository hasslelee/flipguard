//go:build validationidentity

package ckksplanner

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestValidationSemanticIdentityIgnoresRepresentationOnlyChanges(
	t *testing.T,
) {
	modelPath, _ := writeLinearFixture(t, false)
	root := t.TempDir()
	left := filepath.Join(root, "left.csv")
	right := filepath.Join(root, "right.csv")
	leftData := fmt.Sprintf(strings.Join([]string{
		"row_id,label,polynomial_score,plaintext_decision,x_0,unused",
		"0,0,%.17g,false,-1.0,left",
		"1,1,%.17g,true,1.0,right",
		"",
	}, "\n"), linearFixtureScore(-1), linearFixtureScore(1))
	rightData := fmt.Sprintf(strings.Join([]string{
		"row_id,label,polynomial_score,plaintext_decision,x_0",
		"0,0,%.17e,FALSE,-1e0",
		"1,1,%.17e,TRUE,1e0",
		"",
	}, "\r\n"), linearFixtureScore(-1), linearFixtureScore(1))
	if err := os.WriteFile(left, []byte(leftData), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(right, []byte(rightData), 0o600); err != nil {
		t.Fatal(err)
	}
	leftIdentity := computeFixtureIdentity(t, modelPath, left)
	rightIdentity := computeFixtureIdentity(t, modelPath, right)
	if leftIdentity.File.RawSHA256 == rightIdentity.File.RawSHA256 {
		t.Fatal("representation variants unexpectedly have equal raw digest")
	}
	if leftIdentity.ValidationSemanticDigest !=
		rightIdentity.ValidationSemanticDigest {
		t.Fatalf(
			"semantic digest changed across representation variants: %s != %s",
			leftIdentity.ValidationSemanticDigest,
			rightIdentity.ValidationSemanticDigest,
		)
	}
	if leftIdentity.File.OrderedRowIDDigest !=
		rightIdentity.File.OrderedRowIDDigest {
		t.Fatal("ordered row identity changed")
	}
}

func TestValidationSemanticIdentityRejectsSemanticMutations(t *testing.T) {
	modelPath, _ := writeLinearFixture(t, false)
	base := fmt.Sprintf(
		"row_id,label,polynomial_score,plaintext_decision,x_0\n"+
			"0,0,%.17g,false,-1\n"+
			"1,1,%.17g,true,1\n",
		linearFixtureScore(-1),
		linearFixtureScore(1),
	)
	cases := map[string]string{
		"feature": strings.Replace(base, ",-1\n", ",-0.9\n", 1),
		"row_id":  strings.Replace(base, "0,0,", "2,0,", 1),
		"order": fmt.Sprintf(
			"row_id,label,polynomial_score,plaintext_decision,x_0\n"+
				"1,1,%.17g,true,1\n"+
				"0,0,%.17g,false,-1\n",
			linearFixtureScore(1),
			linearFixtureScore(-1),
		),
	}
	root := t.TempDir()
	basePath := filepath.Join(root, "base.csv")
	if err := os.WriteFile(basePath, []byte(base), 0o600); err != nil {
		t.Fatal(err)
	}
	baseline := computeFixtureIdentity(t, modelPath, basePath)
	for name, data := range cases {
		t.Run(name, func(t *testing.T) {
			path := filepath.Join(root, name+".csv")
			if err := os.WriteFile(path, []byte(data), 0o600); err != nil {
				t.Fatal(err)
			}
			identity, err := ComputeValidationSemanticIdentity(
				fixtureIdentityOptions(modelPath, path),
			)
			if name == "feature" {
				if err == nil {
					t.Fatal("changed feature with stale score was accepted")
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if identity.ValidationSemanticDigest ==
				baseline.ValidationSemanticDigest {
				t.Fatalf("%s mutation did not change semantic digest", name)
			}
			if identity.File.OrderedRowIDDigest ==
				baseline.File.OrderedRowIDDigest {
				t.Fatalf("%s mutation did not change ordered row digest", name)
			}
		})
	}
}

func TestValidationSemanticIdentityRejectsModelAndThresholdChanges(
	t *testing.T,
) {
	modelPath, _ := writeLinearFixture(t, false)
	root := t.TempDir()
	validationPath := filepath.Join(root, "validation.csv")
	data := fmt.Sprintf(
		"row_id,label,polynomial_score,plaintext_decision,x_0\n"+
			"0,0,%.17g,false,-1\n"+
			"1,1,%.17g,true,1\n",
		linearFixtureScore(-1),
		linearFixtureScore(1),
	)
	if err := os.WriteFile(validationPath, []byte(data), 0o600); err != nil {
		t.Fatal(err)
	}
	baseline := computeFixtureIdentity(t, modelPath, validationPath)
	modelBytes, err := os.ReadFile(modelPath)
	if err != nil {
		t.Fatal(err)
	}
	var model map[string]any
	if err := json.Unmarshal(modelBytes, &model); err != nil {
		t.Fatal(err)
	}
	model["dataset_name"] = "representation-only model mutation"
	changedModelPath := filepath.Join(root, "model.json")
	changedModelBytes, err := json.Marshal(model)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(
		changedModelPath,
		changedModelBytes,
		0o600,
	); err != nil {
		t.Fatal(err)
	}
	changedModel := computeFixtureIdentity(
		t,
		changedModelPath,
		validationPath,
	)
	if changedModel.ValidationSemanticDigest ==
		baseline.ValidationSemanticDigest {
		t.Fatal("model artifact mutation did not change semantic identity")
	}

	polynomial := model["polynomial_score"].(map[string]any)
	polynomial["decision_threshold"] = 0.4
	thresholdBytes, err := json.Marshal(model)
	if err != nil {
		t.Fatal(err)
	}
	thresholdPath := filepath.Join(root, "threshold.json")
	if err := os.WriteFile(thresholdPath, thresholdBytes, 0o600); err != nil {
		t.Fatal(err)
	}
	_, err = ComputeValidationSemanticIdentity(
		fixtureIdentityOptions(thresholdPath, validationPath),
	)
	if err == nil ||
		!strings.Contains(err.Error(), "stored decision does not match replay") {
		t.Fatalf("threshold mutation was not rejected: %v", err)
	}
}

func TestValidationSemanticIdentityGoldenVector(t *testing.T) {
	modelPath, _ := writeLinearFixture(t, false)
	root := t.TempDir()
	validationPath := filepath.Join(root, "validation.csv")
	data := fmt.Sprintf(
		"row_id,label,polynomial_score,plaintext_decision,x_0\n"+
			"0,0,%.17g,false,-1\n"+
			"1,1,%.17g,true,1\n",
		linearFixtureScore(-1),
		linearFixtureScore(1),
	)
	if err := os.WriteFile(validationPath, []byte(data), 0o600); err != nil {
		t.Fatal(err)
	}
	identity := computeFixtureIdentity(t, modelPath, validationPath)
	const want = "sha256:e25d4bc0eb867f577c4c33b103a8c63d7a2961cc97f5fffeb95af5b7cf73e69f"
	if identity.ValidationSemanticDigest != want {
		t.Fatalf(
			"golden semantic digest changed: got %s want %s",
			identity.ValidationSemanticDigest,
			want,
		)
	}
}

func computeFixtureIdentity(
	t *testing.T,
	modelPath string,
	validationPath string,
) ValidationSemanticIdentity {
	t.Helper()
	identity, err := ComputeValidationSemanticIdentity(
		fixtureIdentityOptions(modelPath, validationPath),
	)
	if err != nil {
		t.Fatal(err)
	}
	return identity
}

func fixtureIdentityOptions(
	modelPath string,
	validationPath string,
) ValidationSemanticIdentityOptions {
	return ValidationSemanticIdentityOptions{
		ModelPath:      modelPath,
		ValidationPath: validationPath,
		DatasetID:      "toy",
		ModelID:        "linear_poly3",
		SplitID:        "split_seed_0",
		PartitionRole:  "development_ablation",
		MarginFloor:    0.001,
	}
}
