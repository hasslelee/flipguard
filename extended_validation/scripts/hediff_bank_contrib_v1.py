#!/usr/bin/env python3
"""Runs inside the isolated Python3.10 image. Official classes are loaded from
reviewed, digest-bound source; no original workspace or training weights used.
"""
import argparse,ast,csv,hashlib,json,time
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader,TensorDataset
import torch.optim as optim
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import shuffle
from imblearn.under_sampling import NearMiss
import tenseal as ts

ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'results/fg_contrib_v1_20260906_run01';OUT=RUN/'external/hediff_bank';SRC=ROOT/'work/fg_contrib_v1_20260906/hediff_source'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
def selected_source(file,names,env):
 tree=ast.parse((SRC/file).read_text());nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names];assert {n.name for n in nodes}==set(names)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SRC/file),'exec'),env)
 return env
def setup_model():
 env=selected_source('plain_models.py',['MLP_Bank','train','test'],dict(torch=torch,nn=nn));m=env['MLP_Bank']();return m,env
def public_context_parameters(context):
 """Read public modulus/context metadata only; never serialize secret keys."""
 begin=time.monotonic()
 try:
  sc=context.seal_context().data;kd=sc.key_context_data();dd=sc.first_context_data();kp=kd.parms();dp=dd.parms();qual=kd.qualifiers()
  result=dict(status='READ',poly_modulus_degree=int(kp.poly_modulus_degree()),key_moduli=[int(v.value()) for v in kp.coeff_modulus()],data_moduli=[int(v.value()) for v in dp.coeff_modulus()],key_total_modulus_bits=int(kd.total_coeff_modulus_bit_count()),data_total_modulus_bits=int(dd.total_coeff_modulus_bit_count()),parameters_set=bool(sc.parameters_set()),security_qualifier=str(qual.sec_level),auto_rescale=bool(context.auto_rescale),auto_mod_switch=bool(context.auto_mod_switch),auto_relin=bool(context.auto_relin),public_metadata_only=True)
 except Exception as e:
  result=dict(status='API_UNAVAILABLE',reason=repr(e),public_metadata_only=True)
 result['introspection_ms']=(time.monotonic()-begin)*1000
 return result
def double_logits(m,X):
 W=m.fc1.weight.detach().numpy().astype(float);b=m.fc1.bias.detach().numpy().astype(float);V=m.fc2.weight.detach().numpy().astype(float);d=m.fc2.bias.detach().numpy().astype(float);h=X.astype(float)@W.T+b;return (h*h+h)@V.T+d
def raw_csv(path,X,y,ids,original_ids):
 fields=['row_id','label','original_label','source_row_id']+[f'x_{j}' for j in range(20)]
 with path.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for x,label,i,source in zip(X,y,ids,original_ids):w.writerow(dict(row_id=int(i),label=int(label),original_label=int(label),source_row_id=int(source),**{f'x_{j}':format(float(v),'.17g') for j,v in enumerate(x)}))
def train():
 OUT.mkdir(parents=True,exist_ok=True);assert not (OUT/'TRAINING_COMPLETE.json').exists()
 torch.manual_seed(20260906);np.random.seed(20260906);torch.set_num_threads(4);torch.set_num_interop_threads(1)
 env=selected_source('handle_data.py',['load_bank','normalization'],dict(pd=pd,np=np,LabelEncoder=LabelEncoder))
 path=ROOT/'work/fg_contrib_v1_20260906/external_data/bank-additional-full.csv';X,y=env['load_bank'](str(path));source_min=X.min(axis=0).astype(float);source_max=X.max(axis=0).astype(float);source_integer=np.all(X==np.rint(X),axis=0);X=env['normalization'](X);assert np.isfinite(X).all()
 frame=pd.read_csv(path,sep=';');ids=frame.index[(frame!='unknown').all(axis=1)].to_numpy();assert len(ids)==len(X)
 sampler=NearMiss();XX,yy=sampler.fit_resample(X,y);original=ids[sampler.sample_indices_];XX,yy,original=shuffle(XX,yy,original,random_state=42)
 split=len(XX)-int(np.ceil(.2*len(XX)));Xtrain,ytrain=XX[:split],yy[:split];Xtest,ytest=XX[split:],yy[split:];assert len(Xtest)>176
 m,env=setup_model();loader=DataLoader(TensorDataset(torch.Tensor(Xtrain),torch.Tensor(ytrain)),batch_size=64);opt=optim.Adam(m.parameters());criterion=nn.CrossEntropyLoss();history=[];begin=time.monotonic()
 for epoch in range(1,101):
  env['train'](m,loader,opt,criterion);accuracy=env['test'](m,loader);history.append(dict(epoch=epoch,training_accuracy_percent=accuracy))
  if epoch%10==0:print('epoch',epoch,'train_accuracy',accuracy,flush=True)
 torch.save(m.state_dict(),OUT/'public_procedure_weights.pt');m.eval()
 W=m.fc1.weight.detach().numpy().astype(float);b=m.fc1.bias.detach().numpy().astype(float);V=m.fc2.weight.detach().numpy().astype(float);d=m.fc2.bias.detach().numpy().astype(float)
 model=dict(schema_version=1,dataset_id='hediff_bank_additional_public_procedure',model_id='hediff_bank_mlp_20_256_2_seed20260906',model_type='hediff_bank_exact_two_logit_square_adapter_v1',original_w1=W.tolist(),original_b1=b.tolist(),original_w2=V.tolist(),original_b2=d.tolist(),output_definition='original unnormalized two logits',algebra='each original logit retained: t*t+t=(t+.5)^2-.25; output bias adjusted separately per class; no output projection, normalization, or label inversion',training_seed=20260906)
 save(OUT/'model.json',model)
 check_indices=np.r_[0:16,48:176];check_X=Xtest[check_indices]
 logits=double_logits(m,check_X);mapped=(check_X.astype(float)@W.T+b+.5)**2@V.T+d-.25*V.sum(axis=1);reference=logits;diff=float(abs(mapped-reference).max());assert diff<1e-10

 with torch.no_grad():fp32=m(torch.Tensor(check_X)).numpy()
 role_idx={'configuration_selection':np.arange(0,16),'independent_evaluation':np.arange(16,48),'development':np.arange(48,176)}
 for role,ix in role_idx.items():raw_csv(OUT/(role+'.csv'),Xtest[ix],ytest[ix],split+ix,original[split+ix])
 # Fixed common plaintext-only stress, numeric/categorical validity distinct.
 X0=Xtest[16:32].astype(float);Xs=X0.copy();categorical=[1,2,3,4,5,6,7,8,9,14];mutable=np.ones(20);mutable[categorical]=0
 for _ in range(20):
  h=Xs@W.T+b;z=(h*h+h)@V.T+d;delta=z[:,0]-z[:,1];gradient=((2*h+1)*(V[0]-V[1]))@W;Xs-=.05/20*mutable*np.sign(delta[:,None]*gradient);Xs=np.clip(np.minimum(np.maximum(Xs,X0-.05),X0+.05),0,1)
 # Preserve the integer lattice of source ages/durations/counts as well as categories.
 for j in np.flatnonzero(source_integer):
  if j in categorical:continue
  span=source_max[j]-source_min[j];assert span>0
  low=np.ceil(source_min[j]+np.maximum(0,X0[:,j]-.05)*span);high=np.floor(source_min[j]+np.minimum(1,X0[:,j]+.05)*span);assert np.all(low<=high)
  restored=np.clip(np.rint(source_min[j]+Xs[:,j]*span),low,high);Xs[:,j]=(restored-source_min[j])/span
 Xs[:,categorical]=X0[:,categorical];assert np.max(abs(Xs-X0))<=.05+1e-12
 raw_csv(OUT/'stress.csv',Xs,ytest[16:32],split+np.arange(16,32),original[split+np.arange(16,32)])
 dev=reference[16:];e=dev-dev.astype(np.float16).astype(float);tau=dict(max_abs=float(abs(e).max()),rmse=float(np.sqrt(np.mean(e*e))))
 save(OUT/'INPUT_MODEL_LOCK.json',dict(seed=20260906,source_commit='ffeed7f131d4b55698a08798927777b44f508099',official_weight_availability='pretrained/.dummy only; original weights unavailable',public_procedure_retraining=True,original_model_reproduction=False,training_count=split,total_resampled=len(XX),test_count=len(Xtest),training_indices_original=original[:split].tolist(),test_indices_original=original[split:].tolist(),roles={k:dict(test_positions=v.tolist(),original_rows=original[split+v].tolist()) for k,v in role_idx.items()},numeric_thresholds=tau,source_sha256={p.name:sha(p) for p in SRC.glob('*.py')},files={p.name:sha(p) for p in OUT.glob('*') if p.is_file()},preprocessing='official complete-case categorical encoding, full-source minmax, NearMiss, shuffle42, final20percent test; full-source preprocessing/label resampling retained, not leakage-free accuracy validation',algebra_max_abs_diff=diff,float32_vs_float64_max_logit_difference=float(abs(fp32.astype(float)-logits).max()),float32_vs_float64_argmax_differences=int(np.sum(fp32.argmax(axis=1)!=logits.argmax(axis=1))),synthetic_labels_known=False,stress='20 steps, step.05/20, radius.05 normalized feature space; categorical unchanged; coordinate-box plus source integer lattice, not validated joint real-customer constraints; first16 audit inputs',torch_version=torch.__version__,tenseal_version=ts.__version__))
 save(OUT/'TRAINING_COMPLETE.json',dict(wall_seconds=time.monotonic()-begin,epochs=100,history=history,development_accuracy_float32=float(np.mean(fp32[16:].argmax(axis=1)==ytest[48:176])),development_accuracy_float64=float(np.mean(logits[16:].argmax(axis=1)==ytest[48:176])),algebra_check_scope='selection16 and development128 only; audit correctness evaluated after configuration freeze',epoch_selection=False))
 print('training_complete',tau,'algebra',diff,flush=True)
def native(stage):
 torch.set_num_threads(4);torch.set_num_interop_threads(1);m,_=setup_model();m.load_state_dict(torch.load(OUT/'public_procedure_weights.pt',map_location='cpu'));m.eval()
 env=selected_source('base_ts.py',['BankMLP_TS'],dict(ts=ts));enc_model=env['BankMLP_TS'](m)
 file={'selection':'configuration_selection','audit':'independent_evaluation','stress':'stress'}[stage];rows=list(csv.DictReader((OUT/(file+'.csv')).open()));X=np.array([[float(r[f'x_{j}']) for j in range(20)] for r in rows]);z=double_logits(m,X)
 with torch.no_grad():fp32=m(torch.Tensor(X)).numpy()
 for k in [1,2,3]:
  out=OUT/'native'/stage/f'key_{k}.json';assert not out.exists();s=time.monotonic();context=ts.context(ts.SCHEME_TYPE.CKKS,poly_modulus_degree=8192,coeff_mod_bit_sizes=[31,26,26,26,26,26,26,31],n_threads=4);context.global_scale=2**26;context.generate_galois_keys();setup=time.monotonic()-s;records=[]
  parameters=public_context_parameters(context)
  if parameters['status']=='READ':
   assert parameters['parameters_set'] and parameters['poly_modulus_degree']==8192
   assert '128' in parameters['security_qualifier']
   assert [v.bit_length() for v in parameters['key_moduli']]==[31,26,26,26,26,26,26,31]
   assert parameters['data_moduli']==parameters['key_moduli'][:-1]
  for i,(row,x) in enumerate(zip(rows,X)):
   begin=time.monotonic();s=begin;encrypted=ts.ckks_vector(context,x.tolist());enc=time.monotonic()-s;s=time.monotonic();result=enc_model(encrypted);he=time.monotonic()-s;s=time.monotonic();a=result.decrypt();dec=time.monotonic()-s;label=int(row['original_label']);p=int(np.argmax(z[i]));pa=int(np.argmax(a));po=int(np.argmax(fp32[i]));original_rounded_label=int(np.asarray(a,dtype=np.float32).argmax())
   records.append(dict(row_id=int(row['row_id']),source_row_id=int(row['source_row_id']),original_label=label if stage!='stress' else None,parent_label_metadata=label,original_float32_logits=fp32[i].astype(float).tolist(),common_float64_logits=z[i].tolist(),ckks_logits=a,original_prediction=po,common_prediction=p,ckks_prediction=pa,original_HEDiff_rounded_prediction=original_rounded_label,all_common_disagreement=p!=pa,hediff_eq2_original=(po==label and po!=original_rounded_label) if stage!='stress' else None,hediff_eq2_common=(p==label and p!=pa) if stage!='stress' else None,encode_encrypt_ms=enc*1000,he_ms=he*1000,decrypt_decode_ms=dec*1000,pdf_inference_ms=(enc+he+dec)*1000,wall_ms=(time.monotonic()-begin)*1000))
  save(out,dict(stage=stage,key=k,config=dict(log_n=13,prime_bits=[31,26,26,26,26,26,26,31],scale_bits=26,source='official Start bank branch, unchanged',security='TenSEAL/SEAL default128 admission; QP218 exceeds our frozen V2N13 limit214; do not claim identical security policy',input_ciphertexts_per_input=1,input_values=20,output_values=2,packing='official CKKSVector.mm; Galois keys and packed vector path; not common Lattigo schedule'),runtime_parameters=parameters,setup_ms=setup*1000,records=records,script_sha256=sha(__file__),model_sha256=sha(OUT/'model.json')));print('native',stage,'key',k,'complete',flush=True)
 save(OUT/'native'/stage/'result.json',dict(keys=3,inputs=len(rows),original_ckks_setting_preserved=True))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['train','selection','audit','stress']);a=p.parse_args()
 if a.mode=='train':train()
 else:native(a.mode)
