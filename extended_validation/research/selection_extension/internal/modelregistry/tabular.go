package modelregistry

import "fmt"

type BodyKind string
type HeadKind string

const (
	BodyLinear           BodyKind = "linear"
	BodyOneHiddenSquare  BodyKind = "one_hidden_square"
	BodyTwoHiddenSquares BodyKind = "two_hidden_squares"

	HeadAffine HeadKind = "affine"
	HeadCubic  HeadKind = "cubic"
)

type TabularFamily struct {
	ModelType        string
	Body             BodyKind
	Head             HeadKind
	HiddenLayers     int
	PaperNameKO      string
	PaperNameEN      string
	ExpectedFormula  string
	V17PrimaryFamily bool
}

var tabularFamilies = map[string]TabularFamily{
	"linear_affine_score": {
		ModelType: "linear_affine_score", Body: BodyLinear, Head: HeadAffine,
		PaperNameKO: "선형 본체와 affine 출력", PaperNameEN: "linear body with affine output",
		ExpectedFormula: "0.5 + 0.197*z",
	},
	"linear_poly3": {
		ModelType: "linear_poly3", Body: BodyLinear, Head: HeadCubic,
		PaperNameKO: "3차 다항 임계값 모델", PaperNameEN: "cubic-polynomial threshold model",
		ExpectedFormula: "0.5 + 0.197*z - 0.004*z^3", V17PrimaryFamily: true,
	},
	"mlp_square_linear_score": {
		ModelType: "mlp_square_linear_score", Body: BodyOneHiddenSquare, Head: HeadAffine,
		HiddenLayers: 1, PaperNameKO: "얕은 제곱 활성화 MLP", PaperNameEN: "shallow square-activation MLP",
		ExpectedFormula: "0.5 + 0.197*z", V17PrimaryFamily: true,
	},
	"mlp_square_poly3": {
		ModelType: "mlp_square_poly3", Body: BodyOneHiddenSquare, Head: HeadCubic,
		HiddenLayers: 1, PaperNameKO: "제곱 MLP와 3차 출력", PaperNameEN: "square MLP with cubic output",
		ExpectedFormula: "0.5 + 0.197*z - 0.004*z^3",
	},
	"mlp_square2_linear_score": {
		ModelType: "mlp_square2_linear_score", Body: BodyTwoHiddenSquares, Head: HeadAffine,
		HiddenLayers: 2, PaperNameKO: "2층 제곱 활성화 MLP", PaperNameEN: "two-hidden-layer square-activation MLP",
		ExpectedFormula: "0.5 + 0.197*z", V17PrimaryFamily: true,
	},
}

func LookupTabular(modelType string) (TabularFamily, error) {
	family, ok := tabularFamilies[modelType]
	if !ok {
		return TabularFamily{}, fmt.Errorf("unsupported tabular model type %q", modelType)
	}
	return family, nil
}

func TabularFamilies() []TabularFamily {
	order := []string{
		"linear_affine_score",
		"linear_poly3",
		"mlp_square_linear_score",
		"mlp_square_poly3",
		"mlp_square2_linear_score",
	}
	result := make([]TabularFamily, 0, len(order))
	for _, modelType := range order {
		result = append(result, tabularFamilies[modelType])
	}
	return result
}
