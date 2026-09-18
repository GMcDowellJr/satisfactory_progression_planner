import fs from 'node:fs';
import { ProductionSolver } from './src/production-solver';
const files = ['gameData_canonical.json','gameData_s125.json','gameData_p20.json','gameData_combined.json'];
const labels = ['baseline 1.0/1.0','inputs 1.25x','power 2.0x','combined 1.25/2.0'];
const cases: [string,[string,number][]][] = [
  ['Iron Plate 20', [['Desc_IronPlate_C',20]]],
  ['Smart Plating 1', [['Desc_SpaceElevatorPart_1_C',1]]],
  ['SP1+VF6+AW1.2', [['Desc_SpaceElevatorPart_1_C',1],['Desc_SpaceElevatorPart_2_C',6],['Desc_SpaceElevatorPart_3_C',1.2]]],
];
(async()=>{
for (const [cn,tg] of cases) {
  for (let i=0;i<files.length;i++){
    const gd = JSON.parse(fs.readFileSync(files[i],'utf8'));
    const ALL=Object.keys(gd.recipes);
    const RES=Object.keys(gd.resources).map(k=>({key:k,itemKey:k,value:'0',weight:'1',unlimited:true}));
    const o:any={key:'c',productionItems:tg.map(([itemKey,v],j)=>({key:`t${j}`,itemKey,mode:'per-minute',value:String(v)})),
      inputItems:[],inputResources:RES,allowHandGatheredItems:false,
      weightingOptions:{resources:'1',power:'1',complexity:'0',buildings:'1'},
      allowedRecipes:Object.fromEntries(ALL.map(k=>[k,!gd.recipes[k].isAlternate]))};
    const res=await new ProductionSolver(o,gd).exec();
    if(res.error){console.log(`FAIL ${cn} ${labels[i]} ${res.error.message}`);continue;}
    const r=res.report!;
    const raws=Object.entries(r.totalRawResources).map(([k,v])=>`${k}=${(v as number).toFixed(2)}`).sort().join(' ');
    console.log(`${cn.padEnd(16)} ${labels[i].padEnd(18)} power=${r.powerUsageEstimate.total.toFixed(2).padStart(9)}MW raw=[${raws}]`);
  }
  console.log('');
}
})();
