#!/usr/bin/env python3
"""Read-only replay of source pixels, split roles, and batch membership.

Does not evaluate a model or inspect CKKS success when selecting inputs.
Official IDX files are deliberately local only. CI checks the committed input
manifest; this full provenance replay is run where those source files exist.
"""
import argparse, csv, gzip, hashlib, json, struct
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'results/fg_expand_v2_20260905_run01'
RAW=ROOT/'data/raw/fashion_mnist'

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    sources=read(RUN/'DATA_SOURCE.json')
    for name,meta in sources.items():
        payload=(RAW/name).read_bytes()
        assert hashlib.md5(payload).hexdigest()==meta['md5']
        assert hashlib.sha256(payload).hexdigest()==meta['sha256']
        assert len(payload)==meta['bytes']
    arrays={}
    for partition,prefix,n in [('train','train',60000),('test','t10k',10000)]:
        xb=gzip.decompress((RAW/f'{prefix}-images-idx3-ubyte.gz').read_bytes())
        yb=gzip.decompress((RAW/f'{prefix}-labels-idx1-ubyte.gz').read_bytes())
        assert struct.unpack('>4I',xb[:16])==(2051,n,28,28)
        assert struct.unpack('>2I',yb[:8])==(2049,n)
        arrays[partition]=(np.frombuffer(xb[16:],np.uint8).reshape(n,784),np.frombuffer(yb[8:],np.uint8))
    split=read(RUN/'SPLIT.json');assert split['source_manifest_sha256']==sha(RUN/'DATA_SOURCE.json')
    expected={k:[] for k in ['training','development','selection']}
    for label in range(10):
        ids=[i for i,y in enumerate(arrays['train'][1]) if y==label]
        ids.sort(key=lambda i:hashlib.sha256(f'FG_EXPAND_V2|train|{label}|{i}'.encode()).digest())
        expected['development']+=ids[:500];expected['selection']+=ids[500:550];expected['training']+=ids[550:]
    for k,v in expected.items():assert sorted(v)==split[k]
    assert sorted(sum(expected.values(),[]))==list(range(60000))
    manifests=read(RUN/'INPUT_SHA256SUMS.json');layout=read(RUN/'BATCH_LAYOUT.json');test_seen=[];checks=[]
    for relative,h in manifests.items():
        p=RUN/relative;assert sha(p)==h
        rows=list(csv.DictReader(p.open()));assert len(rows)==500
        partition='test' if p.name.startswith('audit_') else 'train'
        xx,yy=arrays[partition];indices=[]
        for ordinal,row in enumerate(rows):
            idx=int(row['source_index']);indices.append(idx)
            assert int(row['row_id'])==ordinal and row['sample_id']==f'fashion/{partition}/{idx}'
            assert row['source_partition']==partition and int(row['label'])==int(yy[idx])
            assert row['role']==('locked_audit' if partition=='test' else 'configuration_validation')
            assert np.array_equal(np.array([int(row[f'pixel_{i:03d}']) for i in range(784)],dtype=int),xx[idx])
        counts=np.bincount(yy[indices],minlength=10).tolist();assert counts==[50]*10
        if partition=='test':
            b=int(p.stem.split('_')[1]);assert indices==layout['batches'][b]['official_test_indices']
            expected_ids=sorted(sum([np.flatnonzero(yy==c).tolist()[b*50:(b+1)*50] for c in range(10)],[]))
            assert indices==expected_ids;test_seen+=indices
        elif p.name=='selection.csv':assert indices==split['selection']
        else:
            assert p.name=='development_smoke.csv'
            expected_smoke=sorted(sum([[i for i in split['development'] if yy[i]==c][:50] for c in range(10)],[]))
            assert indices==expected_smoke
        checks.append(dict(path=relative,sha256=h,rows=len(rows),class_counts=counts,pixels_match_official_bytes=True))
    assert sorted(test_seen)==list(range(10000))
    result=dict(status='PASS',source_gzip_files=4,split_counts={k:len(v) for k,v in expected.items()},official_test_unique_inputs=len(test_seen),csv_rows_verified=sum(c['rows'] for c in checks),files=checks,model_evaluation_performed=False)
    path=RUN/'INPUT_PROVENANCE_VERIFICATION.json'
    if args.check:assert read(path)==result
    else:
        with path.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print('SOURCE_PIXELS_SPLITS_AND_ALL_TEST_BATCHES_PASS')
if __name__=='__main__':main()
