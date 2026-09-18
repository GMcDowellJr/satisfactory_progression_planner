import fs from 'node:fs';
import { ProductionSolver } from './src/production-solver';
import type { GameData } from './src/gameData-types';
import type { FactoryOptions } from './src/production-types';

const dataFile = process.argv[2] ?? 'gameData_canonical.json';
const gameData: GameData = JSON.parse(fs.readFileSync(dataFile, 'utf8'));

const ALL = Object.keys(gameData.recipes);
const BASE = ALL.filter((k) => !gameData.recipes[k].isAlternate);
const sel = (keys: string[]) => Object.fromEntries(ALL.map((k) => [k, keys.includes(k)]));
const RESOURCES = Object.keys(gameData.resources).map((k) => ({
  key: k, itemKey: k, value: '0', weight: '1', unlimited: true,
}));
const W = { resources: '1', power: '1', complexity: '1', buildings: '1' };

function opts(targets: [string, number][], allowed: string[]): FactoryOptions {
  return {
    key: 'case',
    productionItems: targets.map(([itemKey, v], i) => ({ key: `t${i}`, itemKey, mode: 'per-minute', value: String(v) })),
    inputItems: [], inputResources: RESOURCES,
    allowHandGatheredItems: false, weightingOptions: W, allowedRecipes: sel(allowed),
  };
}

const byName = (n: string) => ALL.find((k) => gameData.recipes[k].name === n);
const stitched = byName('Alternate: Stitched Iron Plate');
const ALTS = ['Recipe_Alternate_Wire_1_C', 'Recipe_Alternate_IngotSteel_1_C', stitched].filter(Boolean) as string[];

const CASES: { id: string, targets: [string, number][], allowed: string[] }[] = [
  { id: '1  Iron Plate 20/min (base only)', targets: [['Desc_IronPlate_C', 20]], allowed: BASE },
  { id: '2  Reinforced Iron Plate 5/min (base only)', targets: [['Desc_IronPlateReinforced_C', 5]], allowed: BASE },
  { id: '3  Smart Plating 1/min (base only)', targets: [['Desc_SpaceElevatorPart_1_C', 1]], allowed: BASE },
  { id: '4  Versatile Framework 6/min (base only)', targets: [['Desc_SpaceElevatorPart_2_C', 6]], allowed: BASE },
  { id: '5  Automated Wiring 1.2/min (base only)', targets: [['Desc_SpaceElevatorPart_3_C', 1.2]], allowed: BASE },
  { id: '6  Multi-target SP1 + VF6 + AW1.2 (base only)', targets: [['Desc_SpaceElevatorPart_1_C', 1], ['Desc_SpaceElevatorPart_2_C', 6], ['Desc_SpaceElevatorPart_3_C', 1.2]], allowed: BASE },
  { id: '7  SP1 w/ explicit alternates (base + 3 alts)', targets: [['Desc_SpaceElevatorPart_1_C', 1]], allowed: [...BASE, ...ALTS] },
  { id: '8  SP1+VF6+AW1.2, ALL recipes (auto-optimize)', targets: [['Desc_SpaceElevatorPart_1_C', 1], ['Desc_SpaceElevatorPart_2_C', 6], ['Desc_SpaceElevatorPart_3_C', 1.2]], allowed: ALL },
  { id: '11 Plastic 100/min (multi-output/byproduct)', targets: [['Desc_Plastic_C', 100]], allowed: BASE },
  { id: '12 Nuclear Pasta 1/min (late game, ALL)', targets: [['Desc_SpaceElevatorPart_9_C', 1]], allowed: ALL },
  { id: '12b Ballistic Warp Drive 1/min (Phase 5, ALL)', targets: [['Desc_SpaceElevatorPart_11_C', 1]], allowed: ALL },
  { id: '12c AI Expansion Server 1/min (Phase 5, ALL)', targets: [['Desc_SpaceElevatorPart_12_C', 1]], allowed: ALL },
];

(async () => {
  console.log(`## data=${dataFile} recipes=${ALL.length} base=${BASE.length} alts=${ALL.length - BASE.length}`);
  for (const c of CASES) {
    const t0 = Date.now();
    try {
      const res = await new ProductionSolver(opts(c.targets, c.allowed), gameData).exec();
      if (res.error) { console.log(`FAIL  ${c.id} :: ${res.error.message}`); continue; }
      const r = res.report!;
      const nodes = Object.values(res.productionGraph!.nodes);
      const recipeNodes = nodes.filter((n) => n.type === 'RECIPE');
      const machines = Object.entries(r.buildingsUsed).map(([k, v]) => `${k}:${v.count}`).sort();
      const raws = Object.entries(r.totalRawResources).map(([k, v]) => `${k}=${(v as number).toFixed(2)}`).sort();
      console.log(`OK    ${c.id}`);
      console.log(`      ms=${Date.now() - t0} recipes=${recipeNodes.length} power=${r.powerUsageEstimate.total.toFixed(2)}MW machines=[${machines.join(' ')}]`);
      console.log(`      raw=[${raws.join(' ')}]`);
      console.log(`      fractional=${recipeNodes.slice(0, 3).map((n) => `${n.key}@${n.multiplier.toFixed(4)}`).join(' ')}`);
    } catch (e: any) {
      console.log(`THROW ${c.id} :: ${e.message}`);
    }
  }
})();
