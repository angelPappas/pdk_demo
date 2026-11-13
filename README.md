# pdk_demo: a demo TFLN PDK

A small thin-film lithium niobate (TFLN) PDK in [GDSFactory](https://gdsfactory.github.io/gdsfactory/), built to show the full path from simulation to circuit model:

```
GDSFactory cells  ──►  Lumerical simulations  ──►  database/ (CML json + S-parameters)  ──►  INTERCONNECT library
   (pdk/)               (simulations/)                  (database/)                          (interconnect_interface/)
```

Each building block is drawn once in GDS, simulated in Lumerical (FDE, EME, FDTD), converted into a compact model, and compiled into an INTERCONNECT library with the CML Compiler. Circuits such as MZIs and rings can then be simulated from the simulated blocks and compared with measurements from the test die.

## Technology

x-cut LNOI, TE polarisation, light propagating along the crystal Y axis, C band.

| Layer | Material | Thickness |
|---|---|---|
| Substrate | Si | - |
| BOX | SiO2 | 4.7 µm |
| Lithium niobate | x-cut LiNbO3 | 0.6 µm (0.4 µm ridge, 0.2 µm slab) |
| Cladding | SiO2 | - |

Ridge waveguide, 1.0 µm wide at the base, 70° sidewalls. Simulated at 1550 nm: n_eff = 1.856, n_g = 2.255, D = -242 ps/(nm·km). Dimensions and all design parameters are in [`pdk/tfln/constants.csv`](pdk/tfln/constants.csv).

## Components in the PDK

| Component | GDS cell (`pdk/tfln/cells/`) | Ports | Key parameters (defaults) | Simulation | INTERCONNECT element (`database/`) | Status |
|---|---|---|---|---|---|---|
| Straight waveguide | `wg` cross-section + `gf.components.straight` | o1, o2 | width 1.0 µm | FDE: n_eff, n_g, D over wavelength and temperature | `wg_te_cband_ydir` (template `wg_strip_straight_parameterized`, 11 wavelengths × 2 temperatures) | Ready. Propagation loss (20 dB/m) and dn_eff/dT are assumed values |
| Sine S-bend | `bend_s` | o1, o2 | dy 1.3 µm, length 20 µm | Part of the coupler FDTD model | - | GDS only |
| 90° bend | `bend_90` (angle ±90) | o1, o2 | radius 50 µm | FDE bend sweep (`bend_fde.py`) + 3D FDTD of the full arc with a straight control (`bend90_fdtd.py`: R = 20, 30, 50 µm; net loss ≈ 0.02 dB, TE-like ≈ 0.14 dB at R = 50 µm) | CML template `wg_bend_90` (not built yet) | GDS done. A 180° turn of any length is two `bend_90` plus a straight |
| Directional coupler (2×2) | `directional_coupler` | o1, o2 (left), o3, o4 (right) | gap 0.4 µm, length 21 µm, port separation 4 µm | 3D FDTD, 4-port S-parameters, 1530-1570 nm | `dc_te_cband_ydir` (template `dc_strip_te_c`, `spar_fixed`) | Ready. 50:50 design |
| Taper | `taper` | o1 (narrow), o2 (wide) | 1 → 12 µm over 200 µm | EME, complex 2-port S-matrix, 1530-1570 nm | Inside the grating coupler element | Ready (as part of the grating coupler) |
| Grating coupler with its taper | `grating_coupler` | o1 (waveguide), fiber (marker) | period 0.945 µm, fill 0.6, 20 periods, 8° fibre | 3D FDTD power efficiency (0.365 at 1550 nm) cascaded with the EME taper | `gc_te_cband_ydir` (template `gc_strip_te_c`, `spar_fixed`): one 2-port element, opt_1 waveguide, opt_2 fibre | Ready. Grating phase and reflection are placeholders (0) until the FDTD run records them |
| Test die | `test_die` | - | 8 × 7.4 mm, 26 structures | - | - | Template. See below |

Not in the PDK yet: Euler bend, MMI, edge coupler, phase shifters (electro-optic, thermal), modulators, RF lines and pads.

## Test die

`test_die` places every block between grating-coupler pairs, so a single fibre-array scan characterises the die:

| Group | Structures | What it extracts |
|---|---|---|
| Reference and loss | GC-to-GC reference, straights of 0.5, 2.5 and 5 mm | Grating loss, propagation loss (cutback) |
| Tapers | 1 and 4 back-to-back taper pairs | Taper loss |
| S-bends | 2, 10 and 20 S-bends in series | S-bend loss |
| 180° turns | Serpentines of 2, 4 and 8 turns (each two `bend_90`) | Bend loss |
| Directional couplers | Lengths 10, 16, 21, 26 µm at gap 0.4 µm; gaps 0.3 and 0.5 µm at length 21 µm | Split ratio and excess loss versus wavelength |
| MZI | Two unbalanced MZIs (ΔL 300 and 600 µm) | Group index from the fringe period |
| Rings | Racetracks, gaps 0.3, 0.4, 0.5 µm | Group index, loss, coupling |
| EO, thermal, RF | Placeholders (metal boxes) | To be defined |

Write the GDS with `python -m pdk.make_test_die` (output: `gds/tfln_test_die.gds`).

## Repository layout

```
pdk/tfln/                  GDSFactory PDK: layers, cross-section, cells, constants.csv
pdk/make_test_die.py       writes gds/tfln_test_die.gds
simulations/               Lumerical scripts (FDE, EME, FDTD) and the converters to CML data
  wg_to_cml_json.py        waveguide model   -> wg_model/
  bend_fde.py              90° bend FDE sweep -> bend_model/
  dc_to_cml.py             coupler S-matrix  -> dc_model/
  gc_to_cml.py             taper + grating   -> gc_model/
database/                  CML source data per component (json + S-parameter file)
interconnect_interface/    builds the INTERCONNECT library from database/
```

## Quick start

```bash
uv sync                                   # Python >= 3.12, gdsfactory >= 9.51
python -c "from pdk.tfln.pdk import TFLN_PDK; import gdsfactory as gf; gf.get_component('directional_coupler').show()"
python -m pdk.make_test_die
```

## Building the INTERCONNECT library

Requires Lumerical v261 with the CML Compiler on Windows, and this repo run from WSL (the compiler works in `/mnt/c/pdk_work`).

```bash
python -m interconnect_interface.main                      # every component in database/ that is ready
python -m interconnect_interface.main wg_te_cband_ydir     # or only the named ones
```

The script finds the ready components in `database/`, creates a template library named `pdk_demo`, adds each component from its template (`wg_strip_straight_parameterized`, `dc_strip_te_c`, `gc_strip_te_c`), copies the database files in, removes the template's unused elements and builds the library. A library with the same name already installed in INTERCONNECT must be uninstalled first.

## Known limitations

- The waveguide loss and its temperature dependence are assumed, not simulated.
- The grating coupler model has |S21| from FDTD and the taper's complex response from EME. Its phase and back-reflection are placeholders.
- The crystal axis rotation along a ring or bend is not modelled; the models assume propagation along the crystal Y axis.
- The test die is a template; the electro-optic, thermal and RF structures are not designed yet.