# pdk_demo: a demo TFLN PDK

A small thin-film lithium niobate (TFLN) PDK in [GDSFactory](https://gdsfactory.github.io/gdsfactory/), inspired by the CSEM open-access platform (WG1 ridge waveguide). It shows the full path from simulation to circuit model:

```
GDSFactory cells  ──►  Lumerical / Tidy3D simulations  ──►  database/ (CML json + S-parameters)  ──►  INTERCONNECT library
   (pdk/)                   (simulations/)                       (database/)                         (interconnect_interface/)
```

Each building block is drawn once in GDS, simulated (FDE, EME, 3D FDTD), converted into a compact model, and compiled into an INTERCONNECT library with the CML Compiler. Circuits such as MZIs and rings can then be simulated from the simulated blocks and compared with measurements from the test die.

## Technology

x-cut LNOI, TE polarisation, light propagating along the crystal Y axis, C band.

| Layer | Material | Thickness |
|---|---|---|
| Substrate | Si | - |
| BOX | SiO2 | 4.7 µm |
| Lithium niobate | x-cut LiNbO3 | 0.6 µm (0.4 µm ridge, 0.2 µm slab) |
| Cladding | SiO2 | 1.6 µm in the simulations (`None` in `layer_stack.py`) |

Ridge waveguide, 1.0 µm wide at the base, 70° sidewalls. The slab is kept everywhere, so every component uses the same 400 nm ridge on the 200 nm slab. Simulated at 1550 nm: n_eff = 1.856, n_g = 2.255, D = -242 ps/(nm·km). Dimensions and all design parameters are in [`pdk/tfln/constants.csv`](pdk/tfln/constants.csv).

How the numbers were chosen:

| Parameter | Value | Origin |
|---|---|---|
| Film, ridge, slab | 600 / 400 / 200 nm | CSEM paper (WG1). The slab is inferred as 600 − 400 |
| BOX | 4.7 µm | CSEM paper, not swept |
| Sidewall angle | 70° | Assumption (literature range 40°–80°, 65° pure-Ar etch, 75–78° at Luxtelligence). Swept 60°–80°, checked against SEM images |
| Waveguide width | 1.0 µm at the base (about 0.71 µm at the top) | Lumerical MODE width sweep, 0.6–1.8 µm |
| Cladding | 1.6 µm | Grating-coupler FDTD cladding sweep |
| Bend radius | 50 µm | 3D FDTD bend study (R = 20, 30, 50 µm) |

At 1.0 µm TE0 and TM0 are nearly degenerate (n_eff 1.8561 vs 1.8577) and TE1 is barely guided in the C band, so the guide is not single-mode in the strict sense.

### GDS layers

| Layer | GDS | Purpose |
|---|---|---|
| WG | 1/0 | Ridge waveguide (stays at 600 nm, the surroundings are etched by 400 nm) |
| MET1 | 10/0 | Electrodes, heaters, poling structures |
| MET2 | 11/0 | Second metal, RF routing |
| VIA | 12/0 | MET1 to MET2 connection |
| DEEP_GRID, CLADDING_OPEN | 20/0, 21/0 | Deep etch grid, cladding opening |
| TEXT, PORT, PORT_ELECTRICAL, DEVREC, FLOORPLAN | 100–104 | Labels, ports, device recognition, floorplan |

## Components in the PDK

| Component | GDS cell (`pdk/tfln/cells/`) | Ports | Key parameters (defaults) | Simulation | INTERCONNECT element (`database/`) | Status |
|---|---|---|---|---|---|---|
| Straight waveguide | `wg` cross-section + `gf.components.straight` | o1, o2 | width 1.0 µm | FDE: n_eff, n_g, D over wavelength and temperature | `wg_te_cband_ydir` (template `wg_strip_straight_parameterized`) | Ready. Propagation loss (20 dB/m) and dn_eff/dT are assumed |
| Sine S-bend | `bend_s` | o1, o2 | dy 1.3 µm, length 20 µm | Part of the coupler FDTD model | - | GDS only |
| 90° bend | `bend_90` | o1, o2 | radius 50 µm | FDE bend sweep + 3D FDTD of the full arc against a straight control (net loss ≈ 0.02 dB, TE-like ≈ 0.14 dB at R = 50 µm) | `bend_90_te_cband` (spar_fixed, wg_bend_90 icon) | Ready |
| Directional coupler (2×2) | `directional_coupler` | o1, o2 (left), o3, o4 (right) | gap 0.4 µm, length 21 µm, port separation 4 µm | 3D FDTD, 4-port S-parameters, 1530–1570 nm | `dc_te_cband_ydir` (template `dc_strip_te_c`) | Ready. 50:50 design |
| Racetrack coupler | `directional_coupler` with the racetrack parameters | o1–o4 | gap 0.4 µm, length 3 µm, S-bends 21 µm, leads 3 µm (κ² = 12.3 % at 1550 nm) | Tidy3D 3D FDTD, 51 points, 1500–1600 nm (`simulations/dc_tidy3d/`) | `dc_racetrack_te_cband_ydir` | Ready |
| 1×2 MMI | `mmi_1x2` | o1 (input), o2, o3 | 5.0 µm × 17.5 µm, access tapers 1.5 µm × 10 µm | 3D FDTD (tolerance and length sweeps) | `mmi_1x2_te_cband_ydir` | Ready |
| Racetrack resonator | `racetrack_resonator` | o1 (bus in), o2 (bus out) | radius 50 µm, built from the racetrack coupler, four `bend_90` and one straight | Compound of the elements above | `rr_racetrack_te_cband_ydir` (compound `.ice` + `.svg`) | Ready |
| Taper | `taper` | o1 (narrow), o2 (wide) | 1 → 12 µm over 200 µm | EME, complex 2-port S-matrix | Inside the grating coupler element | Ready (as part of the grating coupler) |
| Grating coupler with its taper | `grating_coupler` | o1 (waveguide), fiber (marker) | period 0.945 µm, fill 0.6, 20 periods, 8° fibre | 3D FDTD power efficiency (0.365 at 1550 nm) cascaded with the EME taper | `gc_te_cband_ydir` (template `gc_strip_te_c`) | Ready. Grating phase and reflection are placeholders (0) |

Not in the PDK yet: Euler bend, edge coupler, phase shifters (electro-optic, thermal), modulators, RF lines and pads.

## Test dies

**Racetrack die** (`pdk/tfln/cells/test_die_racetrack.py`): one 4-fibre array (pitch 127 µm, grating couplers on the left of every structure). Fibre 2 is the laser input, fibres 1 and 3 are the detectors. Each structure is a unit with its own grating column and a clearance window, so any unit can be measured alone.

| Group | What it extracts |
|---|---|
| Waveguide loop-backs of growing length | Propagation loss (cutback) |
| Loop-backs of equal length with a growing number of 180° turns | Bend loss |
| Racetrack coupler and a sweep of length and gap (through to fibre 3, cross to fibre 1) | Split ratio and excess loss |
| Racetrack resonators for the same coupler variants, plus a longer ring (bus output to fibre 3) | Group index, loss, coupling |

Write the GDS with `python -m pdk.tfln.cells.test_die_racetrack` (output: `gds/tfln_racetrack_die.gds`, about 3.1 × 2.4 mm).

**General test die** (`test_die.py`): places every block between grating-coupler pairs: reference and cutback straights, tapers, S-bends, 180° turns, directional couplers (length and gap sweeps), unbalanced MZIs and rings. The EO, thermal and RF structures are placeholders (metal boxes).

## Repository layout

```
pdk/tfln/                  GDSFactory PDK: layers, layer stack, cross-section, cells, constants.csv
pdk/tfln/cells/            bend_s, bend_90, directional_coupler, taper, grating_coupler, mmi_1x2,
                           racetrack_resonator, test_die_racetrack
test_die.py                general test die
simulations/               Lumerical and Tidy3D scripts and the converters to CML data
  dc_tidy3d/               racetrack coupler in Tidy3D (see its README), writes the CML files
  wg_dispersion.py, wg_width_sweep.py    waveguide FDE
  dc_fdtd.py, dc_supermode_sweep.py      directional coupler
  gc_fdtd_2d.py, gc_fdtd_3d.py           grating coupler
  taper_eme.py                           taper
  tfln_common.py                         shared stack constants
database/passives/         CML source data per component (json + S-parameter file)
interconnect_interface/    builds the INTERCONNECT library from database/
```

## Quick start

```bash
uv sync                                   # Python >= 3.12, gdsfactory >= 9.51
python -c "from pdk.tfln.pdk import TFLN_PDK; import gdsfactory as gf; gf.get_component('racetrack_resonator').show()"
python -m pdk.tfln.cells.test_die_racetrack
```

## Building the INTERCONNECT library

Requires Lumerical v261 with the CML Compiler on Windows, and this repo run from WSL (the compiler works in `/mnt/c/pdk_work`).

```bash
python -m interconnect_interface.main                      # every component in database/ that is ready
python -m interconnect_interface.main wg_te_cband_ydir     # or only the named ones
```

The script finds the ready components in `database/`, creates a template library named `pdk_demo`, adds each component from its template, copies the database files in, removes the template's unused elements and builds the library. The 90° bend reuses the free MMI spar_fixed template with the `wg_bend_90` icon, and the racetrack resonator is a compound element (DC + 4 × `bend_90` + straight) with no template. A library with the same name already installed in INTERCONNECT must be uninstalled first.

## Known limitations

- The waveguide loss and its temperature dependence are assumed, not simulated.
- The grating coupler model has |S21| from FDTD and the taper's complex response from EME. Its phase and back-reflection are placeholders.
- The `bend_90` model takes its phase from the bent-FDE n_eff and n_g; its reflection is not simulated.
- The crystal axis rotation along a ring or bend is not modelled; the models assume propagation along the crystal Y axis.
- `layer_stack.py` has no cladding thickness and no metal layers, although the simulations use 1.6 µm of cladding.
- The electro-optic, thermal and RF structures are not designed yet.
- The ports o3 and o4 of the directional coupler are numbered differently in the cells and in `test_die.py`; the racetrack cell finds them by position.