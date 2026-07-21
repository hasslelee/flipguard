package ckksbackend

import (
	"encoding/hex"
	"strings"
	"testing"
)

func TestBuildCKKSProfileBoundFactsForAllProfiles(
	t *testing.T,
) {
	profiles := AllCKKSProfiles()

	if len(profiles) != 11 {
		t.Fatalf(
			"expected 11 profiles, got %d",
			len(profiles),
		)
	}

	digests := make(map[string]string)

	for _, profile := range profiles {
		facts, digest, err :=
			BuildCKKSProfileBoundFacts(
				profile,
			)
		if err != nil {
			t.Fatalf(
				"BuildCKKSProfileBoundFacts(%s) failed: %v",
				profile.Name,
				err,
			)
		}

		if facts.ProfileName != profile.Name {
			t.Fatalf(
				"profile name mismatch: got %q, expected %q",
				facts.ProfileName,
				profile.Name,
			)
		}
		if facts.LibraryVersion !=
			expectedLattigoVersion {
			t.Fatalf(
				"profile %s Lattigo version: got %q, expected %q",
				profile.Name,
				facts.LibraryVersion,
				expectedLattigoVersion,
			)
		}
		if facts.RingN !=
			1<<facts.LogN {
			t.Fatalf(
				"profile %s ring dimension mismatch",
				profile.Name,
			)
		}
		if facts.MaxLevel !=
			len(facts.QPrimes)-1 {
			t.Fatalf(
				"profile %s max-level mismatch",
				profile.Name,
			)
		}
		if facts.TotalQPBits !=
			facts.TotalQBits+
				facts.TotalPBits {
			t.Fatalf(
				"profile %s total QP bits mismatch",
				profile.Name,
			)
		}
		if facts.Semantics.CertificateEligible {
			t.Fatalf(
				"profile %s facts must not be certificate eligible",
				profile.Name,
			)
		}

		if !strings.HasPrefix(
			digest,
			"sha256:",
		) {
			t.Fatalf(
				"profile %s digest lacks sha256 prefix: %q",
				profile.Name,
				digest,
			)
		}

		decoded, err := hex.DecodeString(
			strings.TrimPrefix(
				digest,
				"sha256:",
			),
		)
		if err != nil {
			t.Fatalf(
				"profile %s digest decode failed: %v",
				profile.Name,
				err,
			)
		}
		if len(decoded) != 32 {
			t.Fatalf(
				"profile %s digest length: got %d, expected 32",
				profile.Name,
				len(decoded),
			)
		}

		if previous, exists :=
			digests[digest]; exists {
			t.Fatalf(
				"profiles %s and %s produced the same digest",
				previous,
				profile.Name,
			)
		}

		digests[digest] = profile.Name
	}
}

func TestBuildCKKSProfileBoundFactsIsDeterministic(
	t *testing.T,
) {
	profile, err := FindCKKSProfile(
		"default",
	)
	if err != nil {
		t.Fatalf(
			"FindCKKSProfile failed: %v",
			err,
		)
	}

	firstFacts, firstDigest, err :=
		BuildCKKSProfileBoundFacts(
			profile,
		)
	if err != nil {
		t.Fatalf(
			"first facts build failed: %v",
			err,
		)
	}

	secondFacts, secondDigest, err :=
		BuildCKKSProfileBoundFacts(
			profile,
		)
	if err != nil {
		t.Fatalf(
			"second facts build failed: %v",
			err,
		)
	}

	firstJSON, err :=
		firstFacts.CanonicalJSON()
	if err != nil {
		t.Fatalf(
			"first canonical JSON failed: %v",
			err,
		)
	}

	secondJSON, err :=
		secondFacts.CanonicalJSON()
	if err != nil {
		t.Fatalf(
			"second canonical JSON failed: %v",
			err,
		)
	}

	if string(firstJSON) !=
		string(secondJSON) {
		t.Fatal(
			"profile facts canonical JSON is not deterministic",
		)
	}
	if firstDigest != secondDigest {
		t.Fatalf(
			"profile facts digest changed: %s != %s",
			firstDigest,
			secondDigest,
		)
	}
}

func TestProfileFactsDoNotClaimEndToEndBound(
	t *testing.T,
) {
	profile, err := FindCKKSProfile(
		"short_chain_6_scale40",
	)
	if err != nil {
		t.Fatalf(
			"FindCKKSProfile failed: %v",
			err,
		)
	}

	facts, _, err :=
		BuildCKKSProfileBoundFacts(
			profile,
		)
	if err != nil {
		t.Fatalf(
			"BuildCKKSProfileBoundFacts failed: %v",
			err,
		)
	}

	if facts.Semantics.
		DirectEndToEndAbsoluteBoundAvailable {
		t.Fatal(
			"unexpected direct end-to-end bound claim",
		)
	}
	if facts.Semantics.
		DirectFailureProbabilityAvailable {
		t.Fatal(
			"unexpected direct failure-probability claim",
		)
	}
	if facts.Semantics.CertificateEligible {
		t.Fatal(
			"profile facts alone cannot issue a certificate",
		)
	}

	if !strings.Contains(
		facts.Semantics.
			FreshPublicKeyNoiseMeaning,
		"standard deviation",
	) {
		t.Fatal(
			"fresh PK noise semantics must identify a standard deviation",
		)
	}
	if !strings.Contains(
		facts.Semantics.
			NoiseBoundMeaning,
		"truncation",
	) {
		t.Fatal(
			"noise bound semantics must identify a truncation bound",
		)
	}
}

func TestProfileScaleChangesFactsDigest(
	t *testing.T,
) {
	defaultProfile, err := FindCKKSProfile(
		"default",
	)
	if err != nil {
		t.Fatalf(
			"find default profile: %v",
			err,
		)
	}

	scale38Profile, err := FindCKKSProfile(
		"scale38",
	)
	if err != nil {
		t.Fatalf(
			"find scale38 profile: %v",
			err,
		)
	}

	_, defaultDigest, err :=
		BuildCKKSProfileBoundFacts(
			defaultProfile,
		)
	if err != nil {
		t.Fatalf(
			"build default facts: %v",
			err,
		)
	}

	_, scale38Digest, err :=
		BuildCKKSProfileBoundFacts(
			scale38Profile,
		)
	if err != nil {
		t.Fatalf(
			"build scale38 facts: %v",
			err,
		)
	}

	if defaultDigest == scale38Digest {
		t.Fatal(
			"default and scale38 profiles produced identical facts digests",
		)
	}
}
