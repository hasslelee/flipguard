package main

import "testing"

func TestFormatOptionalBool(t *testing.T) {
	truth := true
	falsehood := false
	tests := []struct {
		name  string
		value *bool
		want  string
	}{
		{name: "unavailable comparator", value: nil, want: "not_applicable"},
		{name: "equal", value: &truth, want: "true"},
		{name: "different", value: &falsehood, want: "false"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			if got := formatOptionalBool(test.value); got != test.want {
				t.Fatalf("formatOptionalBool() = %q, want %q", got, test.want)
			}
		})
	}
}
