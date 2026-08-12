# Revision-era regeneration ledger

One row per dataset regenerated on Octopus `paper-cpc` (see REGENERATION.md
for the campaign). Datasets not listed here are submission-era.

| dataset | paper-cpc commit | date | machine | vs archived |
|---|---|---|---|---|
| `gaussian_pic_field_validation_summary.tsv` | `12325fc` | 2026-08-12 | CPU (4 threads), OCTOPUS_GPIC_GRIDS=48,64,96,128,192,256 | max 3.1% rel shift in error metrics; shape identical |
| `pic_gaussian_field_validation_random_summary.tsv` | `12325fc` | 2026-08-12 | CPU (8 threads) | **bit-identical** at archived settings (SOURCE_AXIS=160, FIELD_AXIS=81, PIC_GRID=128 — the script's defaults drifted to 320/161/256; pin via env when regenerating) |
| `bb3d singleslice_fort.{24,25,34,35}` | BB3D `50d01d8` | 2026-08-12 | this host, 2 MPI ranks | **bit-identical** live rerun from archived decks; launcher must be `/usr/lib64/openmpi/bin/mpirun` (the conda mpirun aborts with MPI_ERR_ARG) |
