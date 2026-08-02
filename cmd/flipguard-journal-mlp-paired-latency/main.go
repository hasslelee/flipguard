package main

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/hasslelee/flipguard/internal/ckksbackend"
	"github.com/hasslelee/flipguard/internal/ckksplanner"
)

const protocolSchema = "flipguard_journal_mlp_paired_latency_protocol_v1"

type binding struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
}

type protocolArm struct {
	ID            string                           `json:"id"`
	Role          string                           `json:"role"`
	Candidate     ckksplanner.SynthesizedCandidate `json:"candidate"`
	ProfileSource string                           `json:"profile_source"`
	ProfileName   string                           `json:"profile_name,omitempty"`
	Source        binding                          `json:"source"`
}

type subsetRow struct {
	Rank        int    `json:"rank"`
	RowID       int    `json:"row_id"`
	SampleID    string `json:"sample_id"`
	SourceIndex int    `json:"source_index"`
	Label       int    `json:"label"`
}

type executionProtocol struct {
	SchemaVersion                 string        `json:"schema_version"`
	ProtocolID                    string        `json:"protocol_id"`
	ExecutionSourceCommit         string        `json:"execution_source_commit"`
	ExecutionCriticalSourceDigest string        `json:"execution_critical_source_digest"`
	FrozenBinarySHA256            string        `json:"frozen_binary_sha256"`
	Model                         binding       `json:"model"`
	LockedAudit                   binding       `json:"locked_audit"`
	SecurityReconciliation        binding       `json:"security_reconciliation"`
	SelectedRows                  []subsetRow   `json:"selected_rows"`
	FreshKeysets                  int           `json:"fresh_keysets"`
	WarmupRuns                    int           `json:"warmup_runs"`
	MeasurementRuns               int           `json:"measurement_runs"`
	MarginFloor                   float64       `json:"margin_floor"`
	MarginUtilizationCap          float64       `json:"margin_utilization_cap"`
	ConcurrentCKKSProcesses       int           `json:"concurrent_ckks_processes"`
	OutlierRemoval                bool          `json:"outlier_removal"`
	Arms                          []protocolArm `json:"arms"`
}

type runManifest struct {
	SchemaVersion                 string `json:"schema_version"`
	ProtocolID                    string `json:"protocol_id"`
	ProtocolSHA256                string `json:"protocol_sha256"`
	ExecutionSourceCommit         string `json:"execution_source_commit"`
	CurrentSourceCommit           string `json:"current_source_commit"`
	ExecutionCriticalSourceDigest string `json:"execution_critical_source_digest"`
	BinarySHA256                  string `json:"binary_sha256"`
	Keyset                        int    `json:"keyset"`
	Attempt                       int    `json:"attempt"`
	StartedAt                     string `json:"started_at"`
	PID                           int    `json:"pid"`
	ParentPID                     int    `json:"parent_pid"`
	GoVersion                     string `json:"go_version"`
	GOOS                          string `json:"goos"`
	GOARCH                        string `json:"goarch"`
	LogicalCPUs                   int    `json:"logical_cpus"`
	NoRetuning                    bool   `json:"no_retuning"`
	ProcessRestartPolicy          string `json:"process_restart_policy"`
}

func main() {
	if err := run(os.Args[1:]); errors.Is(err, flag.ErrHelp) {
		return
	} else if err != nil {
		fmt.Fprintf(os.Stderr, "flipguard-journal-mlp-paired-latency: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string) error {
	flags := flag.NewFlagSet("flipguard-journal-mlp-paired-latency", flag.ContinueOnError)
	protocolPath := flags.String("protocol", "", "frozen execution protocol JSON")
	outputRoot := flags.String("output", "", "new append-only keyset attempt directory")
	keyset := flags.Int("keyset", 0, "one-based fresh-keyset process block")
	attempt := flags.Int("attempt", 1, "one-based preserved process attempt")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if *protocolPath == "" || *outputRoot == "" || *keyset <= 0 || *attempt <= 0 {
		return fmt.Errorf("--protocol, --output, positive --keyset, and positive --attempt are required")
	}
	if flags.NArg() != 0 {
		return fmt.Errorf("unexpected positional arguments: %v", flags.Args())
	}
	if clean, err := gitClean(); err != nil || !clean {
		return fmt.Errorf("encrypted measurement requires a clean tree: clean=%t error=%v", clean, err)
	}
	protocolBytes, err := os.ReadFile(*protocolPath)
	if err != nil {
		return err
	}
	var protocol executionProtocol
	decoder := json.NewDecoder(bytes.NewReader(protocolBytes))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&protocol); err != nil {
		return fmt.Errorf("parse protocol: %w", err)
	}
	if err := validateProtocol(protocol, *keyset); err != nil {
		return err
	}
	self, err := os.Executable()
	if err != nil {
		return err
	}
	selfDigest, err := digestFile(self)
	if err != nil || selfDigest != protocol.FrozenBinarySHA256 {
		return fmt.Errorf("binary digest mismatch: got %s expected %s error=%v", selfDigest, protocol.FrozenBinarySHA256, err)
	}
	for _, item := range append([]binding{protocol.Model, protocol.LockedAudit, protocol.SecurityReconciliation}, armBindings(protocol.Arms)...) {
		actual, err := digestFile(item.Path)
		if err != nil || actual != item.SHA256 {
			return fmt.Errorf("input binding mismatch for %s: got %s expected %s error=%v", item.Path, actual, item.SHA256, err)
		}
	}
	if _, err := os.Stat(*outputRoot); !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("refusing to overwrite output root %s", *outputRoot)
	}
	if err := os.MkdirAll(*outputRoot, 0o755); err != nil {
		return err
	}
	head, err := gitHead()
	if err != nil {
		return err
	}
	manifest := runManifest{
		SchemaVersion: "flipguard_journal_mlp_paired_latency_run_manifest_v1",
		ProtocolID:    protocol.ProtocolID, ProtocolSHA256: digestBytes(protocolBytes),
		ExecutionSourceCommit: protocol.ExecutionSourceCommit, CurrentSourceCommit: head,
		ExecutionCriticalSourceDigest: protocol.ExecutionCriticalSourceDigest,
		BinarySHA256:                  selfDigest, Keyset: *keyset, Attempt: *attempt,
		StartedAt: time.Now().UTC().Format(time.RFC3339), PID: os.Getpid(), ParentPID: os.Getppid(),
		GoVersion: runtime.Version(), GOOS: runtime.GOOS, GOARCH: runtime.GOARCH,
		LogicalCPUs: runtime.NumCPU(), NoRetuning: true,
		ProcessRestartPolicy: "one_new_process_per_fresh_keyset_preserve_failed_attempts",
	}
	if err := writeExclusiveJSON(filepath.Join(*outputRoot, "run_manifest.json"), manifest); err != nil {
		return err
	}

	arms, err := runtimeArms(protocol.Arms)
	if err != nil {
		return err
	}
	rowIDs := make([]int, len(protocol.SelectedRows))
	for index, row := range protocol.SelectedRows {
		rowIDs[index] = row.RowID
	}
	ledgerPath := filepath.Join(*outputRoot, "records.jsonl")
	ledger, err := os.OpenFile(ledgerPath, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o644)
	if err != nil {
		return err
	}
	buffered := bufio.NewWriter(ledger)
	encoder := json.NewEncoder(buffered)
	onRecord := func(record ckksbackend.JournalMLPPairedLatencyRecord) error {
		if err := encoder.Encode(record); err != nil {
			return err
		}
		if err := buffered.Flush(); err != nil {
			return err
		}
		return ledger.Sync()
	}
	result, runErr := ckksbackend.RunJournalMLPPairedLatencyKeyset(
		ckksbackend.JournalMLPPairedLatencyConfig{
			ModelPath: protocol.Model.Path, AuditPath: protocol.LockedAudit.Path,
			SelectedRowIDs: rowIDs, Keyset: *keyset,
			WarmupRuns: protocol.WarmupRuns, MeasurementRuns: protocol.MeasurementRuns,
			MarginFloor: protocol.MarginFloor, UtilizationCap: protocol.MarginUtilizationCap,
			Arms: arms,
		},
		onRecord,
	)
	closeErr := ledger.Close()
	if runErr != nil {
		return runErr
	}
	if closeErr != nil {
		return closeErr
	}
	if err := writeExclusiveJSON(filepath.Join(*outputRoot, "result.json"), result); err != nil {
		return err
	}
	completion := map[string]any{
		"schema_version": "flipguard_journal_mlp_paired_latency_completion_v1",
		"keyset":         *keyset, "attempt": *attempt, "records": len(result.Records),
		"ledger_sha256": mustDigest(ledgerPath), "result_sha256": mustDigest(filepath.Join(*outputRoot, "result.json")),
		"completed_at": time.Now().UTC().Format(time.RFC3339),
	}
	if err := writeExclusiveJSON(filepath.Join(*outputRoot, "completed.json"), completion); err != nil {
		return err
	}
	fmt.Printf("journal_mlp_paired_latency keyset=%d records=%d output=%s\n", *keyset, len(result.Records), *outputRoot)
	return nil
}

func validateProtocol(protocol executionProtocol, keyset int) error {
	if protocol.SchemaVersion != protocolSchema || protocol.ProtocolID == "" || len(protocol.ExecutionSourceCommit) != 40 {
		return fmt.Errorf("invalid protocol identity")
	}
	if keyset > protocol.FreshKeysets || protocol.FreshKeysets != 3 || protocol.WarmupRuns != 1 || protocol.MeasurementRuns != 6 {
		return fmt.Errorf("protocol repetition policy changed")
	}
	if len(protocol.SelectedRows) != 100 || len(protocol.Arms) != 3 || protocol.ConcurrentCKKSProcesses != 0 || protocol.OutlierRemoval {
		return fmt.Errorf("protocol population, arm, concurrency, or outlier policy changed")
	}
	counts := make([]int, 10)
	seenRows := make(map[int]bool)
	for _, row := range protocol.SelectedRows {
		if row.Label < 0 || row.Label >= 10 || seenRows[row.RowID] {
			return fmt.Errorf("invalid selected row identity")
		}
		seenRows[row.RowID] = true
		counts[row.Label]++
	}
	for label, count := range counts {
		if count != 10 {
			return fmt.Errorf("selected class %d count %d; expected 10", label, count)
		}
	}
	return nil
}

func runtimeArms(protocolArms []protocolArm) ([]ckksbackend.JournalMLPPairedLatencyArm, error) {
	output := make([]ckksbackend.JournalMLPPairedLatencyArm, 0, len(protocolArms))
	for _, arm := range protocolArms {
		if arm.Candidate.Security.FinalAdmission != ckksplanner.SecurityAdmissionPass {
			return nil, fmt.Errorf("arm %s is not Security-V2 admitted", arm.ID)
		}
		var profile ckksbackend.CKKSProfile
		var err error
		switch arm.ProfileSource {
		case "synthesized_literal":
			profile, err = arm.Candidate.Profile()
		case "builtin_catalog_concrete_literal":
			profile, err = ckksbackend.FindCKKSProfile(arm.ProfileName)
		default:
			return nil, fmt.Errorf("arm %s has unknown profile source %q", arm.ID, arm.ProfileSource)
		}
		if err != nil {
			return nil, fmt.Errorf("arm %s profile: %w", arm.ID, err)
		}
		output = append(output, ckksbackend.JournalMLPPairedLatencyArm{
			ID: arm.ID, Role: arm.Role, CandidateID: arm.Candidate.ID, Profile: profile,
		})
	}
	return output, nil
}

func armBindings(arms []protocolArm) []binding {
	result := make([]binding, 0, len(arms))
	for _, arm := range arms {
		result = append(result, arm.Source)
	}
	return result
}

func writeExclusiveJSON(path string, value any) error {
	if _, err := os.Stat(path); err == nil {
		return fmt.Errorf("refusing to overwrite %s", path)
	} else if !errors.Is(err, os.ErrNotExist) {
		return err
	}
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}

func digestFile(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hasher := sha256.New()
	if _, err := io.Copy(hasher, file); err != nil {
		return "", err
	}
	return "sha256:" + hex.EncodeToString(hasher.Sum(nil)), nil
}

func digestBytes(value []byte) string {
	sum := sha256.Sum256(value)
	return "sha256:" + hex.EncodeToString(sum[:])
}

func mustDigest(path string) string {
	value, err := digestFile(path)
	if err != nil {
		panic(err)
	}
	return value
}

func gitHead() (string, error) {
	value, err := exec.Command("git", "rev-parse", "HEAD").Output()
	return strings.TrimSpace(string(value)), err
}

func gitClean() (bool, error) {
	value, err := exec.Command("git", "status", "--porcelain").Output()
	return len(bytes.TrimSpace(value)) == 0, err
}
