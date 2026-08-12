# BeamBeam3D cross-code comparison — provenance

Recorded 2026-08-06 (2026-08-05_b audit, U22-12). The comparison **data** was
committed and reproduces exactly, but nothing recorded where it came from: no
BeamBeam3D version, no run date, no host, and no note saying which of the six
decks in this directory produced the published numbers. A cross-code agreement
whose other code cannot be identified is not a reproducible claim.

## Which deck

The single-slice coherent-mode comparison uses:

| file | role |
|---|---|
| `beam1.in`, `beam2.in` | the two beam definitions |
| `singleslice_fort.24`, `singleslice_fort.25` | BeamBeam3D `fort.24`/`fort.25` outputs |
| `singleslice_fort.34`, `singleslice_fort.35` | BeamBeam3D `fort.34`/`fort.35` outputs |

The `multislice*`, `*_crossing` and `eicdamp` files in this directory belong to
other studies and are **not** the single-slice comparison inputs.

## The other code

- **BeamBeam3D**, checkout at commit `50d01d8`.
- Run directory on this host: `/cfs/ad/dxu/Library/BeamBeam3D/coherent_modes`.
- Run date: **2026-07-27** (mtime of `BeamBeam3D.log` in that directory).
- 2 MPI processes, 8192 turns tracked, 1 collision point, luminosity sampled
  every 1000 turns, close-orbit squeeze over the first 20 turns — read from
  `BeamBeam3D.log`, which is not committed here because it is a run artefact of
  an external tree.

## Verified, not asserted

Checked on 2026-08-06 with `cmp`, against the live run directory above:

- `singleslice_fort.{24,25,34,35}` are **bit-identical** to `fort.{24,25,34,35}`
  in the run directory (they are the same files, renamed on commit);
- `beam1.in` and `beam2.in` are **bit-identical** to the run directory's copies.

Checksums of the two spectra the paper reads:

```
d8dd38ce670935ebe5cb59e17347b876  singleslice_fort.24
888cdda8d9558bcec8b6860a804f4fc4  singleslice_fort.25
```

## Matching Octopus configuration

The deck matches the Octopus benchmark parameter for parameter: 100k
macroparticles, 128x128 grid, 1 slice, 8192 turns, sigma = 106 um, beta* = 0.55,
npart = 8.9141e9, tunes 62.31 / 60.32, and a horizontal offset
`cn.x = 1.06e-5` = 0.1 sigma.

## What is still not reproducible from this repository

The BeamBeam3D tree itself is not vendored here, so reproducing the comparison
requires that code at commit `50d01d8`. That is a deliberate boundary — this
repository does not vendor other codes — but it means "reproduces exactly"
above refers to the committed OUTPUTS reproducing, not to re-running
BeamBeam3D from scratch.
