# Deferred multi-turn emittance-growth ensembles

These 80 TSVs are **not** used by any figure or table of the CPC manuscript.
They are retained here because they are the raw material for a planned separate
study, not because they are in doubt.

## Why they are not in the paper

The manuscript measures the field-solver error budget at the level of a
**single kick**, where systematic and shot-noise components are properties of
the solver alone. How the fluctuating component then propagates into multi-turn
emittance growth is a dynamical question that cannot be separated from genuine
beam-beam diffusion, single-particle resonance crossing and coherent-mode
activity without a dedicated study. The manuscript says so explicitly
(Sections 4.1 and 4.3) and does not draw multi-turn conclusions from these runs.

## What is here

Per-turn `eps_x, eps_y, eps_z` for both beams, 4 seeds per arm, produced by
`validation/slice_interpolation_emittance_growth.jl`:

| arm | stem |
|---|---|
| baseline (linear z-interpolation, CIC, 15 slices) | `emittance_growth_linear_n15_cic` |
| quadratic z-interpolation, CIC | `emittance_growth_quadratic_n15_cic` |
| linear, TSC | `emittance_growth_linear_n15_tsc` |
| quadratic, TSC | `emittance_growth_quadratic_n15_tsc` |
| shared source-slice mesh | `emittance_growth_linear_n15_cic_srcgrid` |
| node-indexed mesh | `emittance_growth_linear_n15_cic_node` |
| 30 slices | `emittance_growth_linear_n30_cic` |
| Gaussian-subtracted hybrid, 64^2 | `emittance_growth_hybrid_n15_cic` |
| soft-Gaussian control | `emittance_growth_gaussctrl_n15` |
| fourth-order field differences | `emittance_growth_deriv4` |

## Reproducing them

`validation/slice_interpolation_emittance_growth.jl`, driven by
`OCTOPUS_EMIT_{SCHEME,NSLICES,DEPOSIT,GRIDMODE,SEED,TURNS,NPART,GRID,TAG}`.

**Pin `OCTOPUS_EMIT_TURNS` explicitly.** The script's default turn count drifted
from 800 to 600 during development; these archives were produced at 800 turns
and reproduce exactly only when the count is pinned.

## A correctness note for anyone extending this work

These drivers advance the beam with `execute!(task, b1, b2; turns=1)` inside a
loop so they can sample emittance every turn. That pattern is safe **only
because none of these arms contains a stochastic element**: they are
collision-plus-linear-map lines, which are deterministic given the particle
state.

Do not add a radiation (or any other stochastic) element to a looped driver.
The counter-based Philox stream is keyed by
`(seed, turn, stream, particle, component)`, and a fresh `execute!` call
restarts the task turn counter, so every turn would replay the *same* normal
variates. The excitation then acts as a fixed per-particle kick rather than a
random walk, and the beam equilibrates at `amp/(1-lambda)` instead of `sigma`
(measured: `<x^2>` 795x the intended value over 2000 turns). Use a single
multi-turn `execute!` call and sample through the
`ScheduledObserver`/`MomentObserver` hooks instead --- which is what
`paper/mesh_study_driver.jl` and `test/examples/strong_strong_tracking.jl`,
the two drivers here that *do* carry radiation, already do.
