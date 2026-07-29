package ckksbackend

import (
	"math"
	"reflect"
	"testing"
)

func TestBalancedArmOrdersForThreeArms(t *testing.T) {
	got := balancedArmOrders(3)
	want := [][]int{
		{0, 1, 2},
		{1, 2, 0},
		{2, 0, 1},
		{2, 1, 0},
		{0, 2, 1},
		{1, 0, 2},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("unexpected balanced orders: %v", got)
	}

	positionCounts := make([][]int, 3)
	for arm := range positionCounts {
		positionCounts[arm] = make([]int, 3)
	}
	for _, order := range got {
		for position, arm := range order {
			positionCounts[arm][position]++
		}
	}
	for arm, counts := range positionCounts {
		if !reflect.DeepEqual(counts, []int{2, 2, 2}) {
			t.Fatalf(
				"arm %d has unbalanced positions %v",
				arm,
				counts,
			)
		}
	}
}

func TestPairedArmOrderIndexCoversEveryOrderPerRow(t *testing.T) {
	const orderCount = 6
	for rowIndex := 0; rowIndex < 6; rowIndex++ {
		seen := make(map[int]bool)
		for runIndex := 0; runIndex < 6; runIndex++ {
			seen[pairedArmOrderIndex(
				runIndex,
				rowIndex,
				orderCount,
			)] = true
		}
		if len(seen) != orderCount {
			t.Fatalf(
				"row %d covered %d/%d orders: %v",
				rowIndex,
				len(seen),
				orderCount,
				seen,
			)
		}
	}
}

func TestSelectPairedLatencyRowsIsEvenlySpaced(t *testing.T) {
	rows := make([]tabularTestRow, 10)
	for index := range rows {
		rows[index].RowID = index
	}
	selected := selectPairedLatencyRows(rows, 4)
	got := []int{
		selected[0].RowID,
		selected[1].RowID,
		selected[2].RowID,
		selected[3].RowID,
	}
	if !reflect.DeepEqual(got, []int{0, 3, 6, 9}) {
		t.Fatalf("unexpected selected rows: %v", got)
	}
}

func TestSummarizePairedTabularPairs(t *testing.T) {
	arms := []PairedTabularLatencyArm{
		{ID: "direct"},
		{ID: "catalog"},
	}
	records := []PairedTabularLatencyRecord{
		{
			MeasurementRun: 1,
			RowID:          10,
			ArmID:          "direct",
			TotalMS:        2,
			EvalOnlyMS:     1,
		},
		{
			MeasurementRun: 1,
			RowID:          10,
			ArmID:          "catalog",
			TotalMS:        4,
			EvalOnlyMS:     2,
		},
		{
			MeasurementRun: 2,
			RowID:          10,
			ArmID:          "direct",
			TotalMS:        3,
			EvalOnlyMS:     1.5,
		},
		{
			MeasurementRun: 2,
			RowID:          10,
			ArmID:          "catalog",
			TotalMS:        6,
			EvalOnlyMS:     3,
		},
	}
	summaries, err := summarizePairedTabularPairs(arms, records)
	if err != nil {
		t.Fatalf("summarize pairs: %v", err)
	}
	if len(summaries) != 1 {
		t.Fatalf("expected one pair, got %d", len(summaries))
	}
	summary := summaries[0]
	if summary.NumeratorArmID != "catalog" ||
		summary.DenominatorArmID != "direct" ||
		summary.Pairs != 2 {
		t.Fatalf("unexpected pair identity: %+v", summary)
	}
	if math.Abs(summary.GeometricMeanTotalRatio-2) > 1e-12 ||
		math.Abs(summary.MeanTotalDifferenceMS-2.5) > 1e-12 ||
		math.Abs(summary.GeometricMeanEvalOnlyRatio-2) > 1e-12 {
		t.Fatalf("unexpected pair metrics: %+v", summary)
	}
}
