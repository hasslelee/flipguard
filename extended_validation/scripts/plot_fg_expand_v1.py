#!/usr/bin/env python3
"""Standalone research figure; no new experiments or manuscript edits."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/research/fg_expand_v1_20260905'


def main():
    s=json.loads((OUT/'summary.json').read_text());assert s['completed_cases']==s['planned_cases']==4
    cs=s['cases'];x=np.arange(len(cs));labels=[('HTRU2' if c['dataset']=='htru2' else 'Spambase')+'\n'+('Linear + cubic' if c['model_id']=='linear_poly3' else 'Square MLP-4') for c in cs]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
    fig,axs=plt.subplots(2,2,figsize=(11.7,8.0),layout='constrained')
    blue='#2563a6';orange='#c86225'
    ax=axs[0,0];coverage=[100*c['audit_roles']['direct']['coverage'] for c in cs]
    ax.bar(x,coverage,color=blue,width=.55);ax.set_ylim(0,113);ax.set_ylabel('Applicable inputs (%)');ax.set_title('(a) Separate-input coverage',loc='left')
    for i,c in enumerate(cs):
        a=c['audit_roles']['direct'];ax.text(i,coverage[i]+2,f"{a['eligible']}/{a['inputs']}",ha='center')
    ax=axs[0,1];w=.32
    for shift,arm,label,color in [(-w/2,'initial_criteria_off','Initial',orange),(w/2,'direct','Selected',blue)]:
        y=[c['audit_roles'][arm]['protected_unique_bad_inputs'] for c in cs];ax.bar(x+shift,y,width=w,color=color,label=label)
        for i,v in enumerate(y):ax.annotate(str(v),(i+shift,v),xytext=(0,3),textcoords='offset points',ha='center',fontsize=8)
    ax.set_ylabel('Applicable inputs violating either condition');ax.set_title('(b) Unique input counts across 3 keys',loc='left');ax.margins(y=.17);ax.legend(frameon=False)
    ax=axs[1,0]
    for shift,key,label,color in [(-w/2,'direct_selection_total_ms','Bounded selection',blue),(w/2,'finite_search_total_ms','Whole finite set',orange)]:
        y=[c['selection_cost_ms'][key]/1000 for c in cs];ax.bar(x+shift,y,width=w,label=label,color=color)
        for i,v in enumerate(y):ax.annotate(f'{v:.1f}',(i+shift,v),xytext=(0,3),textcoords='offset points',ha='center',fontsize=8)
    ax.set_ylabel('Selection/search wall time (s)');ax.set_title('(c) Setup and evaluation included',loc='left');ax.margins(y=.4);ax.legend(frameon=False)
    ax=axs[1,1];y=[c['paired_geometric_ratios']['finite_fastest_safe_over_direct'] for c in cs]
    ax.axhline(1,color='#64748b',lw=1,ls='--');ax.scatter(x,y,color=blue,zorder=3,s=40)
    for i,v in enumerate(y):ax.annotate(f'{v:.6f}',(i,v),xytext=(5 if i==0 else 0,-14 if i==0 else 8),textcoords='offset points',ha='left' if i==0 else 'center',fontsize=8)
    extent=max(abs(v-1) for v in y);extent=max(extent*1.8,.002);ax.set_ylim(1-extent,1+extent)
    ax.set_ylabel('Fastest acceptable / selected time');ax.set_title('(d) Paired inference; setup excluded',loc='left');ax.ticklabel_format(useOffset=False)
    for ax in axs.flat:ax.set_xticks(x,labels);ax.set_axisbelow(True);ax.grid(axis='y',alpha=.18)
    fig.suptitle('Existing configuration selection on four new dataset-model cases',fontsize=13)
    fig.supxlabel('One split and training seed per case; exploratory. Boundary inputs are excluded from (b).\nRatio near 1 is not an equivalence guarantee. Legacy results are not pooled.',fontsize=9)
    dst=OUT/'figures';dst.mkdir(exist_ok=True)
    for ext in ['pdf','png','svg']:fig.savefig(dst/('selection_and_cost.'+ext),dpi=220)
    plt.close(fig)
    print('Saved standalone PDF, PNG and SVG figure.')


if __name__=='__main__':main()
