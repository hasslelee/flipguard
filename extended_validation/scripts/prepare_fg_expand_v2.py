#!/usr/bin/env python3
"""Official byte-pinned Fashion-MNIST, disjoint train roles, 500-slot batches."""
import csv, gzip, hashlib, json, struct, urllib.request
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'results/fg_expand_v2_20260905_run01'
RAW = ROOT / 'data/raw/fashion_mnist'
FILES = {
    'train-images-idx3-ubyte.gz': '8d4fb7e6c68d591d4c3dfef9ec88bf0d',
    'train-labels-idx1-ubyte.gz': '25c81989df183df01b3e8a0aad5dffbe',
    't10k-images-idx3-ubyte.gz': 'bef4ecab320f06d8554ea6380940ec79',
    't10k-labels-idx1-ubyte.gz': 'bb300cfdad3c16e7a12a480ee83cd310',
}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, obj):
    with p.open('x') as f: json.dump(obj, f, indent=2); f.write('\n')
def main():
    manifest = {}
    for name, md5 in FILES.items():
        path = RAW / name
        url = 'https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/data/fashion/' + name
        if not path.exists():
            with urllib.request.urlopen(url, timeout=120) as r, path.open('xb') as w: w.write(r.read())
        assert hashlib.md5(path.read_bytes()).hexdigest() == md5, name
        manifest[name] = {'url': url, 'md5': md5, 'sha256': sha(path), 'bytes': path.stat().st_size}
    write(RUN/'DATA_SOURCE.json', manifest)
    def load(prefix, n):
        xb=gzip.decompress((RAW/f'{prefix}-images-idx3-ubyte.gz').read_bytes())
        yb=gzip.decompress((RAW/f'{prefix}-labels-idx1-ubyte.gz').read_bytes())
        assert struct.unpack('>IIII',xb[:16])==(2051,n,28,28)
        assert struct.unpack('>II',yb[:8])==(2049,n)
        x=np.frombuffer(xb[16:],dtype=np.uint8).reshape(n,784); y=np.frombuffer(yb[8:],dtype=np.uint8)
        assert len(y)==n and set(y)==set(range(10))
        return x,y
    x,y=load('train',60000); xt,yt=load('t10k',10000)
    roles={'training':[], 'development':[], 'selection':[]}
    for label in range(10):
        ids=np.flatnonzero(y==label).tolist()
        ids.sort(key=lambda i:hashlib.sha256(f'FG_EXPAND_V2|train|{label}|{i}'.encode()).digest())
        roles['development']+=ids[:500]; roles['selection']+=ids[500:550]; roles['training']+=ids[550:]
    roles={k:sorted(v) for k,v in roles.items()}
    assert len(set(sum(roles.values(),[])))==60000
    write(RUN/'SPLIT.json',{'source_manifest_sha256':sha(RUN/'DATA_SOURCE.json'), 'policy':'fashion_mnist_train_sha256_stratified_rank_v1',**roles})
    out=RUN/'inputs';out.mkdir()
    header=['row_id','sample_id','source_index','source_partition','role','label']+[f'pixel_{i:03d}' for i in range(784)]
    def emit(name,ids,xx,yy,partition,role):
        with (out/name).open('x',newline='') as f:
            w=csv.writer(f);w.writerow(header)
            for ri,i in enumerate(ids):w.writerow([ri,f'fashion/{partition}/{i}',i,partition,role,int(yy[i]),*xx[i].tolist()])
    emit('selection.csv',roles['selection'],x,y,'train','configuration_validation')
    # First 50 per class in the fixed development role; never test-derived.
    smoke=sorted(sum([[i for i in roles['development'] if y[i]==c][:50] for c in range(10)],[]))
    emit('development_smoke.csv',smoke,x,y,'train','configuration_validation')
    batches=[]
    for b in range(20):
        ids=sorted(sum([np.flatnonzero(yt==c).tolist()[50*b:50*(b+1)] for c in range(10)],[]))
        assert len(ids)==500
        emit(f'audit_{b:02d}.csv',ids,xt,yt,'test','locked_audit')
        batches.append({'batch_id':b,'official_test_indices':ids,'valid_slots':500,'file':f'inputs/audit_{b:02d}.csv'})
    assert len(set(sum([b['official_test_indices'] for b in batches],[])))==10000
    write(RUN/'BATCH_LAYOUT.json',{'proposal_before_main_lock':True,'selection_count':500,'test_count':10000,'layout':'784 feature ciphertexts, one sample per slot; zero padding to N/2; ten output ciphertexts','batches':batches})
    write(RUN/'INPUT_SHA256SUMS.json',{str(p.relative_to(RUN)):sha(p) for p in sorted(out.iterdir())})
    print(json.dumps({'train':len(roles['training']),'development':5000,'selection':500,'test_batches':20,'source_manifest_sha256':sha(RUN/'DATA_SOURCE.json')}))
if __name__=='__main__':main()
