package experiment

import (
	"path/filepath"
	"strings"
)

// CKKSResultDir returns a CKKS result directory with an optional output tag.
func CKKSResultDir(base string) string {
	tag := sanitizeOutputTag(GetRuntimeOptions().CKKSOutputTag)
	if tag == "" {
		return base
	}

	return filepath.Join(base, tag)
}

// CKKSResultPath returns a CKKS result file path with an optional output tag.
func CKKSResultPath(base string, name string) string {
	return filepath.Join(CKKSResultDir(base), name)
}

func sanitizeOutputTag(tag string) string {
	tag = strings.TrimSpace(tag)
	if tag == "" {
		return ""
	}

	var builder strings.Builder
	builder.Grow(len(tag))

	for i := 0; i < len(tag); i++ {
		ch := tag[i]

		switch {
		case ch >= 'a' && ch <= 'z':
			builder.WriteByte(ch)
		case ch >= 'A' && ch <= 'Z':
			builder.WriteByte(ch)
		case ch >= '0' && ch <= '9':
			builder.WriteByte(ch)
		case ch == '.', ch == '_', ch == '-':
			builder.WriteByte(ch)
		case ch == ' ':
			builder.WriteByte('_')
		default:
			builder.WriteByte('_')
		}
	}

	return strings.Trim(builder.String(), "._-")
}
