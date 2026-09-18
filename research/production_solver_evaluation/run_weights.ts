import fs from 'node:fs';
import { ProductionSolver } from './src/production-solver';
import type { GameData } from './src/gameData-types';
const gameData: GameData = JSON.parse(fs.readFileSync(process.argv[2] ?? 'gameData_canonical.json','utf8'));
const ALL = Object.keys(gameData.recipes);
const sel = (ks:string[]) => Object.fromEntries(ALL.map(k=>[k,ks.includes(k)]));
const RES = Object.keys(gameData.resources).map(k=>({key:k,itemKey:k,value:'0',weight:'1',unlimited:true}));
const targetsFor = (t:[string,number][]) => t.map(([itemKey,v],i)=>({key:`t${i}`,itemKey,mode:'per-minute',value:String(v)}));
const cases: [string,[string,number][]][] = [
  ['SP1+VF6+AW1.2', [['Desc_SpaceElevatorPart_1_C',1],['Desc_SpaceElevatorPart_2_C',6],['Desc_SpaceElevatorPart_3_C',1.2]]],
  ['Nuclear Pasta 1', [['Desc_SpaceElevatorPart_9_C',1]]],
  ['Ballistic Warp Drive 1', [['Desc_SpaceElevatorPart_11_C',1]]],
  ['AI Expansion Server 1', [['Desc_SpaceElevatorPart_12_C',1]]],
];
const weightSets: [string, any][] = [
  ['complexity=0 (LP only)', {resources:'1',power:'1',complexity:'0',buildings:'1'}],
  ['resources-only',         {resources:'1',power:'0',complexity:'0',buildings:'0'}],
  ['power-only',             {resources:'0',power:'1',complexity:'0',buildings:'0'}],
  ['buildings-only',         {resources:'0',power:'0',complexity:'0',buildings:'1'}],
  ['complexity=1 (MIP)',     {resources:'1',power:'1',complexity:'1',buildings:'1'}],
];
(async()=>{
for (const [cn,tg] of cases) for (const [wn,W] of weightSets) {
  const t0=Date.now();
  try {
    const res = await new ProductionSolver({key:'c',productionItems:targetsFor(tg) as any,inputItems:[],inputResources:RES,allowHandGatheredItems:false,weightingOptions:W,allowedRecipes:sel(ALL)} as any, gameData).exec();
    if (res.error) { console.log(`FAIL  ${cn.padEnd(24)} ${wn.padEnd(24)} ${res.error.message}`); continue; }
    const r=res.report!; const rn=Object.values(res.productionGraph!.nodes).filter(n=>n.type==='RECIPE');
    const raws=Object.entries(r.totalRawResources).reduce((a,[,v])=>a+(v as number),0);
    console.log(`OK    ${cn.padEnd(24)} ${wn.padEnd(24)} ms=${String(Date.now()-t0).padStart(5)} recipes=${String(rn.length).padStart(3)} power=${r.powerUsageEstimate.total.toFixed(0).padStart(7)}MW rawTotal=${raws.toFixed(1).padStart(9)}`);
  } catch(e:any){ console.log(`THROW ${cn.padEnd(24)} ${wn.padEnd(24)} ${e.message}`); }
}
})();
