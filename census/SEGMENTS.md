# Every published segment, checked

`scrollscout check-segment` on all 81 segments in the open-data bucket that have a tifxyz
mesh traced on an 8.6–9.4 µm scan with a published surface prediction (12 points each). 45 of 81 likely follow their sheet.

Not checked: 46 segments of PHerc0500P2 (2.215 µm scan), because the score was validated on 8.64 µm and 9.36 µm scans only.

A segment *likely follows the sheet* when its median point scores above the clean threshold (0.63).
This rule called all 20 of the team's segments that the First Letters survey judged by eye correctly;
on other scrolls it is a prediction, not a measurement. *No papyrus* counts points whose
surroundings show no papyrus in the CT (the segment leaves the scroll or the scan there).

| scroll | segments | likely follow the sheet | likely cut across layers |
|---|---:|---:|---:|
| PHerc0139 | 38 | 35 | 3 |
| PHerc0800 | 6 | 6 | 0 |
| PHerc0814 | 19 | 1 | 18 |
| PHerc0841 | 3 | 0 | 3 |
| PHerc1447 | 15 | 3 | 12 |

## PHerc0139

| segment | verdict | median score | points clean | no papyrus | survey (by eye) |
|---|---|---:|---:|---:|---|
| `20260302000001-w050_2026030220` | follows the sheet | +1.06 | 83% | 0 |  |
| `20260127000000-w057_2026012713` | follows the sheet | +1.05 | 67% | 0 |  |
| `20260115000001-w056_2026011514` | follows the sheet | +1.04 | 75% | 0 |  |
| `20250108000001-w026_2025010854` | follows the sheet | +1.02 | 67% | 0 |  |
| `20260306000000-w038_2026030608` | follows the sheet | +1.02 | 75% | 0 |  |
| `20260316000000-w036_2026031607` | follows the sheet | +1.00 | 67% | 0 |  |
| `20260310000000-w037_2026031015` | follows the sheet | +0.98 | 67% | 0 |  |
| `20260206000000-w042_2026020613` | follows the sheet | +0.95 | 58% | 0 |  |
| `20260311000000-w023_202603112281` | follows the sheet | +0.95 | 58% | 0 |  |
| `20250108000000-w025_2025010863` | follows the sheet | +0.91 | 58% | 0 |  |
| `20260112000000-w043_2026011217` | follows the sheet | +0.91 | 67% | 0 |  |
| `20250108000003-w028_2025010836` | follows the sheet | +0.90 | 67% | 0 |  |
| `20260215000000-w024_2026021572` | follows the sheet | +0.89 | 58% | 0 |  |
| `20251226000000-w055_2025122611` | follows the sheet | +0.89 | 58% | 0 |  |
| `20260306000001-w051_2026030600` | follows the sheet | +0.89 | 58% | 0 |  |
| `20260318000000-w049_20260318` | follows the sheet | +0.88 | 75% | 0 |  |
| `20260227000000-w052_2026022705` | follows the sheet | +0.87 | 58% | 0 |  |
| `20260317000000-w035_2026031718` | follows the sheet | +0.87 | 67% | 0 |  |
| `20260325000000-w046_20260325` | follows the sheet | +0.87 | 67% | 0 |  |
| `20260126000000-w045_2026012619` | follows the sheet | +0.86 | 67% | 0 |  |
| `20250108000004-w029_2025010827` | follows the sheet | +0.86 | 67% | 0 |  |
| `20250108000002-w027_2025010845` | follows the sheet | +0.85 | 67% | 0 |  |
| `20250223000000-w059_2025022312` | follows the sheet | +0.85 | 58% | 0 |  |
| `20260219000001-w048_2026021912` | follows the sheet | +0.83 | 75% | 0 |  |
| `20260302000000-w039_2026030210` | follows the sheet | +0.81 | 64% | 1 |  |
| `20260210000000-w058_2026021020` | follows the sheet | +0.80 | 58% | 0 |  |
| `20260206000001-w047_2026020613` | follows the sheet | +0.80 | 67% | 0 |  |
| `20260203000000-w032_2026020303` | follows the sheet | +0.80 | 67% | 0 |  |
| `20260219000000-w033_2026021913` | follows the sheet | +0.79 | 58% | 0 |  |
| `20250831000000-w040_2025083102` | follows the sheet | +0.79 | 67% | 0 |  |
| `20250108000005-w030_2025010818` | follows the sheet | +0.78 | 67% | 0 |  |
| `20260130000000-w031_2026013019` | follows the sheet | +0.78 | 67% | 0 |  |
| `20260303000000-w034_2026030317` | follows the sheet | +0.75 | 50% | 0 |  |
| `20260115000000-w044_2026011522` | follows the sheet | +0.72 | 50% | 0 |  |
| `20260108000000-w041_2026010816` | follows the sheet | +0.72 | 58% | 0 |  |
| `20260220000000-w053_2026022021` | cuts across layers | +0.62 | 50% | 0 |  |
| `20260206000002-w054_2026020617` | cuts across layers | +0.54 | 42% | 0 |  |
| `20260422000000-title_2026042222_zmid_flatboi` | cuts across layers | +0.54 | 33% | 0 |  |

## PHerc0800

| segment | verdict | median score | points clean | no papyrus | survey (by eye) |
|---|---|---:|---:|---:|---|
| `20251028222030-auto_grown_20251028222030940` | follows the sheet | +1.18 | 92% | 0 | follows the sheet (fiber crosshatch visible) |
| `20251028220955-auto_grown_20251028220955262` | follows the sheet | +1.18 | 92% | 0 | follows the sheet (fiber crosshatch visible) |
| `20251028220042-auto_grown_20251028220042762` | follows the sheet | +1.17 | 100% | 0 | follows the sheet (fiber crosshatch visible) |
| `20251028213516-auto_grown_20251028213516907` | follows the sheet | +1.17 | 100% | 0 | follows the sheet (fiber crosshatch visible) |
| `20251028225813-auto_grown_20251028225813045` | follows the sheet | +1.13 | 100% | 0 | follows the sheet (fiber crosshatch visible) |
| `20251029010146-auto_grown_20251029010146642` | follows the sheet | +1.13 | 100% | 0 | follows the sheet (fiber crosshatch visible) |

## PHerc0814

| segment | verdict | median score | points clean | no papyrus | survey (by eye) |
|---|---|---:|---:|---:|---|
| `20260225160055-auto_grown_20260225160055913` | follows the sheet | +0.64 | 50% | 0 |  |
| `20260226123353-auto_grown_20260226123353106` | cuts across layers | +0.50 | 42% | 0 |  |
| `20250928235954-auto_grown_20250928235953722_copy` | cuts across layers | +0.47 | 42% | 0 |  |
| `20260226110425-auto_grown_20260226110425097_abf` | cuts across layers | +0.41 | 42% | 0 |  |
| `20260226000000-46527_2um_try2` | cuts across layers | +0.34 | 25% | 0 |  |
| `20260226121302-auto_grown_20260226121302716_abf` | cuts across layers | +0.07 | 25% | 0 |  |
| `20260226113324-auto_grown_20260226113324624_abf` | cuts across layers | +0.05 | 25% | 0 |  |
| `20250925161630-auto_grown_20250925161630635` | cuts across layers | -0.04 | 25% | 0 |  |
| `20250926165636-auto_trace_20250926165636789` | cuts across layers | -0.26 | 8% | 1 |  |
| `20250930083742-auto_grown_20250930083742882` | cuts across layers | -0.26 | 17% | 0 |  |
| `20250928235953-auto_grown_20250928235953722` | cuts across layers | -0.27 | 8% | 0 |  |
| `20250926051122-auto_grown_20250926051122829` | cuts across layers | -0.27 | 8% | 0 |  |
| `20250925222237-auto_grown_20250925222237459` | cuts across layers | -0.30 | 0% | 0 |  |
| `20250925212701-auto_grown_20250925212701145` | cuts across layers | -0.31 | 8% | 0 |  |
| `20251001060526-auto_grown_20251001060526760` | cuts across layers | -0.36 | 0% | 0 |  |
| `20250929040153-auto_grown_20250929040153260` | cuts across layers | -0.45 | 0% | 0 |  |
| `20250926203608-auto_grown_20250926203608932` | cuts across layers | -0.54 | 0% | 0 |  |
| `20250925182632-auto_grown_20250925182632715` | cuts across layers | -0.60 | 17% | 0 |  |
| `20250925204843-auto_grown_20250925204843950` | cuts across layers | -0.75 | 8% | 0 |  |

## PHerc0841

| segment | verdict | median score | points clean | no papyrus | survey (by eye) |
|---|---|---:|---:|---:|---|
| `20260220214732-auto_grown_20260220144552896` | cuts across layers | -0.01 | 25% | 0 |  |
| `20260221022814-auto_grown_20260220174252405` | cuts across layers | -0.14 | 8% | 0 |  |
| `20260220213127-w00` | cuts across layers | -0.23 | 17% | 0 |  |

## PHerc1447

| segment | verdict | median score | points clean | no papyrus | survey (by eye) |
|---|---|---:|---:|---:|---|
| `20250703025628-auto_grown_20250703025628283` | follows the sheet | +1.24 | 83% | 0 | follows the sheet |
| `20250703034159-auto_grown_20250703034159599` | follows the sheet | +1.14 | 83% | 0 | follows the sheet |
| `20250702235910-auto_grown_20250702235910292` | follows the sheet | +1.12 | 75% | 0 | follows the sheet |
| `20251105093211-z_dbg_gen_00320` | cuts across layers | +0.39 | 45% | 3 | on the sheet between many onion-ring spots, where the surfac |
| `20250502205333-auto_grown_20250502181030065` | cuts across layers | +0.12 | 33% | 0 | oblique striations: surface cuts across several layers |
| `20250502184658-auto_grown_20250502163923577` | cuts across layers | -0.05 | 11% | 6 | oblique striations: surface cuts across several layers |
| `20250502182456-auto_grown_20250502161202782` | cuts across layers | -0.20 | 30% | 6 | oblique striations: surface cuts across several layers |
| `20250502183421-auto_grown_20250502161744358` | cuts across layers | -0.30 | 27% | 7 | oblique striations: surface cuts across several layers |
| `20250502180748-auto_grown_20250502160748721` | cuts across layers | -0.33 | 20% | 6 | oblique striations: surface cuts across several layers |
| `20250502182142-auto_grown_20250502161324419` | cuts across layers | -0.80 | 27% | 4 | oblique striations: surface cuts across several layers |
| `20250502184845-auto_grown_20250502164121265` | cuts across layers | -0.90 | 11% | 4 | oblique striations: surface cuts across several layers |
| `20250502183138-auto_grown_20250502162038685` | cuts across layers | -0.94 | 40% | 3 | oblique striations: surface cuts across several layers |
| `20250502185519-auto_grown_20250502164303733` | cuts across layers | -1.38 | 22% | 6 | oblique striations: surface cuts across several layers |
| `20250502184201-auto_grown_20250502163549332` | cuts across layers | -1.38 | 20% | 5 | oblique striations: surface cuts across several layers |
| `20250502180708-auto_grown_20250502160708188` | cuts across layers | -1.65 | 11% | 7 | oblique striations: surface cuts across several layers |
