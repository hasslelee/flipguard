#!/usr/bin/env python3
"""Reconstruct existing paired costs and plain algebra only. No native execution."""
import collections,math,json
import numpy as np
from analyze_fg_cause_v1 import ROOT,OLD,RUN,BANK,DOC,NEW,BIND,read,rows,table,emit

def main():
 selections=rows(OLD/'SELECTION_RUNS.csv');blocks=rows(OLD/'TIMING_BLOCKS.csv');ext=read(OLD/'EXTERNAL_RESULTS.json');ca=read(DOC/'ANALYSIS.json');out=[];checks=[]
 jobs=[]
 for case in ca['internal']['logic']:
  cid=case['case_id'];b=next(r for r in selections if r['case_id']==cid and r['role']=='B30' and r['block']=='0');cc=next(r for r in selections if r['case_id']==cid and r['role']=='C' and r['block']=='0');want=[r for r in blocks if r['case_id']==cid and r['comparator']==b['literal_id'] and r['reference']==cc['literal_id']];assert len(want)==3;jobs.append((cid,want))
 jobs.append(('hediff_bank',ext['timing']))
 for cid,bs in jobs:
  accum=collections.defaultdict(list);ratios=[];params={};paths=[];count=0
  for item in bs:
   j=read(item['raw']);paths.append(item['raw']);pair=collections.defaultdict(dict)
   for arm in j['arms']:
    params[arm['id']]={k:arm[k] for k in ['log_n','log_q','log_p','log_default_scale']}
    accum[(arm['id'],'setup_ms')].append(arm.get('setup_ms',arm.get('setup_keygen_ms')))
   actual=collections.defaultdict(list)
   for r in j['records']:
    enc=r['encode_encrypt_ms'];he=r.get('eval_only_ms',r.get('evaluation_only_ms'));dec=r['decrypt_decode_ms'];pdf=enc+he+dec;aid=r['arm_id'];index=(r['measurement_run'],r.get('row_index',0));assert aid not in pair[index];pair[index][aid]=pdf;count+=1
    for k,v in dict(encode_encrypt_ms=enc,he_ms=he,decrypt_decode_ms=dec,pdf_ms=pdf,native_ms=r['total_ms']).items():actual[(aid,k)].append(v)
   for k,v in actual.items():accum[k].append(float(np.mean(v)))
   ratio=math.exp(np.mean([math.log(v['comparator']/v['reference_C']) for v in pair.values()]));recorded=float(item['comparator_over_C_pdf_geomean']);assert math.isclose(ratio,recorded,rel_tol=1e-10);ratios.append(ratio)
  rec=dict(case_id=cid,key_blocks=3,unit=bs[0]['unit'],selected_inputs=int(bs[0]['selected_inputs']),raw_measurements=count,paired_B_over_C_geomean=float(math.exp(np.mean(np.log(ratios)))),key_ratios=ratios,source=paths,key_setup_included_in_pdf=False,network=None,queue=None)
  for aid,label in [('reference_C','C'),('comparator','B30')]:
   par=params[aid];rec[label+'_parameters']=par;rec[label+'_qp']=sum(par['log_q'])+sum(par['log_p']);rec[label+'_RNS_words_input_degree1']=(1<<par['log_n'])*len(par['log_q'])*2
   for k in ['setup_ms','encode_encrypt_ms','he_ms','decrypt_decode_ms','pdf_ms','native_ms']:rec[label+'_'+k]=float(np.mean(accum[(aid,k)]))
  rec['same_structural_tier']=(params['reference_C']['log_n']==params['comparator']['log_n'] and len(params['reference_C']['log_q'])==len(params['comparator']['log_q']) and len(params['reference_C']['log_p'])==len(params['comparator']['log_p']))
  out.append(rec)
 table('COST_CAUSES.csv',out)
 obs=rows(DOC/'BANK_CLASS_ERRORS.csv');selalt=[]
 for role in ['A','B','C']:
  result=read(BANK/'selection'/role/'result.json');sel=[r for r in obs if r['stage']=='selection' and r['method']==role];costs=[]
  for n in (1,2,3):
   j=read(BANK/'selection'/role/'trial_1'/f'key_{n}.json');s=j['summary'];costs.append(s['encode_encrypt_ms']+s['evaluation_only_ms']+s['decrypt_decode_ms'])
  selalt.append(dict(role=role,candidate=result['selected']['id'],parameters=result['selected']['parameters'],encrypted_candidates=result['actual_encrypted_candidates'],selection_wall_ms=result['wall_ms'],analysis_ms=result['analysis_ms'],selection_pdf_ms_per_key_batch=float(np.mean(costs)),max_usage=max(float(r['max_usage']) for r in sel),max_abs=max(float(r['max_abs']) for r in sel),all_proposal_pass=not any(r['violation']=='True' or r['flip']=='True' for r in sel),scope='selection16 only; independent random keys per role; no stress winner used'))
 table('BANK_SELECTION_ALTERNATIVES.csv',selalt)
 original=read(BANK/'planning/plan.json');actual=read(BANK/'selection/C/analysis.json')['plan']
 for k in ['calibration','multiclass_decision','deployment']:
  a=dict(original['contract'][k]);b=dict(actual['contract'][k]);a.pop('calibration_scope',None);b.pop('calibration_scope',None);assert a==b
 assert original['initial_candidates'][0]['parameters']==actual['initial_candidates'][0]['parameters']
 checks.append(dict(check='external preflight versus actual C selection synthesis',result='same numerical contract and initial parameters; actual contract role/digest differs',actual_source=str((BANK/'selection/C/analysis.json').relative_to(ROOT)),actual_contract_digest=actual['contract_digest']))
 model=read(BANK/'model.json');V=np.array(model['original_w2']);cos=np.dot(V[0],V[1])/(np.linalg.norm(V[0])*np.linalg.norm(V[1]));n2=max(np.sum(abs(V),axis=1));policy=[];chosen=rows(DOC/'BANK_PLAINTEXT_SELECTIONS.csv')
 for name in ['original_first16','uniform_hash16','development_quartile4x4']:
  ss=[r for r in chosen if r['policy']==name];m=min(float(r['margin']) for r in ss if r['applicable']=='True');H=max(float(r['shifted_hidden_maxabs']) for r in ss);agg=512+n2+n2*2*H*40;budget=m*.25;unit=budget/agg;p=math.ceil(-math.log2(unit));policy.append(dict(policy=name,protected_min_margin=m,per_output_initial_budget=budget,max_shifted_hidden=H,aggregate_sensitivity_formula=agg,unit_budget=unit,analysis_precision_bits=p,analysis_scale_floor_guard=max(18,p+3),backend_validated=False,encrypted_evaluated=False,scope='plaintext arithmetic prediction only, no candidate synthesis/prime generation/C invocation'))
 table('BANK_POLICY_ANALYSIS_ONLY.csv',policy)
 overlap=set(r['source_row_id'] for r in chosen if r['policy']=='uniform_hash16')&set(r['source_row_id'] for r in chosen if r['policy']=='development_quartile4x4')
 checks.append(dict(check='uniform versus quartile plaintext choices',common_inputs=len(overlap),different_each=16-len(overlap),same_min_margin=policy[1]['protected_min_margin']==policy[2]['protected_min_margin'],same_initial_plain_estimate=policy[1]['analysis_scale_floor_guard']==policy[2]['analysis_scale_floor_guard']))
 emit(DOC/'SUPPLEMENT.json',dict(cost_rows=len(out),existing_timing_jobs=sum(len(bs) for _,bs in jobs),checks=checks,bank_output_weight_cosine=float(cos),bank_output_weight_sum_l1=float(np.sum(abs(V[0]+V[1]))),bank_output_weight_difference_l1=float(np.sum(abs(V[0]-V[1]))),interpretation='opposing output weights are compatible with opposing final errors; encrypted intermediate errors were not recorded, so causal layer attribution is unknown',proposal='review existing inactive same-tier precision policy; not implemented/activated',policy_estimates=policy))
 emit(NEW/'SUPPLEMENT_READ_BINDINGS.json',dict(files=BIND))
 print(json.dumps(dict(costs=[{k:r[k] for k in ['case_id','paired_B_over_C_geomean','C_pdf_ms','B30_pdf_ms']} for r in out],checks=checks,plaintext_policy=policy),indent=2))
if __name__=='__main__':main()
