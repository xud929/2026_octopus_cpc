# Revision-era regeneration ledger

One row per dataset regenerated on Octopus `paper-cpc` (see REGENERATION.md
for the campaign). Datasets not listed here are submission-era.

| dataset | paper-cpc commit | date | machine | vs archived |
|---|---|---|---|---|
| `gaussian_pic_field_validation_summary.tsv` | `12325fc` | 2026-08-12 | CPU (4 threads), OCTOPUS_GPIC_GRIDS=48,64,96,128,192,256 | **shifted-with-cause, PROVEN**: PIC columns reproduce to 6.4e-12; the 3.0% shift is isolated to the hybrid columns and their gains — the U23-2 signature. The archive (2026-07-28) predates that fix, so its hybrid values are the defective self-comparison; this regeneration is the corrected side. Fig 2 hybrid curve and caption gains move ~3%. |
| `pic_gaussian_field_validation_random_summary.tsv` | `12325fc` | 2026-08-12 | CPU (8 threads) | **bit-identical** at archived settings (SOURCE_AXIS=160, FIELD_AXIS=81, PIC_GRID=128 — the script's defaults drifted to 320/161/256; pin via env when regenerating) |
| `bb3d singleslice_fort.{24,25,34,35}` | BB3D `50d01d8` | 2026-08-12 | this host, 2 MPI ranks | **bit-identical** live rerun from archived decks; launcher must be `/usr/lib64/openmpi/bin/mpirun` (the conda mpirun aborts with MPI_ERR_ARG) |
| `kick_decomposition_R100.tsv` | `12325fc` | 2026-08-12 | CPU (16 threads), OCTOPUS_KD_R=100 NBOOT=200 | **verified**: 100/108 cells bit-identical, rest ≤1.2e-12 rel (fold order) — archived data stands |
