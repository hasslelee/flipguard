package certify

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	pathpkg "path"
	"path/filepath"
	"sort"
	"strings"
)

const analyticalSourceBundleSchemaVersion = 1

// AnalyticalSourceFile identifies one exact regular source file.
//
// Path is repository-root relative and uses forward slashes. SHA256 binds the
// exact bytes. The absolute checkout root is intentionally excluded.
type AnalyticalSourceFile struct {
	Path string `json:"path"`

	SizeBytes int64 `json:"size_bytes"`

	SHA256 string `json:"sha256"`
}

// AnalyticalSourceBundle is a canonical manifest of the exact implementation
// files to which an analytical result is bound.
//
// Files are stored in lexicographic path order, making the digest independent
// of caller-provided ordering and absolute checkout location.
type AnalyticalSourceBundle struct {
	SchemaVersion int `json:"schema_version"`

	Files []AnalyticalSourceFile `json:"files"`
}

// BuildAnalyticalSourceBundle reads and hashes an explicit set of regular
// files below root.
//
// The function rejects path traversal, absolute paths, duplicate paths, and
// paths that traverse symbolic links. It never recursively includes files that
// were not explicitly requested.
func BuildAnalyticalSourceBundle(
	root string,
	relativePaths []string,
) (
	AnalyticalSourceBundle,
	error,
) {
	if strings.TrimSpace(root) == "" {
		return AnalyticalSourceBundle{}, fmt.Errorf(
			"analytical source-bundle root is empty",
		)
	}

	if len(relativePaths) == 0 {
		return AnalyticalSourceBundle{}, fmt.Errorf(
			"analytical source bundle has no files",
		)
	}

	absoluteRoot, err := filepath.Abs(root)
	if err != nil {
		return AnalyticalSourceBundle{}, fmt.Errorf(
			"resolve analytical source-bundle root: %w",
			err,
		)
	}

	resolvedRoot, err :=
		filepath.EvalSymlinks(absoluteRoot)
	if err != nil {
		return AnalyticalSourceBundle{}, fmt.Errorf(
			"resolve analytical source-bundle root symlinks: %w",
			err,
		)
	}

	rootInfo, err := os.Stat(resolvedRoot)
	if err != nil {
		return AnalyticalSourceBundle{}, fmt.Errorf(
			"stat analytical source-bundle root: %w",
			err,
		)
	}

	if !rootInfo.IsDir() {
		return AnalyticalSourceBundle{}, fmt.Errorf(
			"analytical source-bundle root is not a directory",
		)
	}

	sortedPaths := append(
		[]string(nil),
		relativePaths...,
	)

	sort.Strings(sortedPaths)

	files := make(
		[]AnalyticalSourceFile,
		0,
		len(sortedPaths),
	)

	seen := make(
		map[string]struct{},
		len(sortedPaths),
	)

	for _, relativePath := range sortedPaths {
		if err := validateAnalyticalSourceRelativePath(
			relativePath,
		); err != nil {
			return AnalyticalSourceBundle{}, err
		}

		if _, exists := seen[relativePath]; exists {
			return AnalyticalSourceBundle{}, fmt.Errorf(
				"analytical source bundle has duplicate path %q",
				relativePath,
			)
		}

		seen[relativePath] = struct{}{}

		fullPath := filepath.Join(
			resolvedRoot,
			filepath.FromSlash(relativePath),
		)

		resolvedPath, err :=
			filepath.EvalSymlinks(fullPath)
		if err != nil {
			return AnalyticalSourceBundle{}, fmt.Errorf(
				"resolve analytical source file %q: %w",
				relativePath,
				err,
			)
		}

		if filepath.Clean(resolvedPath) !=
			filepath.Clean(fullPath) {
			return AnalyticalSourceBundle{}, fmt.Errorf(
				"analytical source file %q must not traverse a symbolic link",
				relativePath,
			)
		}

		resolvedRelative, err := filepath.Rel(
			resolvedRoot,
			resolvedPath,
		)
		if err != nil {
			return AnalyticalSourceBundle{}, fmt.Errorf(
				"resolve analytical source file %q relative to root: %w",
				relativePath,
				err,
			)
		}

		if resolvedRelative == ".." ||
			strings.HasPrefix(
				resolvedRelative,
				".."+string(filepath.Separator),
			) ||
			filepath.IsAbs(resolvedRelative) {
			return AnalyticalSourceBundle{}, fmt.Errorf(
				"analytical source file %q escapes the source root",
				relativePath,
			)
		}

		info, err := os.Lstat(resolvedPath)
		if err != nil {
			return AnalyticalSourceBundle{}, fmt.Errorf(
				"stat analytical source file %q: %w",
				relativePath,
				err,
			)
		}

		if !info.Mode().IsRegular() {
			return AnalyticalSourceBundle{}, fmt.Errorf(
				"analytical source file %q is not a regular file",
				relativePath,
			)
		}

		data, err := os.ReadFile(resolvedPath)
		if err != nil {
			return AnalyticalSourceBundle{}, fmt.Errorf(
				"read analytical source file %q: %w",
				relativePath,
				err,
			)
		}

		sum := sha256.Sum256(data)

		files = append(
			files,
			AnalyticalSourceFile{
				Path: relativePath,

				SizeBytes: int64(len(data)),

				SHA256: "sha256:" +
					hex.EncodeToString(sum[:]),
			},
		)
	}

	bundle := AnalyticalSourceBundle{
		SchemaVersion: analyticalSourceBundleSchemaVersion,

		Files: files,
	}

	if err := bundle.Validate(); err != nil {
		return AnalyticalSourceBundle{}, fmt.Errorf(
			"validate generated analytical source bundle: %w",
			err,
		)
	}

	return bundle, nil
}

// Validate checks canonical ordering, path safety, and exact digest syntax.
func (bundle AnalyticalSourceBundle) Validate() error {
	if bundle.SchemaVersion !=
		analyticalSourceBundleSchemaVersion {
		return fmt.Errorf(
			"unsupported analytical source-bundle schema version %d",
			bundle.SchemaVersion,
		)
	}

	if len(bundle.Files) == 0 {
		return fmt.Errorf(
			"analytical source bundle has no files",
		)
	}

	previousPath := ""

	for index, file := range bundle.Files {
		if err := validateAnalyticalSourceRelativePath(
			file.Path,
		); err != nil {
			return fmt.Errorf(
				"validate analytical source file %d: %w",
				index,
				err,
			)
		}

		if index > 0 &&
			file.Path <= previousPath {
			if file.Path == previousPath {
				return fmt.Errorf(
					"analytical source bundle has duplicate path %q",
					file.Path,
				)
			}

			return fmt.Errorf(
				"analytical source bundle paths are not in canonical order: %q precedes %q",
				file.Path,
				previousPath,
			)
		}

		if file.SizeBytes < 0 {
			return fmt.Errorf(
				"analytical source file %q has negative size",
				file.Path,
			)
		}

		if err := validateAnalyticalProofDigest(
			"source file "+file.Path,
			file.SHA256,
		); err != nil {
			return err
		}

		previousPath = file.Path
	}

	return nil
}

// CanonicalJSON returns the root-independent representation used by Digest.
func (bundle AnalyticalSourceBundle) CanonicalJSON() (
	[]byte,
	error,
) {
	if err := bundle.Validate(); err != nil {
		return nil, err
	}

	encoded, err := json.Marshal(bundle)
	if err != nil {
		return nil, fmt.Errorf(
			"marshal analytical source bundle: %w",
			err,
		)
	}

	return encoded, nil
}

// Digest returns the SHA-256 digest of the canonical source manifest.
//
// Each manifest entry already contains the exact file-byte SHA-256, so this
// digest transitively binds every requested file's path, size, and contents.
func (bundle AnalyticalSourceBundle) Digest() (
	string,
	error,
) {
	canonical, err := bundle.CanonicalJSON()
	if err != nil {
		return "", err
	}

	sum := sha256.Sum256(canonical)

	return "sha256:" +
		hex.EncodeToString(sum[:]), nil
}

func validateAnalyticalSourceRelativePath(
	value string,
) error {
	if value == "" {
		return fmt.Errorf(
			"analytical source path is empty",
		)
	}

	if strings.TrimSpace(value) != value {
		return fmt.Errorf(
			"analytical source path %q has surrounding whitespace",
			value,
		)
	}

	if strings.ContainsRune(value, '\x00') {
		return fmt.Errorf(
			"analytical source path contains a NUL byte",
		)
	}

	if strings.Contains(value, `\`) {
		return fmt.Errorf(
			"analytical source path %q must use forward slashes",
			value,
		)
	}

	if pathpkg.IsAbs(value) {
		return fmt.Errorf(
			"analytical source path %q must be relative",
			value,
		)
	}

	cleaned := pathpkg.Clean(value)

	if cleaned != value {
		return fmt.Errorf(
			"analytical source path %q is not canonical; expected %q",
			value,
			cleaned,
		)
	}

	if cleaned == "." ||
		cleaned == ".." ||
		strings.HasPrefix(cleaned, "../") {
		return fmt.Errorf(
			"analytical source path %q escapes the source root",
			value,
		)
	}

	return nil
}
