package main

import (
	"bytes"
	"strings"
	"testing"
)

func TestRunRequiresUserInputs(t *testing.T) {
	output := &bytes.Buffer{}
	err := run(nil, output)
	if err == nil || !strings.Contains(err.Error(), "--model is required") {
		t.Fatalf("expected required model error, got %v", err)
	}
}
