package ckksplanner

import "testing"

func TestJournalCatalogProfileSetIsFrozenSeven(t *testing.T) {
	if len(JournalSecurityV2AdmittedCatalogProfiles) != 7 {
		t.Fatalf("catalog denominator changed: %d", len(JournalSecurityV2AdmittedCatalogProfiles))
	}
	seen := map[string]bool{}
	for _, name := range JournalSecurityV2AdmittedCatalogProfiles {
		if seen[name] {
			t.Fatalf("duplicate catalog profile %s", name)
		}
		seen[name] = true
	}
}
