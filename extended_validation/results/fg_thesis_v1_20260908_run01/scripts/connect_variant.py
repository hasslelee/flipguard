from pathlib import Path
R=Path('/home/ckks2/deciprotect/research/thesis_validation_v1')
for cmd in ['contribution-case','bank-case']:
 p=R/'cmd'/cmd/'main.go';s=p.read_text()
 s=s.replace('var ioMS float64','var ioMS float64\nvar thesisDelta = .001\nvar thesisRho = .5\nvar thesisSlack bool\nvar thesisBSlack bool')
 s=s.replace('flag.Parse()','flag.Float64Var(&thesisDelta, "delta", .001, "sensitivity margin floor")\n\tflag.Float64Var(&thesisRho, "rho", .5, "sensitivity error fraction")\n\tflag.BoolVar(&thesisSlack, "cprime", false, "isolated existing optional precision slack")\n\tflag.BoolVar(&thesisBSlack, "b-slack", false, "independent auxiliary slack")\n\tflag.Parse()\n\tif thesisSlack && *role != "C" { panic("Cprime only for C") }\n\tif thesisBSlack && *role != "B" { panic("B slack only for B") }\n\tif (thesisSlack || thesisBSlack) && (thesisDelta != .001 || thesisRho != .5) { panic("no compound policy variants") }')
 if cmd=='contribution-case':
  s=s.replace('o := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()','o := ckksplanner.DefaultJournalMNISTMulticlassContractOptions()\n\t\to.MarginFloor = thesisDelta\n\t\to.MarginUtilizationCap = thesisRho')
  s=s.replace('o := ckksplanner.DefaultPrimaryTabularContractOptions()','o := ckksplanner.DefaultPrimaryTabularContractOptions()\n\to.MarginFloor = thesisDelta\n\to.SafetyFactor = thesisRho')
 else:
  # Bank Cprime is not combined with sensitivity or a changed selection contract.
  s=s.replace('c := old.Contract','c := old.Contract\n\tif thesisDelta != .001 || thesisRho != .5 { panic("Bank sensitivity is offline-only") }')
 s=s.replace('c := old.Contract','c := old.Contract\n\tif *data != "" && (*mode == "select" || *mode == "plan") { c = freshContract(c, *data, "configuration_validation") }',1)
 s=s.replace('if *mode == "select" {','if *mode == "plan" {\n\t\tc = freshContract(c,c.ValidationData.Path,"configuration_validation")\n\t\tp,e := ckksplanner.ThesisInitialPlan(c,thesisSlack);must(e)\n\t\tcr,e:=ckksplanner.ThesisConcreteRecord(p.InitialCandidates[0]);must(e)\n\t\tsave(filepath.Join(*out,"plan.json"),p)\n\t\tsave(filepath.Join(*out,"result.json"),map[string]any{"plan":p,"concrete":cr,"wall_ms":ms(start),"new_encrypted_calls":0})\n\t\treturn\n\t}\n\tif *mode == "select" {',1)
 s=s.replace('plan, e = ckksplanner.Synthesize(c, ckksplanner.DefaultPrimarySynthesisPolicy())','plan, e = ckksplanner.ThesisInitialPlan(c, thesisSlack)')
 s=s.replace('t := execute(c, cand, idx, filepath.Join(*out, fmt.Sprintf("trial_%d", idx)))','if thesisBSlack {\n\t\t\t\tvar at []map[string]any\n\t\t\t\tcand,at,e = ckksplanner.ThesisIndependentSlack(facts,cand);must(e)\n\t\t\t\tsave(filepath.Join(*out,fmt.Sprintf("slack_static_%d.json",idx)),at)\n\t\t\t}\n\t\t\tconcrete,e:=ckksplanner.ThesisConcreteRecord(cand);must(e)\n\t\t\tsave(filepath.Join(*out,fmt.Sprintf("concrete_%d.json",idx)),concrete)\n\t\t\tt := execute(c, cand, idx, filepath.Join(*out, fmt.Sprintf("trial_%d", idx)))')
 s=s.replace('"protocol": "FG_CONTRIB_V1_20260906"','"protocol": "FG_THESIS_V1_20260908", "cprime": thesisSlack, "b_slack": thesisBSlack, "rho": thesisRho, "delta": thesisDelta')
 # Audit uses fixed selected parameters, never runs selection/repair.
 s=s.replace('t := execute(c, cand, 1, *out)','cr,e:=ckksplanner.ThesisConcreteRecord(cand);must(e);save(filepath.Join(*out,"concrete.json"),cr)\n\t\tt := execute(c, cand, 1, *out)')
 p.write_text(s)
print('Connected only new CLI/wrapper; preserved legacy core files unchanged')
