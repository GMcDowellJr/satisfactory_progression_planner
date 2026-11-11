# Phase 5 walk-back, 1.0 standard (non-alternate) recipes, recalled from game knowledge.
# recipe: product -> (out_qty, {inputs}, {byproducts})
import numpy as np
from collections import defaultdict
R = {
 "Iron Ingot":(1,{"Iron Ore":1},{}),
 "Copper Ingot":(1,{"Copper Ore":1},{}),
 "Caterium Ingot":(1,{"Caterium Ore":3},{}),
 "Steel Ingot":(3,{"Iron Ore":3,"Coal":3},{}),
 "Iron Plate":(2,{"Iron Ingot":3},{}),
 "Iron Rod":(1,{"Iron Ingot":1},{}),
 "Screw":(4,{"Iron Rod":1},{}),
 "Wire":(2,{"Copper Ingot":1},{}),
 "Cable":(1,{"Wire":2},{}),
 "Copper Sheet":(1,{"Copper Ingot":2},{}),
 "Concrete":(1,{"Limestone":3},{}),
 "Quartz Crystal":(3,{"Raw Quartz":5},{}),
 "Silica":(5,{"Raw Quartz":3},{}),
 "Steel Beam":(1,{"Steel Ingot":4},{}),
 "Steel Pipe":(2,{"Steel Ingot":3},{}),
 "Reinforced Iron Plate":(1,{"Iron Plate":6,"Screw":12},{}),
 "Modular Frame":(2,{"Reinforced Iron Plate":3,"Iron Rod":12},{}),
 "Encased Industrial Beam":(1,{"Steel Beam":3,"Concrete":6},{}),
 "Heavy Modular Frame":(1,{"Modular Frame":5,"Steel Pipe":20,"Encased Industrial Beam":5,"Screw":120},{}),
 "Rotor":(1,{"Iron Rod":5,"Screw":25},{}),
 "Stator":(1,{"Steel Pipe":3,"Wire":8},{}),
 "Motor":(1,{"Rotor":2,"Stator":2},{}),
 "Quickwire":(5,{"Caterium Ingot":1},{}),
 "Plastic":(2,{"Crude Oil":3},{"Heavy Oil Residue":1}),
 "Rubber":(2,{"Crude Oil":3},{"Heavy Oil Residue":2}),
 "Circuit Board":(1,{"Copper Sheet":2,"Plastic":4},{}),
 "Computer":(1,{"Circuit Board":4,"Cable":8,"Plastic":16},{}),
 "AI Limiter":(1,{"Copper Sheet":5,"Quickwire":20},{}),
 "High-Speed Connector":(1,{"Quickwire":56,"Cable":10,"Circuit Board":1},{}),
 "Crystal Oscillator":(2,{"Quartz Crystal":36,"Cable":28,"Reinforced Iron Plate":5},{}),
 "Automated Wiring":(1,{"Stator":1,"Cable":20},{}),
 "Alumina Solution":(12,{"Bauxite":12,"Water":18},{"Silica":5}),
 "Aluminum Scrap":(6,{"Alumina Solution":4,"Coal":2},{"Water":2}),
 "Aluminum Ingot":(4,{"Aluminum Scrap":6,"Silica":5},{}),
 "Alclad Aluminum Sheet":(3,{"Aluminum Ingot":3,"Copper Ingot":1},{}),
 "Aluminum Casing":(2,{"Aluminum Ingot":3},{}),
 "Heat Sink":(1,{"Alclad Aluminum Sheet":5,"Copper Sheet":3},{}),
 "Cooling System":(1,{"Heat Sink":2,"Rubber":2,"Water":5,"Nitrogen Gas":25},{}),
 "Fused Modular Frame":(1,{"Heavy Modular Frame":1,"Aluminum Casing":50,"Nitrogen Gas":25},{}),
 "Radio Control Unit":(2,{"Aluminum Casing":32,"Crystal Oscillator":1,"Computer":2},{}),
 "Turbo Motor":(1,{"Cooling System":4,"Radio Control Unit":2,"Motor":4,"Rubber":24},{}),
 "Smart Plating":(1,{"Reinforced Iron Plate":1,"Rotor":1},{}),
 "Modular Engine":(1,{"Motor":2,"Rubber":15,"Smart Plating":2},{}),
 "Versatile Framework":(2,{"Modular Frame":1,"Steel Beam":12},{}),
 "Electromagnetic Control Rod":(2,{"Stator":3,"AI Limiter":2},{}),
 "Adaptive Control Unit":(1,{"Automated Wiring":5,"Circuit Board":5,"Heavy Modular Frame":1,"Computer":2},{}),
 "Supercomputer":(1,{"Computer":4,"AI Limiter":2,"High-Speed Connector":3,"Plastic":28},{}),
 "Assembly Director System":(1,{"Adaptive Control Unit":2,"Supercomputer":1},{}),
 "Magnetic Field Generator":(2,{"Versatile Framework":5,"Electromagnetic Control Rod":2},{}),
 "Thermal Propulsion Rocket":(2,{"Modular Engine":5,"Turbo Motor":2,"Cooling System":6,"Fused Modular Frame":2},{}),
 "Pressure Conversion Cube":(1,{"Fused Modular Frame":1,"Radio Control Unit":2},{}),
 "Copper Powder":(5,{"Copper Ingot":30},{}),
 "Nuclear Pasta":(1,{"Copper Powder":200,"Pressure Conversion Cube":1},{}),
 "Reanimated SAM":(1,{"SAM":4},{}),
 "Ficsite Ingot":(1,{"Reanimated SAM":2,"Aluminum Ingot":6},{}),
 "Ficsite Trigon":(3,{"Ficsite Ingot":1},{}),
 "Diamonds":(1,{"Coal":20},{}),
 "Time Crystal":(1,{"Diamonds":2},{}),
 "Dark Matter Residue":(10,{"Reanimated SAM":5},{}),
 "Dark Matter Crystal":(1,{"Diamonds":1,"Dark Matter Residue":5},{}),
 "Excited Photonic Matter":(10,{},{}),
 "Biochemical Sculptor":(4,{"Assembly Director System":1,"Ficsite Trigon":80,"Water":20},{}),
 "Superposition Oscillator":(1,{"Dark Matter Crystal":6,"Crystal Oscillator":1,"Alclad Aluminum Sheet":9,"Excited Photonic Matter":25},{"Dark Matter Residue":25}),
 "Neural-Quantum Processor":(1,{"Time Crystal":3,"Supercomputer":1,"Ficsite Trigon":15,"Excited Photonic Matter":25},{"Dark Matter Residue":25}),
 "AI Expansion Server":(1,{"Magnetic Field Generator":1,"Neural-Quantum Processor":1,"Superposition Oscillator":1,"Excited Photonic Matter":100},{"Dark Matter Residue":100}),
 "Singularity Cell":(10,{"Nuclear Pasta":1,"Dark Matter Crystal":20,"Iron Plate":100,"Concrete":200},{}),
 "Ballistic Warp Drive":(1,{"Thermal Propulsion Rocket":1,"Singularity Cell":5,"Superposition Oscillator":2,"Dark Matter Crystal":40},{}),
}
FINAL = ["Nuclear Pasta","Biochemical Sculptor","AI Expansion Server","Ballistic Warp Drive"]
items = list(R)
idx = {k:i for i,k in enumerate(items)}
n=len(items)
A=np.zeros((n,n))  # A[item, recipe] = net output per craft
for j,p in enumerate(items):
    o,ins,by = R[p]
    A[idx[p],j]+=o
    for k,v in list(ins.items())+[(k,-v) for k,v in by.items()]:
        if k in idx: A[idx[k],j]-=v
def solve(demand):
    d=np.zeros(n)
    for k,v in demand.items(): d[idx[k]]=v
    x=np.linalg.solve(A,d)  # crafts/min
    prod={items[j]:x[j]*R[items[j]][0] for j in range(n) if abs(x[j])>1e-12}
    raw=defaultdict(float); by=defaultdict(float)
    for j,p in enumerate(items):
        o,ins,bp=R[p]
        for k,v in ins.items():
            if k not in idx: raw[k]+=x[j]*v
        for k,v in bp.items():
            if k not in idx: raw[k]-=x[j]*v
    return prod,raw
import sys
if __name__=="__main__":
    for tag,dem in [("ALL",{f:1 for f in FINAL})]+[(f,{f:1}) for f in FINAL]:
        prod,raw=solve(dem)
        print("=====",tag)
        print("RAW:",{k:round(v,2) for k,v in sorted(raw.items(),key=lambda t:-t[1])})
    prod,raw=solve({f:1 for f in FINAL})
    print("===== ALL intermediates /min")
    for k,v in sorted(prod.items(),key=lambda t:-t[1]): print(f"{k:28s} {v:10.3f}")
