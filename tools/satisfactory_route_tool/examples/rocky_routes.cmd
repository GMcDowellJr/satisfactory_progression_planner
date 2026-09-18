@echo off
REM Example commands after installing the package.

set PLANNER=C:\path\satisfactory_planning_data_v1_14.zip
set ROADS=C:\path\spatial\scim_roads\scim_road_prior_5m.npz

REM A -> C / Steel, tractor
satisfactory-route solve ^
  --planner "%PLANNER%" ^
  --roads "%ROADS%" ^
  --origin -2650.2936 370.0145 ^
  --destination -1373.5683 412.7417 ^
  --mode tractor ^
  --bridge-policy forbid ^
  --out data\local\routes\a_to_c

REM A -> D / Oil, truck
satisfactory-route solve ^
  --planner "%PLANNER%" ^
  --roads "%ROADS%" ^
  --origin -2650.2936 370.0145 ^
  --destination -2540.9607 -740.4848 ^
  --mode truck ^
  --bridge-policy forbid ^
  --out data\local\routes\a_to_d
