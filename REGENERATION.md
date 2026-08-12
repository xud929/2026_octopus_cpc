# Regenerating the paper's data on Octopus `paper-cpc`

The revision regenerates the archived datasets against current Octopus (the
submitted data predates both the 2026-08-05/06 audit corrections' final form
and the 2026-08-11 performance campaign). Runbook: one row per dataset,
generator, machine, and standing. Record the exact `paper-cpc` commit in
each regenerated file's provenance (header comment or a sibling
`PROVENANCE` note), rerun `make_figures.py` and `verify_manuscript_claims.py`
after each batch, and commit data + figure changes together.

**Reporting policy (owner, 2026-08-12):** the paper's tables and figures
are produced on THIS machine's GPU (RTX 4500 Ada) — the EIC strong-strong
production case at ~0.3 s/turn including luminosity and moment output is the
headline table number. The A100 result (<0.2 s/turn, near state of the art)
is cited in TEXT from the Octopus history records
(`docs/history/weak_strong_cuda_luminosity_2026_08_11.md` and the
strong-strong benchmark histories), not carried by any table or figure. The
revised manuscript must fit **15 pages including everything** — the Sec. 6
rewrite budget is bounded by that.

**Settings pins.** Two datasets already caught script-default drift (the
U23-10 class): regeneration MUST pin the archived settings explicitly (env
or kwargs) and record them in the ledger row — a bare default run answers a
different question than the archived figure.

**Read this first — the performance section changes qualitatively.** The
2026-08-11 Octopus campaign (device-side luminosity reduction, fused moment
kernels, observer buffering; `docs/history/weak_strong_cuda_luminosity_2026_08_11.md`)
removed costs the submitted Sec. 6 *describes* — e.g. the per-moment
host-synchronizing reductions. Tables 4–6 will not just shift numerically;
parts of the narrative describe machinery that no longer exists. Regenerate
those last, after deciding how Sec. 6 is rewritten.

## Physics datasets (safe to regenerate first — expect ulp-to-noise-level shifts)

| dataset(s) | generator | machine | notes |
|---|---|---|---|
| `gaussian_pic_field_validation_summary.tsv` (Fig. 2) | Octopus `validation/gaussian_pic_field_validation.jl` | CPU, threads | needs `OCTOPUS_GPIC_GRIDS=48,64,96,128,192,256` |
| `pic_gaussian_field_validation_random_summary.tsv` (Fig. 3) | Octopus `validation/pic_gaussian_field_validation.jl` | CPU, threads | `OCTOPUS_PIC_VALIDATION_RANDOM_CASES=100`, no per-case data |
| `flat_beam_noise_floor.tsv` (Table 1, Fig. 1) + `nf_seed_*` | Octopus `validation/noise_floor_meshswap.jl` | this machine (GPU or CPU threads) | production `picgrid/hybgrid = 128/64` assignment reproduces Table 1 (verified bit-for-bit at submission); seeds per archived set |
| `noise_floor_meshswap.tsv` (Sec. 4.1 control) | same script, meshswap assignment | this machine (GPU or CPU threads) | |
| `kick_decomposition_R100*.tsv` (Sec. 4.1) | Octopus `validation/kick_decomposition.jl` | CPU ok, hours | `OCTOPUS_KD_R=100`, seeds as archived |
| `mesh_study_reexecution.tsv`, `mesh_study_both_planes.tsv`, `mesh_study_cache_none.tsv` | `drivers/mesh_study_driver.jl` | this machine | cache_none arm: `OCTOPUS_PIC_GREEN_CACHE=none`; seeds 1/2222/3333 |
| `lambda_round_converged.tsv`, `lambda_flat_converged.tsv` (Table 2) | Octopus `validation/lambda_round_converged.jl` / `lambda_flat_converged.jl` | this machine, long | 8192 turns, 1e5/beam, 3 seeds each |
| `yokoya_vs_aspect{,_narrow}.tsv`, `yokoya_vs_xi_theory.tsv`, `yokoya_box_convergence.tsv`, `lambda_narrowplane_fixedxiy.tsv` theory side | Octopus `validation/coherent_mode_vlasov_theory.jl` | CPU | theory only; already carries the audit fixes |
| `yokoya_vs_aspect_measured.tsv`, `yokoya_vs_xi_measured.tsv`, `lambda_narrowplane.tsv` | `drivers/lambda_flatxi.jl`, `drivers/lambda_fixedxiy.jl`, `drivers/lambda_narrowplane.jl`, `drivers/lambda_tunescan.jl` | this machine, long | scans print to stdout — capture transcripts to `data/*.log` and transcribe; keep the transcripts (see README, Run transcripts) |
| `eic_emittance_octopus.tsv` (Table 3, Fig. 8) | Octopus `validation/eic_emittance_benchmark.jl` | this machine, hours | BB3D side stays frozen unless BeamBeam3D is rerun |
| `emit_xcode_*.tsv`, centroid overlays | Octopus `validation/emit_xcode.jl` | this machine | |
| `crossing_lum_anchor.tsv` (Sec. 5.5) | Octopus `validation/crossing_luminosity_anchor.jl` | CPU | hand-transcribed from `.lum` outputs (U21-12) — keep the transcript |
| `softgauss_count_scan.tsv`, `lambda_tuneswap_control.tsv`, `stationarity_*.tsv` | **generator not identified in the archived README** | — | owner to identify or mark frozen |

## Frozen without a driver (documented gaps — cannot be regenerated)

`pic_analytic_floor.tsv`, `slice_longitudinal_zscan*_jumps.tsv` (Fig. 4),
The zscan jumps regenerate only if `slice_longitudinal_zscan.jl` (in
Octopus validation) still emits the jump tables; check before assuming.
The BeamBeam3D outputs are NO LONGER frozen: the 50d01d8 checkout on this
host reruns the archived decks bit-identically (verified 2026-08-12,
single-slice set; use `/usr/lib64/openmpi/bin/mpirun`). The manuscript
rests no conclusion on the remaining frozen-only files alone.

## Performance datasets (THIS machine's GPU, regenerate last)

| dataset | generator | notes |
|---|---|---|
| `cuda_device_time_decomposition.tsv`, `cuda_device_activities.tsv` (Table 6) | Octopus `profiling/cuda_device_profile.jl` | the decomposition will differ structurally post-2026-08-11 |
| `cpu_gpu_timing_summary.tsv`, `gpu_size_scaling.tsv` (Tables 4–5) | wall-clock A/B per the archived headers | re-derive the ablation list — several ablated costs no longer exist |
| `instrumentation_overhead.tsv`, `production_ab_growth.tsv`, `round12_ablations.tsv` | archived headers name the settings | same caveat |

## Sequencing

1. CPU-tractable physics first (Figs. 2–3, kick decomposition, theory
   curves) — validates the pipeline end to end on `paper-cpc`.
2. This-machine physics campaigns (Tables 1–3, Figs. 5–9 measured sides).
3. Rewrite Sec. 6 against the current architecture, then regenerate the
   performance tables to match.
4. After each batch: `make_figures.py`, `verify_manuscript_claims.py`
   (the finding count should fall), commit data+figs together with the
   `paper-cpc` commit hash in the message.
