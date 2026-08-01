package ckksplanner

import (
	"math"
	"testing"

	"github.com/hasslelee/flipguard/internal/journalmnist"
)

func TestJournalMNISTGraphFacts(t *testing.T) {
	mlp, levels, q, err := journalMNISTGraphFacts(journalmnist.MLPModelType)
	if err != nil {
		t.Fatal(err)
	}
	if mlp.MultiplicativeDepth != 1 || mlp.MulOps != 79500 || levels != 3 || q != 4 {
		t.Fatalf("unexpected MLP facts: %+v levels=%d q=%d", mlp, levels, q)
	}
	lenet, levels, q, err := journalMNISTGraphFacts(journalmnist.LeNetModelType)
	if err != nil {
		t.Fatal(err)
	}
	if lenet.MultiplicativeDepth != 4 || lenet.MulOps != 421984 || levels != 12 || q != 13 {
		t.Fatalf("unexpected LeNet facts: %+v levels=%d q=%d", lenet, levels, q)
	}
}

func TestMulticlassTopTwoUsesLowestIndexTieBreak(t *testing.T) {
	top, runner, gap, tied, err := multiclassTopTwo([]float64{2, 2, 1})
	if err != nil {
		t.Fatal(err)
	}
	if top != 0 || runner != 1 || gap != 0 || !tied {
		t.Fatalf("unexpected tie result: top=%d runner=%d gap=%g tied=%t", top, runner, gap, tied)
	}
}

func TestDigestMulticlassPlaintextLogitsIsOrderSensitive(t *testing.T) {
	one := DigestMulticlassPlaintextLogits([]string{"a", "b"}, [][]float64{{1, 2}, {3, 4}})
	two := DigestMulticlassPlaintextLogits([]string{"b", "a"}, [][]float64{{3, 4}, {1, 2}})
	if one == two {
		t.Fatal("ordered multiclass digest must change with sample order")
	}
	three := DigestMulticlassPlaintextLogits([]string{"a", "b"}, [][]float64{{math.Nextafter(1, 2), 2}, {3, 4}})
	if one == three {
		t.Fatal("full-precision multiclass digest must change with one-bit logit change")
	}
}
