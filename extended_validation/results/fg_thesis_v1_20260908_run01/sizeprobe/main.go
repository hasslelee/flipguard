// Material-size probe only. No user inputs, no inference, no secret-key serialization.
package main

import (
 "encoding/json"
 "flag"
 "os"
 "time"
 "github.com/tuneinsight/lattigo/v6/schemes/ckks"
)
func must(e error){if e!=nil{panic(e)}}
func main(){
 in:=flag.String("concrete","","public concrete parameters");out:=flag.String("out","","fresh output JSON");flag.Parse()
 var source struct {Concrete struct {LogN int `json:"log_n"`; Q []uint64 `json:"q"`; P []uint64 `json:"p"`; S int `json:"log_default_scale"`}}
 b,e:=os.ReadFile(*in);must(e);must(json.Unmarshal(b,&source));c:=source.Concrete
 params,e:=ckks.NewParametersFromLiteral(ckks.ParametersLiteral{LogN:c.LogN,Q:c.Q,P:c.P,LogDefaultScale:c.S});must(e)
 started:=time.Now();kg:=ckks.NewKeyGenerator(params);sk,pk:=kg.GenKeyPairNew();rlk:=kg.GenRelinearizationKeyNew(sk)
 setupMS:=float64(time.Since(started).Nanoseconds())/1e6
 started=time.Now();pub,e:=pk.MarshalBinary();must(e);relin,e:=rlk.MarshalBinary();must(e)
 keySerializeMS:=float64(time.Since(started).Nanoseconds())/1e6
 pt:=ckks.NewPlaintext(params,params.MaxLevel());must(ckks.NewEncoder(params).Encode(make([]float64,params.MaxSlots()),pt))
 ct,e:=ckks.NewEncryptor(params,pk).EncryptNew(pt);must(e)
 levels:=[]map[string]any{}
 for l:=params.MaxLevel();l>=0;l-- {ct.Resize(1,l);started=time.Now();b,e:=ct.MarshalBinary();must(e);levels=append(levels,map[string]any{"level":l,"bytes":len(b),"serialize_ms":float64(time.Since(started).Nanoseconds())/1e6})}
 result:=map[string]any{"kind":"fresh generated material size probe, not inference or network", "public_key_bytes":len(pub),"relinearization_key_bytes":len(relin),"rotation_key_count":0,"rotation_key_bytes":0,"secret_key_serialized":false,"setup_ms":setupMS,"key_serialization_ms":keySerializeMS,"ciphertext_degree":1,"ciphertext_by_level":levels,"Q":params.Q(),"P":params.P(),"log_n":params.LogN(),"valid_slots":params.MaxSlots(),"input_value":"zeros, independent of all evaluation datasets","size_interpretation":"measured one ciphertext at each representation level; aggregate sizes require actual ciphertext counts; no transport timing"}
 f,e:=os.OpenFile(*out,os.O_WRONLY|os.O_CREATE|os.O_EXCL,0644);must(e);en:=json.NewEncoder(f);en.SetIndent("","  ");must(en.Encode(result));must(f.Close())
}
