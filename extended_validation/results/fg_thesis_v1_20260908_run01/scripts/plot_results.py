"""Scientific descriptive plot from frozen audit and paired-time tables only."""
import csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import run as r
DOC=r.ROOT/'docs/research/fg_thesis_v1_20260908'
def main():
    assert not (DOC/'CPRIME_COST_AND_SLACK.png').exists() and not (DOC/'CPRIME_COST_AND_SLACK.svg').exists(),'preserve completed figures'
    audit=list(csv.DictReader(open(DOC/'AUDIT_METRICS.csv')));timing=list(csv.DictReader(open(DOC/'TIMING_SUMMARY.csv')))
    fr=r.read(r.RUN/'FROZEN_SELECTIONS.json')['records']
    cases=[('hediff_bank','Bank','reserved684'),('spambase__mlp_square_linear_score__split0_seed0','Spambase MLP','existing_audit'),('fashion_seed0','Fashion seed0','existing_audit')]
    plt.rcParams.update({'font.size':11})
    fig,axes=plt.subplots(1,3,figsize=(13.5,4.4),layout='constrained');records=[]
    styles={'C':('o','#333333'),'Cprime':('s','#005b96'),'B30':('^','#bb5500'),'B30slack':('D','#559944')}
    for ax,(cid,title,stage) in zip(axes,cases):
        domains={(int(x['applicable_inputs']),int(x['unique_inputs'])) for x in audit if x['case']==cid and x['stage']==stage and x['setting']=='base'}
        assert len(domains)==1
        applicable,total=next(iter(domains))
        members=[x for x in fr if x['case']==cid and x['phase']=='B' and x['literal_id']]
        refs={x['literal_id'] for x in members if x['role']=='C'}
        if len(refs)!=1:ax.text(.5,.5,'No unique C reference',ha='center');continue
        ref=next(iter(refs));lids=sorted({x['literal_id'] for x in members})
        for lid in lids:
            role=sorted({x['role'] for x in members if x['literal_id']==lid});rr=[x for x in audit if x['case']==cid and x['literal_id']==lid and x['stage']==stage and x['setting']=='base']
            if len(rr)!=1 or rr[0]['complete_key_count']!='True':continue
            y=float(rr[0]['max_budget_usage']);assert y>0
            if lid==ref:x=lo=hi=1.
            else:
                tt=[v for v in timing if v['case']==cid and v['reference_literal']==ref and v['comparator_literal']==lid]
                if len(tt)!=1:continue
                x=float(tt[0]['equal_key_geomean_ratio']);lo=float(tt[0]['key_ratio_min']);hi=float(tt[0]['key_ratio_max'])
            primary='Cprime' if 'Cprime' in role else role[0];marker,color=styles[primary]
            label='/'.join(z.replace('Cprime',"C'").replace('B30slack','B30+slack') for z in role)
            ax.errorbar(x,y,xerr=[[max(0,x-lo)],[max(0,hi-x)]],fmt=marker,color=color,capsize=3,markersize=7,label=label)
            records.append({'case':cid,'stage':stage,'literal_id':lid,'roles':role,'relative_paired_time':x,'key_min':lo,'key_max':hi,'max_budget_usage':y,'unique_inputs':int(rr[0]['unique_inputs']),'applicable_inputs':int(rr[0]['applicable_inputs'])})
        ax.axhline(1,color='#bb3333',ls='--',lw=1);ax.axvline(1,color='#aaaaaa',lw=.7)
        ax.set_yscale('log');ax.set_title(title+f'\nApplicable: {applicable}/{total}',fontsize=11);ax.set_xlabel('Paired inference time / C');ax.grid(axis='y',alpha=.2);ax.legend(fontsize=9,loc='best')
    axes[0].set_ylabel('Maximum observed error / decision budget')
    fig.savefig(DOC/'CPRIME_COST_AND_SLACK.png',dpi=300);fig.savefig(DOC/'CPRIME_COST_AND_SLACK.svg')
    r.write(r.RUN/'FIGURE_DATA.json',{'points':records,'caption':'Descriptive local comparison. X is equal-key-block geometric paired time ratio; horizontal bars are range of three key-block ratios, not confidence intervals. Y is worst observed budget usage within base rho0.5/delta0.001 applicable inputs only; titles show applicable/total; Bank684/Spambase256/Fashion1000. C normalized to1 does not imply zero timing variance. Aliases share audit. No risk guarantee.'})
    plt.close(fig)
if __name__=='__main__':main()
