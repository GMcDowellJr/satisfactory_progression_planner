import json,math,numpy as np
from scipy import sparse
from scipy.sparse.csgraph import dijkstra,minimum_spanning_tree
OUT=__import__('pathlib').Path(__file__).resolve().parent/'out'; OUT.mkdir(exist_ok=True); SP=str(OUT)+'/'
Z=np.load(SP+'Z.npy'); BL=np.load(SP+'blocked.npy'); R=json.load(open(SP+'slope_reach.json')); BR=json.load(open(SP+'bridges.json'))
n=R['n'];B=R['grid_m'];E0,N0=R['east0'],R['north0']; idx=np.arange(n*n).reshape(n,n)
w=lambda i:[round(E0+(i%n)*B),round(N0-(i//n)*B)]
cell=lambda e,nn:int(round((N0-nn)/B))*n+int(round((e-E0)/B))
out={}
for cls in ('2:8','4:8'):
  lim=int(cls[0])/8; rows=[];cols=[];ws=[]
  for dr,dc in ((0,1),(1,0),(1,1),(1,-1)):
    c0=slice(0,n-dc) if dc>=0 else slice(1,n); c1=slice(dc,n) if dc>=0 else slice(0,n-1)
    a=idx[0:n-dr,c0].ravel(); b=idx[dr:n,c1].ravel(); L=B*math.hypot(dr,dc)
    g=np.abs(Z[dr:n,c1]-Z[0:n-dr,c0]).ravel()/L
    ok=~BL[0:n-dr,c0].ravel()&~BL[dr:n,c1].ravel()&np.isfinite(g)&(g<=lim)
    rows.append(a[ok]);cols.append(b[ok]);ws.append(np.full(ok.sum(),L))
  spans=[]; seen=set()
  for k,v in BR.items():
    if not k.startswith(cls): continue
    for s in v['top']:
      i,j=cell(*s['from_core']),cell(*s['to'])
      # hubs sharing a cut-off component (W1, W2) list the same spans; added twice, the COO -> CSR
      # sum made a span cost 3x its length instead of 1.5x (review finding on PR #8, 2026-10-25)
      if (min(i,j),max(i,j)) in seen: continue
      seen.add((min(i,j),max(i,j))); spans.append((i,j,s))
      rows.append(np.array([i]));cols.append(np.array([j]));ws.append(np.array([s['span_m']*1.5]))  # spans cost 1.5x length
  G=sparse.coo_matrix((np.concatenate(ws),(np.concatenate(rows),np.concatenate(cols))),shape=(n*n,n*n)).tocsr(); G=G.maximum(G.T)
  snaps=R['classes'][cls]['snaps']; keys=list(snaps); src=[snaps[k]['node'] for k in keys]
  D,P=dijkstra(G,indices=src,return_predecessors=True)
  M=np.array([[D[i,src[j]] for j in range(len(keys))] for i in range(len(keys))])
  T=minimum_spanning_tree(np.where(np.isfinite(M),M,0)).tocoo()
  links=[]
  for i,j,dist in zip(T.row,T.col,T.data):
    path=[];u=src[j]
    while u!=src[i] and u>=0: path.append(int(u)); u=P[i,u]
    path.append(src[i]); path=path[::-1]
    used=[s for a,b,s in spans if any((path[k],path[k+1]) in ((a,b),(b,a)) for k in range(len(path)-1))]
    z=[float(Z[p//n,p%n]) for p in path]
    links.append(dict(a=keys[i],b=keys[j],km=round(float(dist)/1000,2),spans=used,pts=[w(p) for p in path[::3]]+[w(path[-1])],zmin=round(min(z)),zmax=round(max(z))))
  unreached=[keys[j] for j in range(len(keys)) if not np.isfinite(M[0,j])]
  out[cls]=dict(links=links,unreached=unreached)
  print(cls,'unreached',unreached); [print(' ',l['a'],l['b'],l['km'],'km','spans',[(s['span_m'],s['max_pillar_m']) for s in l['spans']]) for l in links]
json.dump(out,open(SP+'network.json','w',newline='\n'))
