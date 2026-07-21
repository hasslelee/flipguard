package certify

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestAnalyticalSourceBundleMatchesVersion1GoldenVector(
	t *testing.T,
) {
	root := writeAnalyticalSourceFixture(t)

	bundle, err := BuildAnalyticalSourceBundle(
		root,
		[]string{
			"internal/sub/b.txt",
			"internal/a.go",
		},
	)
	if err != nil {
		t.Fatalf(
			"build source bundle: %v",
			err,
		)
	}

	got, err := bundle.Digest()
	if err != nil {
		t.Fatalf(
			"digest source bundle: %v",
			err,
		)
	}

	const expected = "sha256:" +
		"4600472991b5b1a4f4a92b435c295824" +
		"31738624ccfed890aeea2ed03c542d66"

	if got != expected {
		t.Fatalf(
			"analytical source-bundle schema-v1 digest changed: got %s, expected %s",
			got,
			expected,
		)
	}

	if len(bundle.Files) != 2 {
		t.Fatalf(
			"source file count: got %d, expected 2",
			len(bundle.Files),
		)
	}

	if bundle.Files[0].Path !=
		"internal/a.go" {
		t.Fatalf(
			"first canonical path: got %q",
			bundle.Files[0].Path,
		)
	}

	if bundle.Files[1].Path !=
		"internal/sub/b.txt" {
		t.Fatalf(
			"second canonical path: got %q",
			bundle.Files[1].Path,
		)
	}
}

func TestAnalyticalSourceBundleIsIndependentOfCheckoutRoot(
	t *testing.T,
) {
	firstRoot := writeAnalyticalSourceFixture(t)
	secondRoot := writeAnalyticalSourceFixture(t)

	paths := []string{
		"internal/a.go",
		"internal/sub/b.txt",
	}

	first, err := BuildAnalyticalSourceBundle(
		firstRoot,
		paths,
	)
	if err != nil {
		t.Fatalf(
			"build first source bundle: %v",
			err,
		)
	}

	second, err := BuildAnalyticalSourceBundle(
		secondRoot,
		paths,
	)
	if err != nil {
		t.Fatalf(
			"build second source bundle: %v",
			err,
		)
	}

	firstDigest, err := first.Digest()
	if err != nil {
		t.Fatalf(
			"digest first source bundle: %v",
			err,
		)
	}

	secondDigest, err := second.Digest()
	if err != nil {
		t.Fatalf(
			"digest second source bundle: %v",
			err,
		)
	}

	if firstDigest != secondDigest {
		t.Fatalf(
			"checkout root changed digest: %s != %s",
			firstDigest,
			secondDigest,
		)
	}
}

func TestAnalyticalSourceBundleChangesWithFileContents(
	t *testing.T,
) {
	root := writeAnalyticalSourceFixture(t)

	paths := []string{
		"internal/a.go",
		"internal/sub/b.txt",
	}

	before, err := BuildAnalyticalSourceBundle(
		root,
		paths,
	)
	if err != nil {
		t.Fatalf(
			"build source bundle before change: %v",
			err,
		)
	}

	if err := os.WriteFile(
		filepath.Join(
			root,
			"internal",
			"a.go",
		),
		[]byte("package changed\n"),
		0o644,
	); err != nil {
		t.Fatalf(
			"modify source fixture: %v",
			err,
		)
	}

	after, err := BuildAnalyticalSourceBundle(
		root,
		paths,
	)
	if err != nil {
		t.Fatalf(
			"build source bundle after change: %v",
			err,
		)
	}

	requireDifferentSourceBundleDigest(
		t,
		before,
		after,
		"file contents",
	)
}

func TestAnalyticalSourceBundleChangesWithPath(
	t *testing.T,
) {
	root := writeAnalyticalSourceFixture(t)

	first, err := BuildAnalyticalSourceBundle(
		root,
		[]string{
			"internal/a.go",
		},
	)
	if err != nil {
		t.Fatalf(
			"build first path bundle: %v",
			err,
		)
	}

	renamedPath := filepath.Join(
		root,
		"internal",
		"renamed.go",
	)

	if err := os.WriteFile(
		renamedPath,
		[]byte("package a\n"),
		0o644,
	); err != nil {
		t.Fatalf(
			"write renamed fixture: %v",
			err,
		)
	}

	second, err := BuildAnalyticalSourceBundle(
		root,
		[]string{
			"internal/renamed.go",
		},
	)
	if err != nil {
		t.Fatalf(
			"build renamed path bundle: %v",
			err,
		)
	}

	requireDifferentSourceBundleDigest(
		t,
		first,
		second,
		"file path",
	)
}

func TestAnalyticalSourceBundleRejectsDuplicatePath(
	t *testing.T,
) {
	root := writeAnalyticalSourceFixture(t)

	_, err := BuildAnalyticalSourceBundle(
		root,
		[]string{
			"internal/a.go",
			"internal/a.go",
		},
	)

	if err == nil {
		t.Fatal(
			"expected duplicate source path to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"duplicate path",
	) {
		t.Fatalf(
			"unexpected duplicate-path error: %v",
			err,
		)
	}
}

func TestAnalyticalSourceBundleRejectsUnsafePaths(
	t *testing.T,
) {
	root := writeAnalyticalSourceFixture(t)

	testCases := []string{
		"",
		" internal/a.go",
		"internal/a.go ",
		"/internal/a.go",
		"../internal/a.go",
		"internal/../a.go",
		"./internal/a.go",
		"internal//a.go",
		`internal\a.go`,
	}

	for _, unsafePath := range testCases {
		t.Run(
			unsafePath,
			func(t *testing.T) {
				_, err :=
					BuildAnalyticalSourceBundle(
						root,
						[]string{
							unsafePath,
						},
					)

				if err == nil {
					t.Fatalf(
						"expected unsafe path %q to fail",
						unsafePath,
					)
				}
			},
		)
	}
}

func TestAnalyticalSourceBundleRejectsSymlink(
	t *testing.T,
) {
	root := writeAnalyticalSourceFixture(t)

	linkPath := filepath.Join(
		root,
		"internal",
		"link.go",
	)

	if err := os.Symlink(
		"a.go",
		linkPath,
	); err != nil {
		t.Skipf(
			"symbolic links unavailable: %v",
			err,
		)
	}

	_, err := BuildAnalyticalSourceBundle(
		root,
		[]string{
			"internal/link.go",
		},
	)

	if err == nil {
		t.Fatal(
			"expected symbolic-link source path to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"symbolic link",
	) {
		t.Fatalf(
			"unexpected symbolic-link error: %v",
			err,
		)
	}
}

func TestAnalyticalSourceBundleValidateRejectsUnsortedFiles(
	t *testing.T,
) {
	bundle := AnalyticalSourceBundle{
		SchemaVersion: analyticalSourceBundleSchemaVersion,

		Files: []AnalyticalSourceFile{
			{
				Path:      "z.go",
				SizeBytes: 1,
				SHA256:    analyticalScopeTestDigest,
			},
			{
				Path:      "a.go",
				SizeBytes: 1,
				SHA256:    analyticalScopeTestDigest,
			},
		},
	}

	err := bundle.Validate()
	if err == nil {
		t.Fatal(
			"expected unsorted source bundle to fail",
		)
	}

	if !strings.Contains(
		err.Error(),
		"not in canonical order",
	) {
		t.Fatalf(
			"unexpected canonical-order error: %v",
			err,
		)
	}
}

func writeAnalyticalSourceFixture(
	t *testing.T,
) string {
	t.Helper()

	root := t.TempDir()

	subdirectory := filepath.Join(
		root,
		"internal",
		"sub",
	)

	if err := os.MkdirAll(
		subdirectory,
		0o755,
	); err != nil {
		t.Fatalf(
			"create source fixture directory: %v",
			err,
		)
	}

	if err := os.WriteFile(
		filepath.Join(
			root,
			"internal",
			"a.go",
		),
		[]byte("package a\n"),
		0o644,
	); err != nil {
		t.Fatalf(
			"write first source fixture: %v",
			err,
		)
	}

	if err := os.WriteFile(
		filepath.Join(
			subdirectory,
			"b.txt",
		),
		[]byte("line1\r\nline2\n"),
		0o644,
	); err != nil {
		t.Fatalf(
			"write second source fixture: %v",
			err,
		)
	}

	return root
}

func requireDifferentSourceBundleDigest(
	t *testing.T,
	first AnalyticalSourceBundle,
	second AnalyticalSourceBundle,
	changedField string,
) {
	t.Helper()

	firstDigest, err := first.Digest()
	if err != nil {
		t.Fatalf(
			"first source-bundle digest for %s failed: %v",
			changedField,
			err,
		)
	}

	secondDigest, err := second.Digest()
	if err != nil {
		t.Fatalf(
			"second source-bundle digest for %s failed: %v",
			changedField,
			err,
		)
	}

	if firstDigest == secondDigest {
		t.Fatalf(
			"%s change did not alter source-bundle digest",
			changedField,
		)
	}
}
