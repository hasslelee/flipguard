package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"sort"

	"github.com/hasslelee/flipguard/internal/experiment"
)

type experimentEntry struct {
	Name        string
	Description string
	Run         func() error
}

func main() {
	experiments := map[string]experimentEntry{
		"logreg_small": {
			Name:        "logreg_small",
			Description: "Boundary-focused polynomial logistic-style decision-stability simulation",
			Run:         experiment.RunLogRegSmall,
		},
	}

	experimentName := flag.String("experiment", "logreg_small", "experiment name to run")
	listExperiments := flag.Bool("list", false, "list available experiments")
	flag.Parse()

	if *listExperiments {
		printExperiments(experiments)
		return
	}

	entry, ok := experiments[*experimentName]
	if !ok {
		fmt.Fprintf(os.Stderr, "unknown experiment: %s\n\n", *experimentName)
		printExperiments(experiments)
		os.Exit(2)
	}

	fmt.Printf("Running experiment: %s\n", entry.Name)
	fmt.Printf("Description: %s\n\n", entry.Description)

	if err := entry.Run(); err != nil {
		log.Fatalf("flipguard experiment %s failed: %v", entry.Name, err)
	}
}

func printExperiments(experiments map[string]experimentEntry) {
	names := make([]string, 0, len(experiments))
	for name := range experiments {
		names = append(names, name)
	}
	sort.Strings(names)

	fmt.Println("Available experiments:")
	for _, name := range names {
		entry := experiments[name]
		fmt.Printf("  %-16s %s\n", entry.Name, entry.Description)
	}
}
