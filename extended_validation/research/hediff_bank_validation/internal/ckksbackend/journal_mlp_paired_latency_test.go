package ckksbackend

import (
	"testing"

	"github.com/hasslelee/flipguard/internal/journalmnist"
)

func TestSelectJournalMNISTRowsPreservesDeclaredOrder(t *testing.T) {
	rows := []journalmnist.PartitionRow{
		{RowID: 1, SampleID: "one"},
		{RowID: 3, SampleID: "three"},
		{RowID: 8, SampleID: "eight"},
	}
	selected, err := selectJournalMNISTRows(rows, []int{8, 1})
	if err != nil {
		t.Fatal(err)
	}
	if len(selected) != 2 || selected[0].SampleID != "eight" || selected[1].SampleID != "one" {
		t.Fatalf("unexpected selected order: %+v", selected)
	}
}

func TestSelectJournalMNISTRowsRejectsMissingAndDuplicateIDs(t *testing.T) {
	rows := []journalmnist.PartitionRow{{RowID: 1, SampleID: "one"}}
	if _, err := selectJournalMNISTRows(rows, []int{2}); err == nil {
		t.Fatal("expected missing row rejection")
	}
	if _, err := selectJournalMNISTRows(rows, []int{1, 1}); err == nil {
		t.Fatal("expected duplicate row rejection")
	}
}
