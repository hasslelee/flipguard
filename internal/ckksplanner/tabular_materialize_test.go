package ckksplanner

import (
	"bytes"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"testing"
)

func TestMaterializeTabularValidationBuildsBoundContract(t *testing.T) {
	modelPath, _ := writeLinearFixture(t, false)
	root := t.TempDir()
	dataPath := filepath.Join(root, "features.csv")
	validationPath := filepath.Join(root, "validation.csv")
	data := []byte(
		"row_id,label,x_0\n" +
			"0,0,-1\n" +
			"1,1,0\n" +
			"2,1,1\n",
	)
	if err := os.WriteFile(dataPath, data, 0o600); err != nil {
		t.Fatalf("write feature data: %v", err)
	}

	first, err := MaterializeTabularValidation(
		modelPath,
		dataPath,
		validationPath,
	)
	if err != nil {
		t.Fatalf("materialize validation: %v", err)
	}
	firstBytes, err := os.ReadFile(validationPath)
	if err != nil {
		t.Fatalf("read materialized validation: %v", err)
	}
	if first.SchemaVersion != 2 ||
		first.Rows != 3 ||
		first.SourceDataSHA256 != digestBytes(data) ||
		first.ValidationSHA256 != digestBytes(firstBytes) {
		t.Fatalf("unexpected materialization summary: %+v", first)
	}
	if !bytes.Contains(
		firstBytes,
		[]byte(TabularValidationMaterializationSchemaV2),
	) || !bytes.Contains(firstBytes, []byte(first.SourceDataSHA256)) {
		t.Fatalf(
			"materialized validation lacks bound provenance:\n%s",
			firstBytes,
		)
	}

	second, err := MaterializeTabularValidation(
		modelPath,
		dataPath,
		validationPath,
	)
	if err != nil {
		t.Fatalf("repeat materialization: %v", err)
	}
	secondBytes, err := os.ReadFile(validationPath)
	if err != nil {
		t.Fatalf("read repeated validation: %v", err)
	}
	if second.ValidationSHA256 != first.ValidationSHA256 ||
		!bytes.Equal(firstBytes, secondBytes) {
		t.Fatal("materialized validation is not deterministic")
	}

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SourceDataPath = dataPath
	options.SplitID = "user_validation"
	options.MarginFloor = 0.01
	contract, err := BuildTabularWorkloadContract(options)
	if err != nil {
		t.Fatalf("build materialized contract: %v", err)
	}
	if contract.SourceData == nil ||
		contract.SourceData.Path != dataPath ||
		contract.SourceData.SHA256 != first.SourceDataSHA256 {
		t.Fatalf(
			"source data was not bound into contract: %+v",
			contract.SourceData,
		)
	}
	if contract.InputMaterialization == nil ||
		contract.InputMaterialization.SourceFeatureSpace !=
			string(TabularDataSpaceModelInput) ||
		contract.InputMaterialization.PreprocessingMethod !=
			TabularPreprocessingIdentityV1 ||
		!contract.InputMaterialization.SourceReplayVerified {
		t.Fatalf(
			"model-input preprocessing was not bound: %+v",
			contract.InputMaterialization,
		)
	}
	if err := verifyContractArtifacts(contract); err != nil {
		t.Fatalf("verify materialized artifacts: %v", err)
	}

	if err := os.WriteFile(
		dataPath,
		append(data, []byte("3,1,2\n")...),
		0o600,
	); err != nil {
		t.Fatalf("mutate source data: %v", err)
	}
	err = verifyContractArtifacts(contract)
	if err == nil || !strings.Contains(
		err.Error(),
		"source data digest changed",
	) {
		t.Fatalf("expected source mutation rejection, got %v", err)
	}
}

func TestBuildContractRejectsTamperedMaterializationProvenance(
	t *testing.T,
) {
	modelPath, _ := writeLinearFixture(t, false)
	root := t.TempDir()
	dataPath := filepath.Join(root, "features.csv")
	validationPath := filepath.Join(root, "validation.csv")
	if err := os.WriteFile(
		dataPath,
		[]byte("row_id,label,x_0\n0,0,-1\n2,1,1\n"),
		0o600,
	); err != nil {
		t.Fatalf("write feature data: %v", err)
	}
	if _, err := MaterializeTabularValidation(
		modelPath,
		dataPath,
		validationPath,
	); err != nil {
		t.Fatalf("materialize validation: %v", err)
	}
	materialized, err := os.ReadFile(validationPath)
	if err != nil {
		t.Fatalf("read materialized validation: %v", err)
	}
	tampered := strings.ReplaceAll(
		string(materialized),
		digestBytes([]byte("row_id,label,x_0\n0,0,-1\n2,1,1\n")),
		"sha256:"+strings.Repeat("0", 64),
	)
	if err := os.WriteFile(
		validationPath,
		[]byte(tampered),
		0o600,
	); err != nil {
		t.Fatalf("write tampered validation: %v", err)
	}

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SourceDataPath = dataPath
	options.SplitID = "user_validation"
	_, err = BuildTabularWorkloadContract(options)
	if err == nil || !strings.Contains(
		err.Error(),
		"does not match source data",
	) {
		t.Fatalf("expected provenance mismatch, got %v", err)
	}
}

func TestBuildContractRejectsPartialMaterializationProvenance(
	t *testing.T,
) {
	modelPath, _ := writeLinearFixture(t, false)
	root := t.TempDir()
	dataPath := filepath.Join(root, "features.csv")
	validationPath := filepath.Join(root, "validation.csv")
	if err := os.WriteFile(
		dataPath,
		[]byte("row_id,label,x_0\n0,0,-1\n2,1,1\n"),
		0o600,
	); err != nil {
		t.Fatalf("write feature data: %v", err)
	}
	if _, err := MaterializeTabularValidation(
		modelPath,
		dataPath,
		validationPath,
	); err != nil {
		t.Fatalf("materialize validation: %v", err)
	}
	materialized, err := os.ReadFile(validationPath)
	if err != nil {
		t.Fatalf("read materialized validation: %v", err)
	}
	records, err := csv.NewReader(bytes.NewReader(materialized)).ReadAll()
	if err != nil {
		t.Fatalf("parse materialized validation: %v", err)
	}
	for index := range records {
		records[index] = append(
			records[index][:5],
			records[index][6:]...,
		)
	}
	var partial bytes.Buffer
	writer := csv.NewWriter(&partial)
	if err := writer.WriteAll(records); err != nil {
		t.Fatalf("write partial provenance fixture: %v", err)
	}
	if err := os.WriteFile(
		validationPath,
		partial.Bytes(),
		0o600,
	); err != nil {
		t.Fatalf("write partial provenance fixture: %v", err)
	}

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SplitID = "user_validation"
	_, err = BuildTabularWorkloadContract(options)
	if err == nil || !strings.Contains(
		err.Error(),
		"provenance columns are incomplete",
	) {
		t.Fatalf("expected incomplete provenance rejection, got %v", err)
	}
}

func TestMaterializeTabularValidationRejectsInvalidFeatureData(
	t *testing.T,
) {
	modelPath, _ := writeLinearFixture(t, false)
	root := t.TempDir()
	dataPath := filepath.Join(root, "features.csv")
	if err := os.WriteFile(
		dataPath,
		[]byte("row_id,label,x_0\n0,2,NaN\n"),
		0o600,
	); err != nil {
		t.Fatalf("write invalid feature data: %v", err)
	}
	_, err := MaterializeTabularValidation(
		modelPath,
		dataPath,
		filepath.Join(root, "validation.csv"),
	)
	if err == nil || !strings.Contains(err.Error(), "label must be 0 or 1") {
		t.Fatalf("expected invalid label rejection, got %v", err)
	}

	if err := os.WriteFile(
		dataPath,
		[]byte("row_id,label,x_0,x_1\n0,0,-1,9\n"),
		0o600,
	); err != nil {
		t.Fatalf("write extra-feature data: %v", err)
	}
	_, err = MaterializeTabularValidationWithOptions(
		modelPath,
		dataPath,
		filepath.Join(root, "validation.csv"),
		TabularMaterializationOptions{
			DataSpace: TabularDataSpaceModelInput,
		},
	)
	if err == nil || !strings.Contains(
		err.Error(),
		"unexpected model-input x_* columns",
	) {
		t.Fatalf("expected extra-feature rejection, got %v", err)
	}
}

func TestMaterializeRawNamedFeaturesAppliesFrozenPreprocessing(
	t *testing.T,
) {
	modelPath := writeRawLinearModelFixture(t)
	root := t.TempDir()
	dataPath := filepath.Join(root, "raw_named.csv")
	validationPath := filepath.Join(root, "validation.csv")
	data := []byte(
		"row_id,label,raw_b,raw_d,unused\n" +
			"0,0,8,25,99\n" +
			"1,1,12,15,100\n",
	)
	if err := os.WriteFile(dataPath, data, 0o600); err != nil {
		t.Fatalf("write named raw data: %v", err)
	}

	materialization, err := MaterializeTabularValidation(
		modelPath,
		dataPath,
		validationPath,
	)
	if err != nil {
		t.Fatalf("materialize named raw data: %v", err)
	}
	if materialization.SourceFeatureSpace !=
		string(TabularDataSpaceRaw) ||
		materialization.PreprocessingMethod !=
			TabularPreprocessingSelectedStandardizationV1 {
		t.Fatalf(
			"unexpected raw materialization summary: %+v",
			materialization,
		)
	}
	records := readCSVFixture(t, validationPath)
	if records[1][10] != "-1" || records[1][11] != "1" ||
		records[2][10] != "1" || records[2][11] != "-1" {
		t.Fatalf(
			"unexpected standardized features: %v / %v",
			records[1],
			records[2],
		)
	}

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SourceDataPath = dataPath
	options.SplitID = "raw_named"
	contract, err := BuildTabularWorkloadContract(options)
	if err != nil {
		t.Fatalf("build raw-data contract: %v", err)
	}
	if contract.InputMaterialization == nil ||
		contract.InputMaterialization.SourceFeatureSpace !=
			string(TabularDataSpaceRaw) ||
		!contract.InputMaterialization.SourceReplayVerified {
		t.Fatalf(
			"raw preprocessing contract missing: %+v",
			contract.InputMaterialization,
		)
	}
}

func TestBuildContractRejectsPreparedRowsThatDoNotMatchRawSource(
	t *testing.T,
) {
	modelPath := writeRawLinearModelFixture(t)
	root := t.TempDir()
	dataPath := filepath.Join(root, "raw_named.csv")
	validationPath := filepath.Join(root, "validation.csv")
	if err := os.WriteFile(
		dataPath,
		[]byte(
			"row_id,label,raw_b,raw_d\n"+
				"0,0,8,25\n"+
				"1,1,12,15\n",
		),
		0o600,
	); err != nil {
		t.Fatalf("write named raw data: %v", err)
	}
	if _, err := MaterializeTabularValidation(
		modelPath,
		dataPath,
		validationPath,
	); err != nil {
		t.Fatalf("materialize named raw data: %v", err)
	}

	records := readCSVFixture(t, validationPath)
	z := -0.25
	score := 0.5 + 0.197*z - 0.004*z*z*z
	records[1][2] = formatMaterializedFloat(z)
	records[1][3] = formatMaterializedFloat(score)
	records[1][4] = "false"
	records[1][10] = "0"
	var tampered bytes.Buffer
	writer := csv.NewWriter(&tampered)
	if err := writer.WriteAll(records); err != nil {
		t.Fatalf("write tampered prepared rows: %v", err)
	}
	if err := os.WriteFile(
		validationPath,
		tampered.Bytes(),
		0o600,
	); err != nil {
		t.Fatalf("replace prepared validation: %v", err)
	}

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SourceDataPath = dataPath
	options.SplitID = "raw_tamper"
	_, err := BuildTabularWorkloadContract(options)
	if err == nil || !strings.Contains(
		err.Error(),
		"does not match source preprocessing",
	) {
		t.Fatalf(
			"expected source/prepared relation rejection, got %v",
			err,
		)
	}
}

func TestMaterializeRawIndexedFeaturesAndRejectsAmbiguousAutoSpace(
	t *testing.T,
) {
	modelPath := writeRawLinearModelFixture(t)
	root := t.TempDir()
	dataPath := filepath.Join(root, "raw_indexed.csv")
	validationPath := filepath.Join(root, "validation.csv")
	if err := os.WriteFile(
		dataPath,
		[]byte(
			"row_id,label,x_1,x_3,x_7\n"+
				"0,0,8,25,99\n",
		),
		0o600,
	); err != nil {
		t.Fatalf("write indexed raw data: %v", err)
	}
	materialization, err := MaterializeTabularValidation(
		modelPath,
		dataPath,
		validationPath,
	)
	if err != nil {
		t.Fatalf("materialize indexed raw data: %v", err)
	}
	if materialization.SourceFeatureSpace !=
		string(TabularDataSpaceRaw) {
		t.Fatalf(
			"indexed raw data resolved incorrectly: %+v",
			materialization,
		)
	}
	records := readCSVFixture(t, validationPath)
	if records[1][10] != "-1" || records[1][11] != "1" {
		t.Fatalf(
			"unexpected indexed standardization: %v",
			records[1],
		)
	}

	ambiguousPath := filepath.Join(root, "ambiguous.csv")
	if err := os.WriteFile(
		ambiguousPath,
		[]byte(
			"row_id,label,x_0,x_1,raw_b,raw_d\n"+
				"0,0,-1,1,8,25\n",
		),
		0o600,
	); err != nil {
		t.Fatalf("write ambiguous data: %v", err)
	}
	_, err = MaterializeTabularValidation(
		modelPath,
		ambiguousPath,
		validationPath,
	)
	if err == nil || !strings.Contains(
		err.Error(),
		"feature space is ambiguous",
	) {
		t.Fatalf("expected ambiguous-space rejection, got %v", err)
	}
}

func TestMaterializeRawFeaturesRejectsMissingPreprocessingMetadata(
	t *testing.T,
) {
	modelPath, _ := writeLinearFixture(t, false)
	root := t.TempDir()
	dataPath := filepath.Join(root, "raw.csv")
	if err := os.WriteFile(
		dataPath,
		[]byte("row_id,label,x_0\n0,0,1\n"),
		0o600,
	); err != nil {
		t.Fatalf("write raw fixture: %v", err)
	}
	_, err := MaterializeTabularValidationWithOptions(
		modelPath,
		dataPath,
		filepath.Join(root, "validation.csv"),
		TabularMaterializationOptions{
			DataSpace: TabularDataSpaceRaw,
		},
	)
	if err == nil || !strings.Contains(
		err.Error(),
		"selected feature indices",
	) {
		t.Fatalf("expected missing preprocessing rejection, got %v", err)
	}
}

func TestMaterializeRejectsUnknownDataSpaceBeforeArtifactReads(
	t *testing.T,
) {
	_, err := MaterializeTabularValidationWithOptions(
		"missing-model.json",
		"missing-data.csv",
		"output.csv",
		TabularMaterializationOptions{
			DataSpace: TabularDataSpace("standardized-ish"),
		},
	)
	if err == nil || !strings.Contains(
		err.Error(),
		"expected auto, model, or raw",
	) {
		t.Fatalf("expected data-space validation error, got %v", err)
	}
}

func TestCommittedTabularSuiteRawMaterializationEquivalence(
	t *testing.T,
) {
	_, sourceFile, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("resolve test source path")
	}
	repositoryRoot := filepath.Clean(
		filepath.Join(filepath.Dir(sourceFile), "..", ".."),
	)
	modelPaths, err := filepath.Glob(
		filepath.Join(
			repositoryRoot,
			"datasets",
			"tabular_suite",
			"*",
			"*",
			"model.json",
		),
	)
	if err != nil {
		t.Fatalf("glob committed tabular models: %v", err)
	}
	if len(modelPaths) != 15 {
		t.Fatalf(
			"expected 15 committed tabular models, got %d",
			len(modelPaths),
		)
	}

	for _, modelPath := range modelPaths {
		modelPath := modelPath
		t.Run(
			filepath.Base(filepath.Dir(filepath.Dir(modelPath)))+
				"/"+filepath.Base(filepath.Dir(modelPath)),
			func(t *testing.T) {
				verifyCommittedRawMaterialization(
					t,
					modelPath,
				)
			},
		)
	}
}

func verifyCommittedRawMaterialization(
	t *testing.T,
	modelPath string,
) {
	t.Helper()
	modelBytes, err := os.ReadFile(modelPath)
	if err != nil {
		t.Fatalf("read committed model: %v", err)
	}
	model := tabularModelArtifact{}
	if err := json.Unmarshal(modelBytes, &model); err != nil {
		t.Fatalf("parse committed model: %v", err)
	}
	if err := validateRawPreprocessingMetadata(model); err != nil {
		t.Fatalf("validate committed preprocessing: %v", err)
	}

	testPath := filepath.Join(filepath.Dir(modelPath), "test.csv")
	testRecords := readCSVFixture(t, testPath)
	testColumns := csvColumnMap(t, testRecords[0])
	rawRecords := make([][]string, 0, len(testRecords))
	rawHeader := []string{"row_id", "label"}
	rawHeader = append(rawHeader, model.SelectedFeatureNames...)
	rawRecords = append(rawRecords, rawHeader)
	for rowIndex, record := range testRecords[1:] {
		rawRecord := []string{
			record[testColumns["row_id"]],
			record[testColumns["label"]],
		}
		for featureIndex := 0; featureIndex < model.InputDim; featureIndex++ {
			name := fmt.Sprintf("x_%d", featureIndex)
			standardized, err := strconv.ParseFloat(
				record[testColumns[name]],
				64,
			)
			if err != nil {
				t.Fatalf(
					"parse committed row %d %s: %v",
					rowIndex+2,
					name,
					err,
				)
			}
			raw := standardized*
				model.Standardization.Std[featureIndex] +
				model.Standardization.Mean[featureIndex]
			rawRecord = append(
				rawRecord,
				formatMaterializedFloat(raw),
			)
		}
		rawRecords = append(rawRecords, rawRecord)
	}

	root := t.TempDir()
	rawPath := filepath.Join(root, "raw.csv")
	validationPath := filepath.Join(root, "validation.csv")
	writeCSVFixture(t, rawPath, rawRecords)
	materialization, err :=
		MaterializeTabularValidationWithOptions(
			modelPath,
			rawPath,
			validationPath,
			TabularMaterializationOptions{
				DataSpace: TabularDataSpaceRaw,
			},
		)
	if err != nil {
		t.Fatalf("materialize committed raw data: %v", err)
	}
	if materialization.Rows != len(testRecords)-1 ||
		materialization.SourceFeatureSpace !=
			string(TabularDataSpaceRaw) {
		t.Fatalf(
			"unexpected committed materialization: %+v",
			materialization,
		)
	}

	preparedRecords := readCSVFixture(t, validationPath)
	preparedColumns := csvColumnMap(t, preparedRecords[0])
	if len(preparedRecords) != len(testRecords) {
		t.Fatalf(
			"prepared row count %d != committed %d",
			len(preparedRecords)-1,
			len(testRecords)-1,
		)
	}
	for rowIndex := 1; rowIndex < len(testRecords); rowIndex++ {
		expected := testRecords[rowIndex]
		actual := preparedRecords[rowIndex]
		if actual[preparedColumns["row_id"]] !=
			expected[testColumns["row_id"]] ||
			actual[preparedColumns["label"]] !=
				expected[testColumns["label"]] ||
			actual[preparedColumns["plaintext_decision"]] !=
				strings.ToLower(
					expected[testColumns["plaintext_decision"]],
				) {
			t.Fatalf(
				"row %d identity/decision mismatch",
				rowIndex+1,
			)
		}
		compareCSVFloat(
			t,
			rowIndex+1,
			"polynomial_score",
			actual[preparedColumns["polynomial_score"]],
			expected[testColumns["polynomial_score"]],
			2e-12,
		)
		for featureIndex := 0; featureIndex < model.InputDim; featureIndex++ {
			name := fmt.Sprintf("x_%d", featureIndex)
			compareCSVFloat(
				t,
				rowIndex+1,
				name,
				actual[preparedColumns[name]],
				expected[testColumns[name]],
				2e-12,
			)
		}
	}

	options := DefaultTabularContractOptions()
	options.ModelPath = modelPath
	options.ValidationPath = validationPath
	options.SourceDataPath = rawPath
	options.SplitID = "committed_raw_equivalence"
	contract, err := BuildTabularWorkloadContract(options)
	if err != nil {
		t.Fatalf("build committed raw contract: %v", err)
	}
	if contract.InputMaterialization == nil ||
		!contract.InputMaterialization.SourceReplayVerified {
		t.Fatalf(
			"committed raw source replay not verified: %+v",
			contract.InputMaterialization,
		)
	}
}

func writeRawLinearModelFixture(t *testing.T) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "model.json")
	model := []byte(`{
  "dataset_id": "toy_raw",
  "dataset_name": "Toy Raw",
  "model_id": "linear_poly3",
  "model_type": "linear_poly3",
  "input_dim": 2,
  "selected_feature_indices": [1, 3],
  "selected_feature_names": ["raw_b", "raw_d"],
  "standardization": {
    "mean": [10, 20],
    "std": [2, 5]
  },
  "scaled_model_for_ckks": {
    "weights": [0.5, -0.25],
    "bias": 0
  },
  "polynomial_score": {
    "formula": "0.5 + 0.197*z - 0.004*z^3",
    "decision_threshold": 0.5
  }
}`)
	if err := os.WriteFile(path, model, 0o600); err != nil {
		t.Fatalf("write raw model fixture: %v", err)
	}
	return path
}

func readCSVFixture(t *testing.T, path string) [][]string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read CSV fixture: %v", err)
	}
	records, err := csv.NewReader(bytes.NewReader(data)).ReadAll()
	if err != nil {
		t.Fatalf("parse CSV fixture: %v", err)
	}
	return records
}

func writeCSVFixture(
	t *testing.T,
	path string,
	records [][]string,
) {
	t.Helper()
	var output bytes.Buffer
	writer := csv.NewWriter(&output)
	if err := writer.WriteAll(records); err != nil {
		t.Fatalf("encode CSV fixture: %v", err)
	}
	if err := os.WriteFile(path, output.Bytes(), 0o600); err != nil {
		t.Fatalf("write CSV fixture: %v", err)
	}
}

func csvColumnMap(
	t *testing.T,
	header []string,
) map[string]int {
	t.Helper()
	columns := make(map[string]int, len(header))
	for index, name := range header {
		if _, exists := columns[name]; exists {
			t.Fatalf("duplicate CSV fixture column %q", name)
		}
		columns[name] = index
	}
	return columns
}

func compareCSVFloat(
	t *testing.T,
	row int,
	field string,
	actualRaw string,
	expectedRaw string,
	tolerance float64,
) {
	t.Helper()
	actual, err := strconv.ParseFloat(actualRaw, 64)
	if err != nil {
		t.Fatalf("parse row %d actual %s: %v", row, field, err)
	}
	expected, err := strconv.ParseFloat(expectedRaw, 64)
	if err != nil {
		t.Fatalf("parse row %d expected %s: %v", row, field, err)
	}
	if math.Abs(actual-expected) > tolerance {
		t.Fatalf(
			"row %d %s mismatch: got %.17g expected %.17g",
			row,
			field,
			actual,
			expected,
		)
	}
}
