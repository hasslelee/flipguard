"""Multiclass decisions depend on score differences, not common-mode error."""
import math
import numpy as np
from .decision import reference_decision


def pairwise_residuals(plaintext, decrypted_by_key):
    p=np.asarray(plaintext,dtype=float);z=np.asarray(decrypted_by_key,dtype=float)
    if p.ndim!=2 or p.shape[1]<2 or z.ndim!=3 or z.shape[1:]!=p.shape or z.shape[0]==0:
        raise ValueError('Expected K>=2 classes and aligned key,input,class arrays')
    if not np.isfinite(p).all() or not np.isfinite(z).all():raise ValueError('Nonfinite logits')
    error=z-p[None,:,:]
    residual=(error.max(axis=2)-error.min(axis=2)).max(axis=0)
    if not np.isfinite(residual).all():raise ValueError('Error range overflow')
    return residual


def difference_gate(decrypted_logits, pairwise_radius):
    z=np.asarray(decrypted_logits,dtype=float)
    top=reference_decision(z)
    if z.shape[1]<2:raise ValueError('Difference gate requires multiclass logits')
    q=float(pairwise_radius)
    if math.isnan(q) or q<0:raise ValueError('Invalid pairwise radius')
    if math.isinf(q):return np.full(len(z),-1,dtype=int)
    sorted_values=np.sort(z,axis=1)
    gap=sorted_values[:,-1]-sorted_values[:,-2]
    return np.where(gap>q,top,-1)
