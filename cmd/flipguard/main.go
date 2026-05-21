package main

import (
	"log"

	"github.com/hasslelee/flipguard/internal/experiment"
)

func main() {
	if err := experiment.RunLogRegSmall(); err != nil {
		log.Fatalf("flipguard experiment failed: %v", err)
	}
}
