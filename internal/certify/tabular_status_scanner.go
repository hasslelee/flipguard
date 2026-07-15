package certify

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

// TabularStatusScanConfig controls reconstruction of repeated tabular
// certification evidence from run_status.csv.
type TabularStatusScanConfig struct {
	StatusPath   string
	ArtifactRoot string
	ModelRoot    string

	MarginFloor  float64
	SafetyFactor float64

	ExpectedRepeats int
}

// TabularScannedCandidate describes one profile-path candidate reconstructed
// from the latest status row of every requested repeat.
type TabularScannedCandidate struct {
	Candidate CandidateDescriptor

	RequestedRuns  int
	SuccessfulRuns int
	FailedRuns     int

	RunTags []string

	// Aggregation is nil when every requested execution failed.
	Aggregation *TabularArtifactAggregation
}

// TabularWorkloadScan contains all reconstructed candidates and the final
// certify-or-reject result for one dataset-model workload.
type TabularWorkloadScan struct {
	Scope    ClaimScope
	Coverage ValidationCoverage

	Candidates []TabularScannedCandidate
	Evidences  []CandidateEvidence

	Summary CertificationSummary
}

// TabularStatusScan summarizes the complete run-status reconstruction.
type TabularStatusScan struct {
	StatusPath string

	RawRows       int
	LatestRows    int
	DuplicateTags int

	Workloads []TabularWorkloadScan
}

type tabularRunStatusRow struct {
	Timestamp string

	DatasetID string
	ModelID   string
	Profile   string
	Path      string

	Repeat int
	Tag    string

	Status   string
	ExitCode int

	SummaryPath string
	LogPath     string
}

type tabularWorkloadKey struct {
	DatasetID string
	ModelID   string
}

type tabularCandidateKey struct {
	Profile string
	Path    string
}

// ScanTabularRunStatus reconstructs candidate evidence from run_status.csv.
//
// The last row for each tag is authoritative. A candidate is marked FAILED
// whenever one or more requested runs failed. A workload scan is aborted when
// successful candidates do not share the exact same validation scope and
// coverage.
func ScanTabularRunStatus(
	config TabularStatusScanConfig,
) (TabularStatusScan, error) {
	if strings.TrimSpace(config.StatusPath) == "" {
		return TabularStatusScan{}, fmt.Errorf(
			"tabular status path is empty",
		)
	}
	if !isFinite(config.MarginFloor) ||
		config.MarginFloor < 0 {
		return TabularStatusScan{}, fmt.Errorf(
			"tabular margin floor must be finite and non-negative",
		)
	}
	if config.ExpectedRepeats <= 0 {
		return TabularStatusScan{}, fmt.Errorf(
			"expected repeats must be positive",
		)
	}

	policy := CertificationPolicy{
		SafetyFactor:              config.SafetyFactor,
		RequireObservedValidation: true,
		RequireAnalyticalBound:    false,
	}
	if err := policy.Validate(); err != nil {
		return TabularStatusScan{}, fmt.Errorf(
			"invalid tabular certification policy: %w",
			err,
		)
	}

	artifactRoot := strings.TrimSpace(
		config.ArtifactRoot,
	)
	if artifactRoot == "" {
		artifactRoot = "."
	}

	modelRoot := strings.TrimSpace(
		config.ModelRoot,
	)
	if modelRoot == "" {
		modelRoot = "datasets/tabular_suite"
	}
	modelRoot = resolveTabularStatusPath(
		artifactRoot,
		modelRoot,
	)

	statusPath := resolveTabularStatusPath(
		artifactRoot,
		config.StatusPath,
	)

	latestRows, rawRows, duplicateTags, err :=
		loadLatestTabularRunStatusRows(
			statusPath,
			artifactRoot,
		)
	if err != nil {
		return TabularStatusScan{}, err
	}

	grouped := make(
		map[tabularWorkloadKey]map[tabularCandidateKey]map[int]tabularRunStatusRow,
	)

	for _, row := range latestRows {
		if row.Repeat < 1 ||
			row.Repeat > config.ExpectedRepeats {
			return TabularStatusScan{}, fmt.Errorf(
				"tag %s has repeat %d outside expected range 1..%d",
				row.Tag,
				row.Repeat,
				config.ExpectedRepeats,
			)
		}

		workloadKey := tabularWorkloadKey{
			DatasetID: row.DatasetID,
			ModelID:   row.ModelID,
		}
		candidateKey := tabularCandidateKey{
			Profile: row.Profile,
			Path:    row.Path,
		}

		if grouped[workloadKey] == nil {
			grouped[workloadKey] = make(
				map[tabularCandidateKey]map[int]tabularRunStatusRow,
			)
		}
		if grouped[workloadKey][candidateKey] == nil {
			grouped[workloadKey][candidateKey] = make(
				map[int]tabularRunStatusRow,
			)
		}

		if existing, exists :=
			grouped[workloadKey][candidateKey][row.Repeat]; exists {
			return TabularStatusScan{}, fmt.Errorf(
				"candidate %s__%s in workload %s__%s has duplicate repeat %d through tags %s and %s",
				candidateKey.Profile,
				candidateKey.Path,
				workloadKey.DatasetID,
				workloadKey.ModelID,
				row.Repeat,
				existing.Tag,
				row.Tag,
			)
		}

		grouped[workloadKey][candidateKey][row.Repeat] =
			row
	}

	workloadKeys := make(
		[]tabularWorkloadKey,
		0,
		len(grouped),
	)
	for key := range grouped {
		workloadKeys = append(
			workloadKeys,
			key,
		)
	}

	sort.Slice(
		workloadKeys,
		func(i int, j int) bool {
			if workloadKeys[i].DatasetID !=
				workloadKeys[j].DatasetID {
				return workloadKeys[i].DatasetID <
					workloadKeys[j].DatasetID
			}

			return workloadKeys[i].ModelID <
				workloadKeys[j].ModelID
		},
	)

	scan := TabularStatusScan{
		StatusPath: statusPath,

		RawRows:       rawRows,
		LatestRows:    len(latestRows),
		DuplicateTags: duplicateTags,

		Workloads: make(
			[]TabularWorkloadScan,
			0,
			len(workloadKeys),
		),
	}

	for _, workloadKey := range workloadKeys {
		workload, err :=
			buildTabularWorkloadScan(
				workloadKey,
				grouped[workloadKey],
				modelRoot,
				config,
				policy,
			)
		if err != nil {
			return TabularStatusScan{}, err
		}

		scan.Workloads = append(
			scan.Workloads,
			workload,
		)
	}

	if len(scan.Workloads) == 0 {
		return TabularStatusScan{}, fmt.Errorf(
			"run status contains no workload",
		)
	}

	return scan, nil
}

func loadLatestTabularRunStatusRows(
	statusPath string,
	artifactRoot string,
) ([]tabularRunStatusRow, int, int, error) {
	rows, err := readTabularArtifactCSV(statusPath)
	if err != nil {
		return nil, 0, 0, fmt.Errorf(
			"read tabular run status: %w",
			err,
		)
	}
	if len(rows) == 0 {
		return nil, 0, 0, fmt.Errorf(
			"tabular run status contains no data row",
		)
	}

	latestByTag := make(
		map[string]map[string]string,
	)
	identityByTag := make(map[string]string)
	duplicateTags := make(map[string]struct{})

	for rowIndex, row := range rows {
		tag, err := requiredTabularArtifactValue(
			row,
			"tag",
			statusPath,
		)
		if err != nil {
			return nil, 0, 0, fmt.Errorf(
				"status row %d: %w",
				rowIndex,
				err,
			)
		}

		identity, err := rawTabularStatusIdentity(
			row,
			statusPath,
		)
		if err != nil {
			return nil, 0, 0, fmt.Errorf(
				"status row %d: %w",
				rowIndex,
				err,
			)
		}

		if previousIdentity, exists :=
			identityByTag[tag]; exists {
			duplicateTags[tag] = struct{}{}

			if previousIdentity != identity {
				return nil, 0, 0, fmt.Errorf(
					"duplicate tag %s changed dataset, model, profile, path, or repeat identity",
					tag,
				)
			}
		}

		identityByTag[tag] = identity
		latestByTag[tag] = row
	}

	latestRows := make(
		[]tabularRunStatusRow,
		0,
		len(latestByTag),
	)

	for _, rawRow := range latestByTag {
		row, err := parseTabularRunStatusRow(
			rawRow,
			statusPath,
			artifactRoot,
		)
		if err != nil {
			return nil, 0, 0, err
		}

		latestRows = append(
			latestRows,
			row,
		)
	}

	sort.Slice(
		latestRows,
		func(i int, j int) bool {
			left := latestRows[i]
			right := latestRows[j]

			switch {
			case left.DatasetID != right.DatasetID:
				return left.DatasetID < right.DatasetID
			case left.ModelID != right.ModelID:
				return left.ModelID < right.ModelID
			case left.Profile != right.Profile:
				return left.Profile < right.Profile
			case left.Path != right.Path:
				return left.Path < right.Path
			case left.Repeat != right.Repeat:
				return left.Repeat < right.Repeat
			default:
				return left.Tag < right.Tag
			}
		},
	)

	return latestRows,
		len(rows),
		len(duplicateTags),
		nil
}

func rawTabularStatusIdentity(
	row map[string]string,
	statusPath string,
) (string, error) {
	keys := []string{
		"dataset",
		"model",
		"profile",
		"path",
		"repeat",
	}

	values := make([]string, 0, len(keys))

	for _, key := range keys {
		value, err := requiredTabularArtifactValue(
			row,
			key,
			statusPath,
		)
		if err != nil {
			return "", err
		}

		values = append(values, value)
	}

	return strings.Join(values, "\x00"), nil
}

func parseTabularRunStatusRow(
	row map[string]string,
	statusPath string,
	artifactRoot string,
) (tabularRunStatusRow, error) {
	required := func(key string) (string, error) {
		return requiredTabularArtifactValue(
			row,
			key,
			statusPath,
		)
	}

	timestamp, err := required("timestamp")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	datasetID, err := required("dataset")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	modelID, err := required("model")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	profile, err := required("profile")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	path, err := required("path")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	repeatText, err := required("repeat")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	tag, err := required("tag")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	status, err := required("status")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	exitCodeText, err := required("exit_code")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	summaryPath, err := required("summary_path")
	if err != nil {
		return tabularRunStatusRow{}, err
	}
	logPath, err := required("log_path")
	if err != nil {
		return tabularRunStatusRow{}, err
	}

	repeat, err := strconv.Atoi(repeatText)
	if err != nil {
		return tabularRunStatusRow{}, fmt.Errorf(
			"tag %s has invalid repeat %q: %w",
			tag,
			repeatText,
			err,
		)
	}

	exitCode, err := strconv.Atoi(exitCodeText)
	if err != nil {
		return tabularRunStatusRow{}, fmt.Errorf(
			"tag %s has invalid exit code %q: %w",
			tag,
			exitCodeText,
			err,
		)
	}

	switch status {
	case "ok":
		if exitCode != 0 {
			return tabularRunStatusRow{}, fmt.Errorf(
				"tag %s has status ok with nonzero exit code %d",
				tag,
				exitCode,
			)
		}

	case "failed":
		// A failed row may have a zero exit code when the process
		// completed without creating its required summary artifact.

	default:
		return tabularRunStatusRow{}, fmt.Errorf(
			"tag %s has unsupported status %q",
			tag,
			status,
		)
	}

	return tabularRunStatusRow{
		Timestamp: timestamp,

		DatasetID: datasetID,
		ModelID:   modelID,
		Profile:   profile,
		Path:      path,

		Repeat: repeat,
		Tag:    tag,

		Status:   status,
		ExitCode: exitCode,

		SummaryPath: resolveTabularStatusPath(
			artifactRoot,
			summaryPath,
		),
		LogPath: resolveTabularStatusPath(
			artifactRoot,
			logPath,
		),
	}, nil
}

func buildTabularWorkloadScan(
	workloadKey tabularWorkloadKey,
	grouped map[tabularCandidateKey]map[int]tabularRunStatusRow,
	modelRoot string,
	config TabularStatusScanConfig,
	policy CertificationPolicy,
) (TabularWorkloadScan, error) {
	candidateKeys := make(
		[]tabularCandidateKey,
		0,
		len(grouped),
	)
	for key := range grouped {
		candidateKeys = append(
			candidateKeys,
			key,
		)
	}

	sort.Slice(
		candidateKeys,
		func(i int, j int) bool {
			if candidateKeys[i].Profile !=
				candidateKeys[j].Profile {
				return candidateKeys[i].Profile <
					candidateKeys[j].Profile
			}

			return candidateKeys[i].Path <
				candidateKeys[j].Path
		},
	)

	workloadID :=
		workloadKey.DatasetID +
			"__" +
			workloadKey.ModelID

	modelScope, err := loadTabularCertificationModelScope(
		modelRoot,
		workloadKey,
		candidateKeys,
		grouped,
		config.ExpectedRepeats,
	)
	if err != nil {
		return TabularWorkloadScan{}, fmt.Errorf(
			"load workload %s model scope: %w",
			workloadID,
			err,
		)
	}

	workload := TabularWorkloadScan{
		Candidates: make(
			[]TabularScannedCandidate,
			0,
			len(candidateKeys),
		),
		Evidences: make(
			[]CandidateEvidence,
			0,
			len(candidateKeys),
		),
	}

	var scopeSet bool
	var referenceScope ClaimScope
	var referenceCoverage ValidationCoverage

	for _, candidateKey := range candidateKeys {
		repeatRows := grouped[candidateKey]

		for repeat := 1; repeat <= config.ExpectedRepeats; repeat++ {
			if _, exists := repeatRows[repeat]; !exists {
				return TabularWorkloadScan{}, fmt.Errorf(
					"candidate %s__%s in workload %s is missing repeat %d",
					candidateKey.Profile,
					candidateKey.Path,
					workloadID,
					repeat,
				)
			}
		}

		candidate := CandidateDescriptor{
			ID: candidateKey.Profile +
				"__" +
				candidateKey.Path,

			Path:   candidateKey.Path,
			Family: candidateKey.Profile,

			IsReference: candidateKey.Profile == "default" &&
				candidateKey.Path == "rescale_aware",
		}

		runs := make(
			[]TabularArtifactRun,
			0,
			config.ExpectedRepeats,
		)
		runTags := make(
			[]string,
			0,
			config.ExpectedRepeats,
		)
		failedRuns := 0

		for repeat := 1; repeat <= config.ExpectedRepeats; repeat++ {
			row := repeatRows[repeat]
			runTags = append(runTags, row.Tag)

			if row.Status == "failed" {
				failedRuns++
				continue
			}

			recordsPath := filepath.Join(
				filepath.Dir(row.SummaryPath),
				"records.csv",
			)

			if !regularFileExists(row.SummaryPath) {
				return TabularWorkloadScan{}, fmt.Errorf(
					"successful tag %s is missing summary artifact %s",
					row.Tag,
					row.SummaryPath,
				)
			}
			if !regularFileExists(recordsPath) {
				return TabularWorkloadScan{}, fmt.Errorf(
					"successful tag %s is missing records artifact %s",
					row.Tag,
					recordsPath,
				)
			}

			runs = append(runs, TabularArtifactRun{
				RecordsPath: recordsPath,
				SummaryPath: row.SummaryPath,
			})
		}

		scannedCandidate := TabularScannedCandidate{
			Candidate: candidate,

			RequestedRuns:  config.ExpectedRepeats,
			SuccessfulRuns: len(runs),
			FailedRuns:     failedRuns,

			RunTags: append(
				[]string(nil),
				runTags...,
			),
		}

		var evidence CandidateEvidence

		if len(runs) == 0 {
			evidence = CandidateEvidence{
				Candidate: candidate,

				SuccessRuns: 0,
				FailedRuns:  failedRuns,

				ObservedValidation: false,
			}
		} else {
			aggregation, err :=
				LoadAndAggregateTabularCandidate(
					TabularArtifactCandidateInput{
						Candidate: candidate,

						WorkloadID: workloadID,
						DatasetID:  workloadKey.DatasetID,
						ModelID:    workloadKey.ModelID,
						SplitID:    modelScope.SplitID,

						Threshold: modelScope.Threshold,

						Runs:       runs,
						FailedRuns: failedRuns,
					},
					config.MarginFloor,
					config.SafetyFactor,
				)
			if err != nil {
				return TabularWorkloadScan{}, fmt.Errorf(
					"scan workload %s candidate %s: %w",
					workloadID,
					candidate.ID,
					err,
				)
			}

			if !scopeSet {
				referenceScope = aggregation.Scope
				referenceCoverage =
					aggregation.Aggregation.Coverage
				scopeSet = true
			} else {
				if err := compareTabularClaimScopes(
					referenceScope,
					aggregation.Scope,
				); err != nil {
					return TabularWorkloadScan{}, fmt.Errorf(
						"workload %s validation scope mismatch for candidate %s: %w",
						workloadID,
						candidate.ID,
						err,
					)
				}

				if referenceCoverage !=
					aggregation.Aggregation.Coverage {
					return TabularWorkloadScan{}, fmt.Errorf(
						"workload %s validation coverage mismatch for candidate %s",
						workloadID,
						candidate.ID,
					)
				}
			}

			aggregationCopy := aggregation
			scannedCandidate.Aggregation =
				&aggregationCopy
			scannedCandidate.Candidate =
				aggregation.Aggregation.
					Evidence.Candidate

			evidence =
				aggregation.Aggregation.Evidence
		}

		workload.Candidates = append(
			workload.Candidates,
			scannedCandidate,
		)
		workload.Evidences = append(
			workload.Evidences,
			evidence,
		)
	}

	if !scopeSet {
		return TabularWorkloadScan{}, fmt.Errorf(
			"workload %s has no successful candidate from which validation scope can be reconstructed",
			workloadID,
		)
	}

	summary, err := CertifyAndSelectWithPolicy(
		workload.Evidences,
		referenceCoverage,
		policy,
	)
	if err != nil {
		return TabularWorkloadScan{}, fmt.Errorf(
			"certify workload %s: %w",
			workloadID,
			err,
		)
	}

	workload.Scope = referenceScope
	workload.Coverage = referenceCoverage
	workload.Summary = summary

	return workload, nil
}

func compareTabularClaimScopes(
	expected ClaimScope,
	actual ClaimScope,
) error {
	switch {
	case actual.WorkloadID != expected.WorkloadID:
		return fmt.Errorf(
			"workload ID=%q; expected %q",
			actual.WorkloadID,
			expected.WorkloadID,
		)

	case actual.DatasetID != expected.DatasetID:
		return fmt.Errorf(
			"dataset ID=%q; expected %q",
			actual.DatasetID,
			expected.DatasetID,
		)

	case actual.ModelID != expected.ModelID:
		return fmt.Errorf(
			"model ID=%q; expected %q",
			actual.ModelID,
			expected.ModelID,
		)

	case actual.SplitID != expected.SplitID:
		return fmt.Errorf(
			"split ID=%q; expected %q",
			actual.SplitID,
			expected.SplitID,
		)

	case actual.ValidationDigest !=
		expected.ValidationDigest:
		return fmt.Errorf(
			"validation digest=%q; expected %q",
			actual.ValidationDigest,
			expected.ValidationDigest,
		)

	case actual.Threshold != expected.Threshold:
		return fmt.Errorf(
			"threshold=%.12g; expected %.12g",
			actual.Threshold,
			expected.Threshold,
		)

	case actual.MarginFloor != expected.MarginFloor:
		return fmt.Errorf(
			"margin floor=%.12g; expected %.12g",
			actual.MarginFloor,
			expected.MarginFloor,
		)

	case actual.SafetyFactor != expected.SafetyFactor:
		return fmt.Errorf(
			"safety factor=%.12g; expected %.12g",
			actual.SafetyFactor,
			expected.SafetyFactor,
		)

	case actual.SampleCount != expected.SampleCount:
		return fmt.Errorf(
			"sample count=%d; expected %d",
			actual.SampleCount,
			expected.SampleCount,
		)
	}

	return nil
}

func resolveTabularStatusPath(
	artifactRoot string,
	path string,
) string {
	if filepath.IsAbs(path) {
		return filepath.Clean(path)
	}

	return filepath.Clean(
		filepath.Join(
			artifactRoot,
			path,
		),
	)
}

func regularFileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.Mode().IsRegular()
}
