"""Pre-open fixed metrics: strict sufficient condition; key events and inputs separate."""
import numpy as np

def arrays(records):
    tab = 'PlainY' in records[0]
    p = np.asarray([[r['PlainY']] if tab else r['plaintext_logits'] for r in records],float)
    a = np.asarray([[r['CKKSY']] if tab else r['ckks_logits'] for r in records],float)
    ids = np.asarray([str(r['RowID'] if tab else r['sample_id']) for r in records])
    y = np.asarray([r['Label'] if tab else r['label'] for r in records])
    assert p.shape == a.shape and np.isfinite(p).all() and np.isfinite(a).all()
    e=abs(a-p)
    if tab:
        pred=(p[:,0]>=.5).astype(int); encrypted=(a[:,0]>=.5).astype(int)
        gap=abs(p[:,0]-.5)
        ratio=np.divide(e[:,0],gap,out=np.full(len(records),np.inf),where=gap>0)
    else:
        pred=p.argmax(1);encrypted=a.argmax(1);ii=np.arange(len(records))
        dist=p[ii,pred,None]-p;cost=e[ii,pred,None]+e
        mask=np.arange(p.shape[1])[None,:]!=pred[:,None]
        gap=np.where(mask,dist,np.inf).min(1)
        ratios=np.divide(cost,dist,out=np.full_like(cost,np.inf),where=dist>0)
        ratios[~mask]=0;ratio=ratios.max(1)
    return {'ids':ids,'margin':gap,'ratio':ratio,'flip':pred!=encrypted,'maxabs':e.max(1),
            'squared_error_sum':(e*e).sum(1),'output_dim':p.shape[1], 'correct':pred==y,'p':p,'a':a}

def summarize(key_records,rho=.5,delta=.001,synthetic=False):
    aa=[arrays(r) for r in key_records if r]
    if not aa:return {'key_contexts':0,'execution_complete':False}
    v={k:np.concatenate([a[k] for a in aa]) for k in ['ids','margin','ratio','flip','maxabs','squared_error_sum','correct']}
    ids=v['ids'];g=v['margin'];ratio=v['ratio'];flip=v['flip'];app=g>delta;common=g>.01
    bad=(v['maxabs']>=rho*g) if aa[0]['output_dim']==1 else (ratio>=rho)
    # A sufficient condition cannot hold at a decision flip. This tests the reducer, not future risk.
    assert not np.any(flip & app & ~bad)
    margins={str(i):float(m) for i,m in zip(ids,g)}
    for a in aa:
        assert len(set(a['ids']))==len(a['ids'])
        for i,m in zip(a['ids'],a['margin']):assert margins[str(i)]==float(m)
    ret={'unique_inputs':len(set(ids)),'key_contexts':len(aa),'input_key_observations':len(ids),
         'applicable_inputs':len(set(ids[app])),'boundary_inputs':len(set(ids[~app])),
         'applicable_observations':int(app.sum()),'all_flip_events':int(flip.sum()),
         'applicable_flip_events':int((flip&app).sum()),'boundary_flip_events':int((flip&~app).sum()),
         'applicable_error_events':int((bad&app).sum()),'boundary_error_events':int((bad&~app).sum()),
         'same_decision_error_events':int((~flip&bad&app).sum()),
         'applicable_unique_flips':len(set(ids[flip&app])),'applicable_unique_errors':len(set(ids[bad&app])),
         'common_inputs':len(set(ids[common])),'common_flip_events':int((flip&common).sum()),
         'common_error_events':int((bad&common).sum()),'max_abs':float(v['maxabs'].max()),
         'rmse':float(np.sqrt(v['squared_error_sum'].sum()/(len(ids)*aa[0]['output_dim']))),
         'min_margin':min(margins.values()),'median_margin':float(np.median(list(margins.values()))),
         'plaintext_accuracy':None if synthetic else float(v['correct'].mean()),'rho':rho,'delta':delta}
    usage=ratio[app]/rho
    ret.update(max_budget_usage=float(usage.max()) if len(usage) else None,
               p95_budget_usage=float(np.quantile(usage,.95)) if len(usage) else None,
               applicable_fraction=ret['applicable_inputs']/ret['unique_inputs'])
    return ret

def selftest():
    # Equality to budget is a violation even if decision is unchanged; ties excluded at delta=0.
    exact=[{'RowID':0,'PlainY':.75,'CKKSY':.625,'Label':1}]
    eq=summarize([exact],rho=.5,delta=0)
    assert eq['applicable_error_events']==1 and eq['all_flip_events']==0 and eq['max_budget_usage']==1
    rr=[{'RowID':1,'PlainY':.6,'CKKSY':.55,'Label':1},{'RowID':2,'PlainY':.5,'CKKSY':.49,'Label':1}]
    a=arrays(rr);assert a['margin'][1]==0 and a['flip'][1]
    r=summarize([rr],rho=.4,delta=0);assert r['applicable_error_events']==1 and r['boundary_flip_events']==1
    rr=[{'sample_id':'a','plaintext_logits':[2.,1.,0.],'ckks_logits':[1.9,1.,.1],'label':0}]
    r=summarize([rr]);assert r['all_flip_events']==0 and r['applicable_error_events']==0
    rr[0]['ckks_logits']=[.8,1.,0.];r=summarize([rr]);assert r['all_flip_events']==1 and r['applicable_error_events']==1
    assert summarize([rr],synthetic=True)['plaintext_accuracy'] is None
    return True

if __name__=='__main__':print(selftest())
