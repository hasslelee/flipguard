package ckksplanner
import "testing"
func TestThesisVariantDefaultAndStructure(t *testing.T) {
 c:=validContractFixture()
 a,e:=Synthesize(c,DefaultPrimarySynthesisPolicy());if e!=nil{t.Fatal(e)}
 b,e:=ThesisInitialPlan(c,false);if e!=nil{t.Fatal(e)}
 if a.InitialCandidates[0].ID!=b.InitialCandidates[0].ID {t.Fatal("default C changed")}
 if DefaultPrimarySynthesisPolicy().PrecisionSlackMode!=PrecisionSlackNone {t.Fatal("global default changed")}
 d,e:=ThesisInitialPlan(c,true);if e!=nil{t.Fatal(e)}
 if !ThesisSameStructure(a.InitialCandidates[0],d.InitialCandidates[0]){t.Fatal("structure changed")}
 if d.InitialCandidates[0].Parameters.LogDefaultScale<a.InitialCandidates[0].Parameters.LogDefaultScale{t.Fatal("precision decreased")}
}
func TestThesisIndependentSlackBoundary(t *testing.T){
 f:=IndependentFacts{RequiredQPrimes:5,RescaleLevels:3,RequiredSlots:16,MaxOutputAbs:5}
 b,e:=GenerateIndependentCandidate(f,30,0);if e!=nil{t.Fatal(e)}
 c,a,e:=ThesisIndependentSlack(f,b);if e!=nil{t.Fatal(e)}
 if len(a)==0 || !ThesisSameStructure(b,c){t.Fatal("missing bounded static exploration")}
 if c.Parameters.LogDefaultScale<30||c.Parameters.LogDefaultScale>50{t.Fatal("scale range")}
 if _,e=ThesisConcreteRecord(c);e!=nil{t.Fatal(e)}
}
