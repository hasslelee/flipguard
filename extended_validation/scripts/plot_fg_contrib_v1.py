#!/usr/bin/env python3
"""Figures from independently reconstructed results, never from selection minima."""
import collections,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1];DOC=ROOT/'docs/research/fg_contrib_v1_20260906'
def main():
 r=json.loads((DOC/'RESULTS.json').read_text());spec=json.loads((ROOT/'protocols/FG_CONTRIB_V1.json').read_text());ids=[c['case_id'] for c in spec['cases']];labels=['Spambase linear','HTRU2 linear','Spambase square MLP','HTRU2 square MLP','Fashion seed 0','Fashion seed 1','Fashion seed 2'];scales=spec['diagnostic']['scales']
 matrix=np.full((7,len(scales)),np.nan);notes={};legend=['Neither condition','Numeric only','Decision + margin only','Both conditions']
 for d in r['diagnostic']:
  if d['diagnostic_kind']!='diagnostic':continue
  i=ids.index(d['case_id']);j=scales.index(d['scale'])
  if d['executed']:
   m=d['metrics']
   if m['key_contexts']==3:matrix[i,j]=int(m['numeric_max_pass'])+2*int(m['proposal_pass']);notes[(i,j)]=str(m['all_flip_events'])
  elif d['generation_failure']:notes[(i,j)]='GEN'
 fig,ax=plt.subplots(figsize=(9,4.7),layout='constrained');cmap=matplotlib.colors.ListedColormap(['#b5b8bd','#e8b05d','#7099cd','#76b0a0']);im=ax.imshow(np.ma.masked_invalid(matrix),vmin=-.5,vmax=3.5,cmap=cmap,aspect='auto')
 ax.set_xticks(range(len(scales)),scales);ax.set_yticks(range(7),labels);ax.set_xlabel('Explicit independent scale bits (fixed Q guard = 0)');ax.set_title('Independent candidate diagnostics on selection inputs')
 for i in range(7):
  for j in range(len(scales)):ax.text(j,i,notes.get((i,j),'NA'),ha='center',va='center',fontsize=11)
 cb=fig.colorbar(im,ax=ax,ticks=range(4),shrink=.85);cb.ax.set_yticklabels(legend,fontsize=8)
 fig.text(.01,-.035,'Numbers: all-input disagreement events over 3 fresh keys. Decision/margin: common V_delta; numeric: all outputs.\nGEN: parameter generation rejected. NA: unmeasured/failed execution. Key repeats are not independent environments.',fontsize=8)
 for ext in ['png','pdf']:fig.savefig(DOC/f'candidate_condition_map.{ext}',dpi=200,bbox_inches='tight')
 plt.close(fig)
 selected=collections.defaultdict(list)
 for s in r['selection_runs']:
  if s['role'] in ['A30','B30','C']:selected[(s['case_id'],s['role'])].append(s)
 fields=['analysis_ms','parameter_ms','key_setup_ms','encode_encrypt_ms','he_ms','decrypt_decode_ms'];colors=['#6d83a9','#bbbbbb','#a3b5c8','#ddad6a','#719f94','#baa2bc'];names=['Analysis/synthesis','Parameters','Key setup','Encode/encrypt','HE evaluation','Decrypt/decode']
 fig,axes=plt.subplots(2,4,figsize=(12,6.5),layout='constrained');axes=axes.flatten()
 for i,cid in enumerate(ids):
  ax=axes[i];bottom=np.zeros(3)
  for field,color,name in zip(fields,colors,names):
   vals=np.array([np.mean([s.get(field,0) for s in selected[(cid,role)]])/1000 if selected[(cid,role)] else np.nan for role in ['A30','B30','C']]);ax.bar(range(3),vals,bottom=bottom,color=color,label=name);bottom+=vals
  total=np.array([np.mean([s['command_wall_ms'] for s in selected[(cid,role)]])/1000 if selected[(cid,role)] else np.nan for role in ['A30','B30','C']]);other=total-bottom
  assert np.all(other[np.isfinite(other)]>=-1e-3),'overlapping cost accounting'
  ax.bar(range(3),other,bottom=bottom,color='#e2e2e2',label='Checks, evidence and other wall');ax.set_xticks(range(3),['A30','B30','C']);ax.set_title(labels[i],fontsize=10);ax.set_ylabel('Actual selection wall (s)');ax.grid(axis='y',alpha=.2)
 axes[-1].axis('off');handles,legend_labels=axes[0].get_legend_handles_labels();axes[-1].legend(handles,legend_labels,loc='center',frameon=False,fontsize=8)
 fig.suptitle('Actual bounded selection cost: mean of both fresh-key blocks',fontsize=12)
 fig.text(.01,-.025,'All attempts and post-hoc checks included. Two key blocks are exploratory repetitions, not independent environments.',fontsize=8)
 for ext in ['png','pdf']:fig.savefig(DOC/f'selection_cost_decomposition.{ext}',dpi=200,bbox_inches='tight')
 plt.close(fig)
 # This uses candidate diagnostic costs, not the fresh paired final timing.
 # Keep each case separate because tabular and packed-image input units differ.
 fig,axes=plt.subplots(2,4,figsize=(12,6.5),layout='constrained');axes=axes.flatten()
 for i,cid in enumerate(ids):
  ax=axes[i];tau=spec['cases'][i]['thresholds']['max_abs']
  for d in r['diagnostic']:
   if d['case_id']!=cid or not d['executed'] or d['diagnostic_kind']!='diagnostic':continue
   m=d['metrics'];x=m['cost']['pdf_inference_ms']/m['key_contexts']/1000;y=m['max_abs'];colour='#38826f' if m['proposal_pass'] else '#b25043'
   ax.scatter(x,y,color=colour,s=28);ax.annotate('S'+str(d['scale']),xy=(x,y),xytext=(3,2),textcoords='offset points',fontsize=7)
  for s in r['selection_runs']:
   if s['case_id']!=cid or s['role']!='C' or not s['literal_id']:continue
   prefix=str(Path(s['raw']).parent)+'/'
   mm=[m for m in r['trial_metrics'] if m['raw'].startswith(prefix) and m['literal_id']==s['literal_id']]
   assert len(mm)==1,'selected C candidate must resolve to one actual trial'
   m=mm[0];ax.scatter(m['cost']['pdf_inference_ms']/m['key_contexts']/1000,m['max_abs'],marker='*',s=75,color='#435f9b',zorder=4)
  ax.axhline(tau,color='#555555',linestyle='--',linewidth=.8);ax.axhline(4*tau,color='#888888',linestyle=':',linewidth=.8)
  ax.set_yscale('log');ax.margins(x=.16);ax.set_title(labels[i],fontsize=10);ax.set_xlabel('Mean PDF time per key (s)',fontsize=8);ax.set_ylabel('Maximum absolute output error',fontsize=8);ax.grid(alpha=.15)
 axes[-1].axis('off')
 from matplotlib.lines import Line2D
 keys=[Line2D([],[],marker='o',linestyle='',color='#38826f',label='Diagnostic: decision condition passes'),Line2D([],[],marker='o',linestyle='',color='#b25043',label='Diagnostic: decision condition fails'),Line2D([],[],marker='*',linestyle='',color='#435f9b',label='C selected: each 3-key block'),Line2D([],[],linestyle='--',color='#555555',label='Main numerical tolerance'),Line2D([],[],linestyle=':',color='#888888',label='Predeclared 4x tolerance')]
 axes[-1].legend(handles=keys,loc='center',frameon=False,fontsize=8)
 fig.suptitle('Candidate error and measured cost on selection inputs',fontsize=12)
 fig.text(.01,-.025,'Fixed inputs per case: 32 tabular / 500 Fashion. Three keys per point. Rejected generations omitted.\nThese diagnostic times do not replace the separate post-selection paired latency experiment.',fontsize=8)
 for ext in ['png','pdf']:fig.savefig(DOC/f'candidate_error_cost.{ext}',dpi=200,bbox_inches='tight')
 plt.close(fig)
if __name__=='__main__':main()
