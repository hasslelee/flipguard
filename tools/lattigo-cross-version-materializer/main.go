package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"math"
	"math/bits"
	"os"
	"reflect"

	ckksv2 "github.com/ldsec/lattigo/v2/ckks"
	rlwev2 "github.com/ldsec/lattigo/v2/rlwe"
	"github.com/tuneinsight/lattigo/v6/ring"
	ckksv6 "github.com/tuneinsight/lattigo/v6/schemes/ckks"
)

const schemaVersion = "flipguard_lattigo_cross_version_materialization_v1"

type materialization struct {
	SchemaVersion string  `json:"schema_version"`
	Input         input   `json:"input"`
	Derived       derived `json:"derived"`

	LattigoV2          concreteParameters  `json:"lattigo_v2_2_0"`
	V6NativeLogLiteral *concreteParameters `json:"lattigo_v6_2_0_native_log_literal,omitempty"`
	V6NativeLogError   string              `json:"lattigo_v6_2_0_native_log_literal_error,omitempty"`
	V6ConcreteImport   concreteParameters  `json:"lattigo_v6_2_0_concrete_import"`

	NativeLogQIdentical *bool `json:"native_log_q_identical,omitempty"`
	NativeLogPIdentical *bool `json:"native_log_p_identical,omitempty"`

	ConcreteImportQIdentical bool `json:"concrete_import_q_identical"`
	ConcreteImportPIdentical bool `json:"concrete_import_p_identical"`
	ScaleIdentical           bool `json:"scale_identical"`
	RingIdentical            bool `json:"ring_identical"`
	XsIdentical              bool `json:"xs_identical"`
	XeIdentical              bool `json:"xe_identical"`
	ExactConcreteTranslation bool `json:"exact_concrete_translation"`
}

type input struct {
	NumSlots    int `json:"num_slots"`
	MaxCTLevel  int `json:"max_ct_level"`
	LogScale    int `json:"log_scale"`
	NumKSPrimes int `json:"num_ks_primes"`
}

type derived struct {
	LogN int   `json:"log_n"`
	LogQ []int `json:"log_q"`
	LogP []int `json:"log_p"`
}

type concreteParameters struct {
	Module          string   `json:"module"`
	Version         string   `json:"version"`
	LogN            int      `json:"log_n"`
	Q               []uint64 `json:"q"`
	P               []uint64 `json:"p"`
	LogDefaultScale int      `json:"log_default_scale"`
	MaxSlots        int      `json:"max_slots"`
	RingType        string   `json:"ring_type"`
	Xs              string   `json:"xs"`
	Xe              string   `json:"xe"`
}

func main() {
	if err := run(os.Args[1:], os.Stdout); errors.Is(err, flag.ErrHelp) {
		return
	} else if err != nil {
		fmt.Fprintf(os.Stderr, "lattigo-cross-version-materializer: %v\n", err)
		os.Exit(1)
	}
}

func run(args []string, output io.Writer) error {
	flags := flag.NewFlagSet(
		"lattigo-cross-version-materializer",
		flag.ContinueOnError,
	)
	flags.SetOutput(output)
	numSlots := flags.Int("num-slots", 0, "HIT requested number of slots")
	maxCTLevel := flags.Int(
		"max-ct-level",
		-1,
		"HIT maximum ciphertext level",
	)
	logScale := flags.Int("log-scale", 0, "HIT CKKS log scale")
	numKSPrimes := flags.Int(
		"num-ks-primes",
		1,
		"HIT key-switch prime count",
	)
	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf("unexpected positional arguments: %v", flags.Args())
	}
	result, err := materialize(input{
		NumSlots:    *numSlots,
		MaxCTLevel:  *maxCTLevel,
		LogScale:    *logScale,
		NumKSPrimes: *numKSPrimes,
	})
	if err != nil {
		return err
	}
	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	return encoder.Encode(result)
}

func materialize(in input) (materialization, error) {
	if in.NumSlots <= 0 || in.NumSlots&(in.NumSlots-1) != 0 {
		return materialization{}, fmt.Errorf(
			"num-slots must be a positive power of two",
		)
	}
	if in.MaxCTLevel < 0 {
		return materialization{}, fmt.Errorf(
			"max-ct-level must be non-negative",
		)
	}
	if in.LogScale <= 0 || in.LogScale >= 63 {
		return materialization{}, fmt.Errorf(
			"log-scale must be in [1,62]",
		)
	}
	if in.NumKSPrimes <= 0 {
		return materialization{}, fmt.Errorf(
			"num-ks-primes must be positive",
		)
	}

	logN := bits.TrailingZeros(uint(in.NumSlots)) + 1
	logQ := make([]int, in.MaxCTLevel+1)
	for index := range logQ {
		logQ[index] = in.LogScale
	}
	logQ[0] = 60
	logP := make([]int, in.NumKSPrimes)
	for index := range logP {
		logP[index] = 61
	}

	v2, err := ckksv2.NewParametersFromLiteral(ckksv2.ParametersLiteral{
		LogN:     logN,
		LogQ:     logQ,
		LogP:     logP,
		Sigma:    rlwev2.DefaultSigma,
		LogSlots: logN - 1,
		Scale:    math.Exp2(float64(in.LogScale)),
	})
	if err != nil {
		return materialization{}, fmt.Errorf(
			"materialize Lattigo v2.2.0: %w",
			err,
		)
	}
	v6Native, nativeErr := ckksv6.NewParametersFromLiteral(
		ckksv6.ParametersLiteral{
			LogN:            logN,
			LogQ:            logQ,
			LogP:            logP,
			LogDefaultScale: in.LogScale,
			Xs:              ring.Ternary{P: 2.0 / 3.0},
			Xe: ring.DiscreteGaussian{
				Sigma: 3.2,
				Bound: 19.2,
			},
			RingType: ring.Standard,
		},
	)
	v6Imported, err := ckksv6.NewParametersFromLiteral(
		ckksv6.ParametersLiteral{
			LogN:            logN,
			Q:               v2.Q(),
			P:               v2.P(),
			LogDefaultScale: in.LogScale,
			Xs:              ring.Ternary{P: 2.0 / 3.0},
			Xe: ring.DiscreteGaussian{
				Sigma: 3.2,
				Bound: 19.2,
			},
			RingType: ring.Standard,
		},
	)
	if err != nil {
		return materialization{}, fmt.Errorf(
			"import concrete Lattigo v2.2.0 primes into v6.2.0: %w",
			err,
		)
	}

	v2Concrete := concreteParameters{
		Module:          "github.com/ldsec/lattigo/v2",
		Version:         "v2.2.0",
		LogN:            v2.LogN(),
		Q:               v2.Q(),
		P:               v2.P(),
		LogDefaultScale: int(math.Round(math.Log2(v2.Scale()))),
		MaxSlots:        v2.Slots(),
		RingType:        "standard",
		Xs:              "uniform_ternary_[1/3,1/3,1/3]",
		Xe:              "discrete_gaussian_sigma_3.2_bound_19.2",
	}
	v6ConcreteImport := concreteParameters{
		Module:          "github.com/tuneinsight/lattigo/v6",
		Version:         "v6.2.0",
		LogN:            v6Imported.LogN(),
		Q:               v6Imported.Q(),
		P:               v6Imported.P(),
		LogDefaultScale: v6Imported.LogDefaultScale(),
		MaxSlots:        v6Imported.MaxSlots(),
		RingType:        "standard",
		Xs:              "uniform_ternary_[1/3,1/3,1/3]",
		Xe:              "discrete_gaussian_sigma_3.2_bound_19.2",
	}
	qEqual := reflect.DeepEqual(v2Concrete.Q, v6ConcreteImport.Q)
	pEqual := reflect.DeepEqual(v2Concrete.P, v6ConcreteImport.P)
	scaleEqual := v2Concrete.LogDefaultScale ==
		v6ConcreteImport.LogDefaultScale
	ringEqual := v2Concrete.RingType == v6ConcreteImport.RingType
	xsEqual := v2Concrete.Xs == v6ConcreteImport.Xs
	xeEqual := v2Concrete.Xe == v6ConcreteImport.Xe
	result := materialization{
		SchemaVersion: schemaVersion,
		Input:         in,
		Derived: derived{
			LogN: logN,
			LogQ: logQ,
			LogP: logP,
		},
		LattigoV2:                v2Concrete,
		V6ConcreteImport:         v6ConcreteImport,
		ConcreteImportQIdentical: qEqual,
		ConcreteImportPIdentical: pEqual,
		ScaleIdentical:           scaleEqual,
		RingIdentical:            ringEqual,
		XsIdentical:              xsEqual,
		XeIdentical:              xeEqual,
		ExactConcreteTranslation: qEqual && pEqual && scaleEqual &&
			ringEqual && xsEqual && xeEqual,
	}
	if nativeErr != nil {
		result.V6NativeLogError = nativeErr.Error()
	} else {
		native := concreteParameters{
			Module:          "github.com/tuneinsight/lattigo/v6",
			Version:         "v6.2.0",
			LogN:            v6Native.LogN(),
			Q:               v6Native.Q(),
			P:               v6Native.P(),
			LogDefaultScale: v6Native.LogDefaultScale(),
			MaxSlots:        v6Native.MaxSlots(),
			RingType:        "standard",
			Xs:              "uniform_ternary_[1/3,1/3,1/3]",
			Xe:              "discrete_gaussian_sigma_3.2_bound_19.2",
		}
		nativeQEqual := reflect.DeepEqual(v2Concrete.Q, native.Q)
		nativePEqual := reflect.DeepEqual(v2Concrete.P, native.P)
		result.V6NativeLogLiteral = &native
		result.NativeLogQIdentical = &nativeQEqual
		result.NativeLogPIdentical = &nativePEqual
	}
	return result, nil
}
