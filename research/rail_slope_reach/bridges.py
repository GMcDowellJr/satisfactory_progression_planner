"""Valley spans: straight constant-grade decks joining two no-bridge components.
Feasible at a class if |dz|/d <= limit and the deck stays within 2 m of or above the
8 m ground everywhere along it (no cut or tunnel). Ranked by length + 2 x max pillar."""
import json,math,numpy as np
from scipy.spatial import cKDTree
from scipy import ndimage as ndi
OUT=__import__('pathlib').Path(__file__).resolve().parent/'out'; OUT.mkdir(exist_ok=True); SP=str(OUT)+'/'
Z=np.load(SP+'Z.npy'); BL=np.load(SP+'blocked.npy'); R=json.load(open(SP+'slope_reach.json')); n=R['n']; B=R['grid_m']
E0,N0=R['east0'],R['north0']; LMAX=600; K=80
Zf=np.where(np.isfinite(Z),Z,-1e9)
def boundary(lab2,c):
  m=lab2==c; return np.argwhere(m & ~ndi.binary_erosion(m,np.ones((3,3))))
w=lambda rc:[round(E0+rc[1]*B),round(N0-rc[0]*B)]
res={}
for cls in ('2','4'):
  lim=int(cls)/8; lab2=np.load(SP+f'lab_{cls}.npy').reshape(n,n); S=R['classes'][f'{cls}:8']['snaps']
  core=S['C1']['comp']; done={}
  A=boundary(lab2,core); ta=cKDTree(A)
  for hub,v in S.items():
    comp=v['comp']
    if comp==core: continue
    if comp in done: res[f'{cls}:8 {hub}']=done[comp]; continue
    Bc=boundary(lab2,comp); tb=cKDTree(Bc)
    pairs=tb.sparse_distance_matrix(ta,LMAX/B,output_type='ndarray')
    pi=pairs['i']; pj=pairs['j']; L=pairs['v']*B
    pa=A[pj]; pb=Bc[pi]
    za=Z[pa[:,0],pa[:,1]]; zb=Z[pb[:,0],pb[:,1]]
    ok=(L>=16)&(np.abs(zb-za)/np.maximum(L,1)<=lim)
    pa,pb,za,zb,L=pa[ok],pb[ok],za[ok],zb[ok],L[ok]
    t=np.linspace(0,1,K)[None,:]; clear=np.zeros(len(L),bool); pillar=np.zeros(len(L)); wet=np.zeros(len(L))
    for s0 in range(0,len(L),60000):
      sl=slice(s0,s0+60000)
      rr=np.rint(pa[sl,:1]+(pb[sl,:1]-pa[sl,:1])*t).astype(np.int32); cc=np.rint(pa[sl,1:]+(pb[sl,1:]-pa[sl,1:])*t).astype(np.int32)
      g=Zf[rr,cc]; deck=za[sl,None]+(zb[sl]-za[sl])[:,None]*t
      clear[sl]=~np.any(g>deck+2.0,axis=1)
      pillar[sl]=np.max(deck-np.where(g>-1e8,g,deck),axis=1); wet[sl]=BL[rr,cc].sum(axis=1)
    idx=np.flatnonzero(clear)
    order=idx[np.argsort(L[idx]+2*pillar[idx])]
    top=[];seen=[]
    for i in order:
      e=w(pa[i]); f=w(pb[i])
      if any(math.dist(e,s)<150 for s in seen): continue
      seen.append(e); top.append(dict(span_m=round(float(L[i])),max_pillar_m=round(float(pillar[i])),over_blocked_m=int(wet[i]*L[i]/K),from_core=e,to=f,dz=round(float(zb[i]-za[i]))))
      if len(top)==3: break
    out=dict(cls=f'{cls}:8',hub=hub,component_km2=v['comp_km2'],pairs_tested=int(ok.sum()),feasible=int(clear.sum()),top=top)
    done[comp]=out; res[f'{cls}:8 {hub}']=out
    print(cls+':8',hub,out['pairs_tested'],out['feasible'],top)
json.dump(res,open(SP+'bridges.json','w',newline='\n'),indent=1)
