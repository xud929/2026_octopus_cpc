# Octopus CPC paper — manuscript and reproduction package

This repository is the publication project for
"A GPU-accelerated framework for multi-slice, multi-turn strong-strong
beam-beam simulation" (submitted to Computer Physics Communications). The
simulation framework itself lives at https://github.com/xud929/Octopus.jl;
this repository archives everything needed to trace and rebuild the paper's
results.

## Layout

- `manuscript/` — the submission tex/pdf, class files and submitted figures
  (copied from the frozen submission snapshot; that snapshot, with its own
  `SHA256SUMS`, remains the archival record of what the journal received).
- `data/` — the frozen, audit-corrected records behind every figure and
  table (nine figures, six tables). This supersedes the earlier
  five-figure supplement packaged with the submission.
- `figs/` — the archived figure PDFs; regenerate with `make_figures.py`.
- `make_figures.py` — rebuilds all nine manuscript figures from `data/`
  offline (matplotlib only, no network, no absolute paths).
- `verify_manuscript_claims.py` — recomputes the manuscript's quantitative
  claims from `data/` and asserts each appears in `manuscript/main.tex`.
- `drivers/` — paper-specific measurement drivers (aspect/tune/xi scans,
  slice-interpolation study arms, the mesh study). They run against Octopus
  pinned in `Project.toml`.

Six further paper-cited measurement scripts live in the Octopus repository
under `validation/` (see its README section "Paper Reproduction Drivers"),
and the device-time profiling driver under `profiling/` — they are reusable
code-correctness measurements, so they stay with the code. Their frozen
outputs are archived here.

## Octopus pin

Every dataset in `data/` was produced at or before Octopus commit
`c3f80f005b55dc314ade1b8980612c08db82d232`
(the migration commit; per-dataset provenance below and in the Octopus audit
records). `Project.toml` pins that commit for the drivers:

```bash
julia --project=. -e 'using Pkg; Pkg.instantiate()'   # once Octopus.jl is public
julia --project=. drivers/lambda_tunescan.jl
```

Until Octopus.jl's public release, point the environment at a local clone
instead: `julia --project=. -e 'using Pkg; Pkg.develop(path="/path/to/Octopus")'`
checked out at the pinned commit.

## Quick start

```bash
python3 make_figures.py           # regenerates figs/*.pdf from data/
python3 verify_manuscript_claims.py
sha256sum -c SHA256SUMS           # integrity of the frozen package
```

**Known state of the claim verifier (2026-08-12):** it reports ~42 findings
against the submitted manuscript. These are not verifier defects — they are
the revision queue created when the 2026-08-05/06 Octopus audits corrected
the archived data (the Vlasov-normalization and quadrature fixes among them)
after submission: numbers the corrected data now derives that the submitted
text does not yet contain. Each finding names the value the revised
manuscript should carry; the verifier reaching zero findings is the
definition of the revision being numerically complete.

---

# Package provenance (the reproduction record)

`python3 make_figures.py` regenerates all **nine** manuscript figures into
`figs/` from `data/`. It uses matplotlib only, with no network access and no
absolute paths.

## Figures

Numbered as in the manuscript.

| # | file | section | data |
|---|---|---|---|
| 1 | `fig_noise_floor.pdf` | 4.1 | `flat_beam_noise_floor.tsv` |
| 2 | `fig_error_vs_grid.pdf` | 4.1 | `gaussian_pic_field_validation_summary.tsv` (regenerate with `OCTOPUS_GPIC_GRIDS=48,64,96,128,192,256`; the script's default sweep is only 48,64,128 — U23-10), `pic_analytic_floor.tsv` |
| 3 | `fig_error_vs_aspect.pdf` | 4.1 | `pic_gaussian_field_validation_random_summary.tsv` |
| 4 | `fig_boundary_jump.pdf` | 4.2 | `slice_longitudinal_zscan_jumps.tsv`, `slice_longitudinal_zscan_tsc_jumps.tsv` |
| 5 | `fig_coherent_fft.pdf` | 5.1 | `coherent_spectrum_pic_{x,y}.tsv` |
| 6 | `fig_yokoya_scans.pdf` | 5.1 | `yokoya_vs_aspect{,_narrow,_measured}.tsv`, `yokoya_vs_xi_{theory,measured}.tsv`, `yokoya_box_convergence.tsv`, `lambda_narrowplane.tsv` (see note) |
| 7 | `fig_multislice_spectra.pdf` | 5.3 | `multislice_centroids_{octopus_kicked,octopus_noise,bb3d}.tsv` |
| 8 | `fig_eic_emittance.pdf` | 5.4 | `eic_emittance_{octopus,bb3d}.tsv` |
| 9 | `fig_eic_modes.pdf` | 5.6 | `eic_mode_spectra.tsv` |

## Tables

- **Table 1** (single-kick error budget, Sec. 4.1) is exactly
  `flat_beam_noise_floor.tsv`. Six-seed repeat scatter: `nf_seed_{11..66}.tsv`.
- **Table 2** (Yokoya factors, Sec. 5.1): the PIC row is
  `lambda_round_converged.tsv`, an independent three-seed re-measurement from
  `lambda_flat_converged.jl` (aspect 1.0) that reproduces the printed entries;
  the BeamBeam3D entry uses the single-slice deck in `data/bb3d_decks/`
  (`beam1.in`, `beam2.in`, `singleslice_fort.{24,25,34,35}`) -- see
  `data/bb3d_decks/PROVENANCE.md` for the BeamBeam3D commit, run date and
  the verification that the committed files are bit-identical to the run.
  "The deck" was ambiguous between six decks in that directory
  (2026-08-05_b audit, U22-12).
- **Table 3** (cross-code emittance benchmark, Sec. 5.4) is computed from
  `eic_emittance_{octopus,bb3d}.tsv` as the mean over the final 2048 turns.
  NOTE the two beams use different baselines, deliberately: the DAMPED electron
  is referenced to the design emittance sigma*^2/beta* (damping erases its
  initial sample), while the UNDAMPED proton is referenced to each code's own
  initial value. Referencing the proton to design would permanently import the
  two codes' initial sampling difference (-0.28 and +0.42 pp in x and y),
  which is larger than the growth differences being compared.
- **Tables 4 and 5** (CUDA waterfall and ablation, Sec. 6.2) are wall-clock A/B
  measurements recorded in the paper text; `cpu_gpu_timing_summary.tsv` and
  `gpu_size_scaling.tsv` hold the thread sweep, observer A/B and size scans.
- **Table 6** (device-time decomposition, Sec. 6.3) is
  `cuda_device_time_decomposition.tsv`, produced by CUDA.jl 6.2.1's in-process
  CUPTI profiler (`CUDA.@profile`) over 10 steady-state turns after 20 warm-up
  turns at the production point. The file header records the summed and the
  UNION device-busy time (they agree to 0.54%, because the production collision
  path is single-stream). Note the transform pipeline is split across two rows:
  `cuFFT transforms` (26.9 ms/turn) is the transform kernels, and
  `transform staging and normalization` (10.8 ms/turn) is the real<->complex
  packing and cuBLAS scaling that exist only to feed them -- their launch
  counts are integer multiples of the transform counts with zero residual.
  The full pipeline is 37.7 ms/turn, 15.6% of device time.

**Correction, 2026-08-06 (audit lead U22-1) — Fig. 6 is unaffected, and here
is why that is checkable.** `yokoya_vs_aspect.tsv` was regenerated again after
a *quadrature* defect was found in the same driver: the source average used a
fixed 96-node Gauss-Hermite rule whose node spacing is set by the measure,
while the integrand's structure lives on the averaged plane's scale `s_t`.
For flat beams the rule stepped over that structure entirely, and the archived
table's three flattest rows were artifacts — r = 0.02 read **23.16** where the
converged value is **1.321**. The rule is now a panel Gauss-Legendre whose
panel width resolves `s_t`.

`make_figures.py` draws the theory curve only for `r >= VLASOV_CONVERGED_MIN_R
= 0.5`, and every row at r >= 0.5 was always on the converged side: the
regenerated values move by ~2e-6 relative (1.2060096 -> 1.2060074 at r = 0.5,
1.1619516 -> 1.1619506 at r = 1.0), i.e. the fifth decimal. **No figure or
caption number changes.** The archived TSV now carries the corrected rows plus
three diagnostic columns (`max_u`, `mode_gap`, `is_mode`/`mesh_ok`); all are
numeric, so `read_tsv`'s `float()` parse is unaffected.

**Note on Fig. 6's theory curves.** `yokoya_vs_aspect.tsv` was regenerated
after a normalization defect was found in
Octopus `validation/coherent_mode_vlasov_theory.jl`: the reduction normalized its
kick to its own averaged curvature rather than to the analytic on-axis
gradient that defines xi, which forces u(0) = 1 whatever the kernel does and
inflates Lambda by (sqrt2 r + 1)/(r + 1). The driver is fixed (both the m=1
matrix and the independent particle solver), carries a self-check that fails
if the circular normalization returns, and the archived TSV is the corrected
output. Round-beam Lambda: 1.40 before, 1.162 after, against a measured 2D
1.206.

The two solvers' residual difference is NOT m=1 truncation, as an earlier
version of this note said: it is the particle solver's periodic box. The
kernel's range is set by the *other* plane's width sigma_o = r, so the
default L = 24 box is narrower than the kernel itself once r is large.
Holding dx fixed and widening the box collapses the difference
(`yokoya_box_convergence.tsv`):

| r | L=24 | L=48 | L=96 | L=192 |
|---|---|---|---|---|
| 0.2 | 1.16% | 0.64% | 0.50% | 0.46% |
| 0.5 | 1.35% | 0.45% | 0.27% | 0.22% |
| 1.0 | 1.68% | 0.53% | 0.22% | 0.12% |
| 11.111 | 8.11% | 2.39% | 0.39% | 0.03% |
| 50 | 12.52% | 4.85% | 1.70% | 0.20% |

So the m=1 closure is accurate to a few parts in 1e3, and the curve plotted
in Fig. 6 (drawn at the default L=24) sits 1.1% below its converged value at
r=0.5 and 1.5% at r=1 --- stated in the figure caption so the visible gap
between the two curves is not read as a difference of model.

`yokoya_vs_aspect.tsv` covers r <= 1, the WIDE plane of a flat source. The
NARROW plane is the reciprocal aspect ratio, archived separately in
`yokoya_vs_aspect_narrow.tsv` (r = 11.111 -> 1.0824, asymptote -> 1.0708 in
the m=1 matrix): these are the narrow-plane values quoted in Sec. 5.1, which
previously appeared in no archived file.

The driver's self-check 4 FAILS only for r <= 0.3 and passes at r = 0.5, 0.7,
0.85, 1.0, 5.0, 11.111 --- so the figure mask is r >= 0.5, not the earlier
and over-conservative r >= 0.8. Self-check 5 is an exact check on the
assembly constants: a harmonic interaction V(u) = u^2/2 has the closed form
K(J,J') = -sqrt(J J')/2 and must give Lambda = 2. Measured: kernel matches
the closed form to 1.2e-14, q_sigma - Q0 = 1.2e-7, (q_pi - Q0)/xi = 1.999988.

## Section-level supporting data

- **Sec. 4.1, mesh study (the measurement that carries the section).**
  `mesh_study_reexecution.tsv` + `drivers/mesh_study_driver.jl` --- seeds 1/2222/3333 at
  64^2, 256^2 and the grid-free soft-Gaussian reference, and seeds 1/2222 at
  128^2 (the coverage is uneven; the third seed is the largest wherever it
  exists, so the 128^2 mean is the one most likely biased low). Re-executed
  from the released tag with the driver archived. This supersedes an earlier
  unarchived study; see "Code and data availability" in the manuscript.
  See also the Green-cache confound control below: about half the apparent
  mesh trend in this file is the cache, not the mesh.
- **Sec. 4.1, mesh-swap control.** `noise_floor_meshswap.tsv` +
  `noise_floor_meshswap.jl` (Octopus `validation/`) (plain PIC at 64^2 against hybrid at 128^2).
  NOTE this same driver also regenerates Table 1 (`flat_beam_noise_floor.tsv`)
  bit-for-bit in all eight rows once `picgrid`/`hybgrid` are set to the
  production assignment (128/64) -- verified. So Table 1 is re-executable, and
  its per-entry structure is readable from the driver: the median over 5/5/3
  independent draws at 1e4/1e5/1e6, taken per solver column, with the draws
  shared across the four columns of a row.
- **Sec. 4.1, both proton planes.** `mesh_study_both_planes.tsv` -- the mesh
  study measured in both planes, seeds 1/2222/3333 at 64^2 and 256^2. Paired
  64^2->256^2: eps_x +0.0342+-0.0105 pp (t=5.65, p=0.030), eps_y
  +0.0426+-0.0045 pp (t=16.36, p=0.004). The manuscript quotes eps_x, the
  conservative plane.
- **Sec. 4.1, systematic/fluctuation decomposition.**
  `kick_decomposition_R100.tsv` + `kick_decomposition.jl` (Octopus
  `validation/`). Realization count
  from `OCTOPUS_KD_R` (default 100), bootstrap draws from `OCTOPUS_KD_NBOOT`
  (default 200); the script writes the archived file directly.
  `bias_floor_bootstrap` is the sampling-noise floor of the bias statistic
  MEASURED by a sign-flip (Rademacher) bootstrap on the CENTRED residuals:
  flipping preserves the per-point fluctuation structure and destroys the
  systematic, so the flipped ensemble's median |mean| is the floor, with no
  distributional assumption. Centring matters -- `bias_floor_bootstrap_uncentered`
  is the same statistic without it, and it runs 13-42% high on the high-bias
  rows because flipping raw errors leaves mu*(1/R)sum(s_r), a residual of the
  systematic of scale |mu|/sqrt(R). `bias_floor_rayleigh` is the
  Gaussian-isotropic closed form `fluct*sqrt(ln 2 / R)`, which sits 6-18% above
  the measured floor throughout.
- **Sec. 4.1, reference-noise bound.** `softgauss_count_scan.tsv`.
- **Sec. 5.1, tune-swap control.** `lambda_tuneswap_control.tsv`.
- **Sec. 5.1, narrow-plane xi control.** `lambda_narrowplane_fixedxiy.tsv` +
  `drivers/lambda_fixedxiy.jl` (holds xi_y = 0.005 at every aspect ratio, showing the
  narrow-plane branch is not a xi_y artifact).
- **Sec. 5.1, flat-beam robustness.** `drivers/lambda_flatxi.jl`, `drivers/lambda_tunescan.jl`
  (Lambda against xi and against working point).
- **Sec. 4.1, Green-cache confound control.** `mesh_study_cache_none.tsv` --
  the identical mesh study re-run with `OCTOPUS_PIC_GREEN_CACHE=none`, three
  seeds at each of 64^2/128^2/256^2. The cache's tight-fit penalty is
  mesh-dependent (+5.4% at 64^2 against +0.4%/+0.3% at 128^2/256^2), so it
  contributes about half the apparent mesh trend; the paper reports the trend
  both with and without it. This arm also carries the full three-seed coverage
  at 128^2 that the cached study lacks.
- **Sec. 5.1, Table 2 re-measurement.** `lambda_round_converged.tsv` +
  `lambda_flat_converged.jl` (Octopus `validation/`; aspect 1.0) -- the round-beam PIC row of Table 2
  re-measured from an archived driver at three fresh seeds.
- **Sec. 5.1, converged flat-beam point.** `lambda_flat_converged.tsv` +
  `lambda_flat_converged.jl` (Octopus `validation/`) -- the r = 0.09 point re-measured at the converged
  settings of Table 2 (8192 turns, 1e5 macroparticles/beam, three seeds),
  reporting BOTH planes. This is what keeps the flat-limit statement from
  resting on the single-seed reduced-settings scan.
- **Sec. 5.4, cross-code emittance benchmark.**
  `eic_emittance_octopus.tsv` (Octopus moment-observer output, every 16 turns)
  and `eic_emittance_bb3d.tsv` (BeamBeam3D `fort.24/25/34/35` column 7,
  subsampled to the same cadence). Head-on, 15 slices, 128^2 mesh, 10^5
  macroparticles per beam in both codes, 8192 turns, electron damping
  shortened to 400 turns. The BeamBeam3D deck is the `eicdamp` case; note that
  the crab cavities and crossing angle must BOTH be off for a head-on
  comparison -- zeroing the crossing angle alone while leaving the crab
  strength at its compensating value tears the beams apart.
- **Sec. 5.2/5.3, cross-code.** BeamBeam3D input decks and raw centroid outputs
  in `data/bb3d_decks/`. Convergence runs:
  `multislice_centroids_octopus_kicked_n{9,15}.tsv`,
  `multislice_centroids_bb3d_n9.tsv`, and the 16384-turn sigma-resolution pair
  `multislice_centroids_{octopus_kicked,bb3d}_16k.tsv`.
- **Sec. 5.5, luminosity anchor.** `crossing_lum_anchor.tsv`
  (Octopus `validation/crossing_luminosity_anchor.jl`; analytic Piwinski
  reference). Provenance caveat: the script prints the R values and writes
  only `.lum` files under `result/lum_anchor/` — this TSV was assembled BY
  HAND from that output, so there is no machine-reproducible path from
  script to artifact; re-deriving it means re-running the script and
  re-transcribing (2026-08-05 audit, U21-12).
- **Sec. 5.5, crossing-angle dynamical cross-check.**
  `multislice_centroids_{octopus_kicked,bb3d}_crossing.tsv` (half angle
  3.855e-4, Piwinski phi = 1). Deck note: the BeamBeam3D field labeled `alpha`
  is the crossing-plane azimuth; `phi` is the half angle. Setting `alpha` alone
  silently runs head-on.
- **Sec. 5.6, weak-strong reduction anchor.**
  `weakstrong_limit_anchor_compensated.tsv` (400 turns at the compensated
  point).
- **Tune-estimator calibration.** Octopus `validation/tune_estimator_calibration.jl`
  (500 synthetic two-tone trials).

## Not used by the manuscript

`data/multiturn_deferred/` holds 80 multi-turn emittance-growth ensemble TSVs
that no figure or table of this paper uses. They support a planned separate
study; see the README in that directory, which also records a driver-level
correctness constraint worth reading before extending them.

## Reproducibility notes

- Scripts in this repository use paths relative to their own location, so
  the package is self-contained; `verify_manuscript_claims.py` reads
  `manuscript/main.tex` (its pre-migration version read an absolute path
  outside the package — fixed 2026-08-12).
- Documented gaps, of two kinds. (a) The driver for the *original*
  mesh/reference decomposition of Sec. 4.1 was not archived, and that study is
  not re-executable; `mesh_study_driver.jl` is the archived re-execution that
  carries the section's conclusions, and the original's claim is withdrawn in
  the manuscript. (b) A few datasets are frozen without their generating
  driver -- `flat_beam_noise_floor.tsv` and its `nf_seed_*` repeats,
  `pic_analytic_floor.tsv`, and the `slice_longitudinal_zscan*` files. These
  are checkable and re-plottable but not re-executable, and the manuscript
  rests no conclusion on any of them alone.
- Pin turn counts explicitly when re-running validation ensembles; at least one
  script's default drifted during development.
