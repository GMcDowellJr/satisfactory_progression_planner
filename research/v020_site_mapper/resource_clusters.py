"""Resource-first opportunity discovery. Coordinates are repository east/north meters.

A resource neighborhood is a candidate opportunity, not a verified build site,
resource allocation, water supply, or traversable connection.
"""
from __future__ import annotations
import argparse,csv,json,math
from collections import Counter,defaultdict
from pathlib import Path

INCLUDE={'iron','copper','limestone','coal','caterium','crude_oil','bauxite','raw_quartz','sulfur','sam','nitrogen_gas'}
PURITY={'impure':0.5,'normal':1.,'pure':2.}


def read_csv(path):
 with open(path,encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def resources_from_repo(repo,assignments_override=None):
 repo=Path(repo)
 socket_path=repo/'planning_data/world/canonical/world_resource_sockets.csv'
 assignment_path=Path(assignments_override) if assignments_override else repo/'planning_data/world/configurations/default_502094/resource_assignments.csv'
 if not socket_path.exists() and (repo/'source_snapshot/world/world_resource_sockets.csv').exists():
  socket_path=repo/'source_snapshot/world/world_resource_sockets.csv'
  if assignments_override is None:
   assignment_path=repo/'source_snapshot/world/resource_assignments_default_502094.csv'
 sockets={s['socket_id']:s for s in read_csv(socket_path)}
 seen=set();out=[]
 for a in read_csv(assignment_path):
  id=a['socket_id'];resource=a['resource_id'].lower();purity=a['purity'].lower()
  if id in seen:raise ValueError(f'Duplicate resource assignment: {id}')
  seen.add(id)
  if resource not in INCLUDE or purity not in PURITY or id not in sockets:continue
  s=sockets[id]
  out.append({'socket_id':id,'resource':resource,'purity':purity,'east_m':float(s['east_m']),
              'north_m':float(s['north_m']),'elevation_m':float(s['elevation_m'])})
 return out


def distance(a,b):return math.hypot(a['east_m']-b['east_m'],a['north_m']-b['north_m'])


def discover(resources,radius=350.,min_nodes=2,max_candidates=1000,overlap_threshold=.78):
 """Generate socket-centered neighborhoods, deduplicate near-identical sets.

 No greedy worldwide spacing: dense complementary neighborhoods must survive.
 All ties and overlapping opportunities are retained unless largely same sockets.
 """
 if radius<=0 or not 0<=overlap_threshold<=1:raise ValueError('Invalid clustering parameters')
 candidates=[]
 for origin in sorted(resources,key=lambda r:r['socket_id']):
  nearby=[r for r in resources if distance(origin,r)<=radius+1e-8]
  if len(nearby)<min_nodes:continue
  ids=frozenset(r['socket_id'] for r in nearby)
  families=Counter(r['resource'] for r in nearby)
  weighted=defaultdict(float)
  for r in nearby:weighted[r['resource']]+=PURITY[r['purity']]
  # Prioritize complementarity without collapsing sites to an arbitrary winning role.
  diversity=len(families)
  seed={'seed_socket_id':origin['socket_id'],'east_m':origin['east_m'],'north_m':origin['north_m'],
        'socket_ids':sorted(ids),'socket_set':ids,'node_count':len(nearby),'resource_family_count':diversity,
        'resource_counts':dict(sorted(families.items())),
        'purity_equivalents':dict(sorted(weighted.items())),
        'resources':[{'id':r['socket_id'],'type':r['resource'],'purity':r['purity'],
                      'east_m':r['east_m'],'north_m':r['north_m'],'elevation_m':r['elevation_m'],
                      'horizontal_distance_m':round(distance(origin,r),1)} for r in sorted(nearby,key=lambda r:(distance(origin,r),r['socket_id']))]}
  candidates.append(seed)
 # Discover distinctive mixed resource clusters first, not largest buildable rectangles.
 candidates.sort(key=lambda c:(-c['resource_family_count'],-c['node_count'],-sum(c['purity_equivalents'].values()),c['seed_socket_id']))
 selected=[]
 for c in candidates:
  if any(len(c['socket_set']&k['socket_set'])/len(c['socket_set']|k['socket_set'])>=overlap_threshold
         and distance(c,k)<=radius/2 for k in selected):continue
  selected.append(c)
  if len(selected)>=max_candidates:break
 for i,c in enumerate(selected,1):
  c['id']=f'RC{i:03d}'
  del c['socket_set']
  c['game_x_m']=round(c['east_m'],2);c['game_y_m']=round(-c['north_m'],2)
  c['description']='; '.join(f'{k}: {v}' for k,v in c['resource_counts'].items())
  c['water_access']='unverified (water wells excluded; open water not evaluated)'
  c['buildability']='unverified (resource cluster is not a factory footprint)'
  c['terrain_access']='unverified (horizontal proximity only)'
 return selected


def nearest_to_point(clusters,x,y):
 return sorted(clusters,key=lambda c:math.hypot(c['game_x_m']-x,c['game_y_m']-y))


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--repo',required=True,type=Path);p.add_argument('--resource-assignments',type=Path)
 p.add_argument('--radius',type=float,default=350);p.add_argument('--max-candidates',type=int,default=1000)
 p.add_argument('--output',type=Path,required=True);p.add_argument('--csv',type=Path)
 args=p.parse_args()
 resources=resources_from_repo(args.repo,args.resource_assignments)
 clusters=discover(resources,radius=args.radius,max_candidates=args.max_candidates)
 result={'schema_version':'0.4.0-resource-first','game_build':'502094',
         'coordinate_policy':'repository north_m = -game Y(m); game X=east_m',
         'settings':{'neighborhood_radius_m':args.radius,'max_candidates':args.max_candidates,'overlap_threshold':0.78},
         'limitations':['Horizontal neighborhood: no terrain traversability or elevation connection proven',
         'Candidate center is a resource node, NOT a verified building platform',
         'Overlapping neighborhoods do not allocate exclusive nodes','Water/shoreline access not evaluated',
         'Corridor/rail/tractor/truck feasibility is separate','Candidate cap truncates catalog; tune settings as required'],
         'clusters':clusters}
 args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',newline='\n')
 if args.csv:
  args.csv.parent.mkdir(parents=True,exist_ok=True)
  with open(args.csv,'w',newline='',encoding='utf-8') as f:
   writer=csv.DictWriter(f,fieldnames=['id','game_x_m','game_y_m','node_count','resource_family_count','description','seed_socket_id'],lineterminator='\n')
   writer.writeheader();writer.writerows({k:c[k] for k in writer.fieldnames} for c in clusters)
 print(f'{len(clusters)} resource-neighborhood candidates; nearest to (1227,-268):')
 for c in nearest_to_point(clusters,1227,-268)[:4]:print(c['id'],c['game_x_m'],c['game_y_m'],c['description'])

if __name__=='__main__':main()
