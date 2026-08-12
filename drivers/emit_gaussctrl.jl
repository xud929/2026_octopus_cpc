"""
Multi-turn artificial emittance growth: `slice_interpolation` and deposition.

Decides whether the longitudinal slice-boundary discontinuity measured by
`slice_longitudinal_zscan.jl` actually moves a physics observable, or whether it
is a field-accuracy artefact with no dynamical consequence -- the outcome the
`field_derivative=:fourth` precedent warns about
(`docs/history/poisson_solver_review_2026_07_24.md`, Section 11).

Reference model
---------------
There is no analytic reference. The setup is constructed so that **all** vertical
emittance growth is numerical:

- head-on collision, no crossing angle, no crab cavities, no dispersion;
- linear one-turn maps only, no chromaticity;
- **no radiation damping or excitation**, so nothing masks or damps growth;
- the strong-strong Poisson solver is the only non-symplectic element.

Any `d(eps_y)/dturn > 0` is therefore an artefact of the solver, and differences
between arms are attributable to the compared option.

Arms
----
Selected by environment variable; one process per arm/seed.

| arm | `slice_interpolation` | slices | deposit | role |
|-----|----------------------|--------|---------|------|
| A | `:linear`    | N   | `:CIC` | production baseline |
| B | `:quadratic` | N   | `:CIC` | the option under test |
| C | `:linear`    | 2N  | `:CIC` | "just add slices" alternative, ~4x cost |
| D | `:linear`    | N   | `:TSC` | isolates deposition from interpolation |
| E | `:quadratic` | N   | `:TSC` | the combination the z-scan favours |
| F | `:linear`    | N   | `:CIC` | `interaction_grid=:source_slice`: removes the transverse grid-resizing jump instead |

Discrimination
--------------
A single-seed growth-rate difference proves nothing, because shot noise alone
drives growth. Each arm is run at several seeds. A *coherent* mechanism -- a
kick discontinuity sampled at the synchrotron frequency -- reproduces across
seeds; shot-noise diffusion does not. The reported statistic is therefore the
seed mean growth rate together with its spread, and an arm is only judged
different if the separation exceeds the seed spread.

`boundary_cross_fraction` records the fraction of particles that change slice
index from one turn to the next. If it is near zero the discontinuity is never
sampled and a null result is meaningless, so it is reported as a validity check
rather than assumed.

Error metric
------------
```text
eps_y(turn)  = sqrt(<y^2><py^2> - <y py>^2)
growth_rate  = least-squares slope of eps_y(turn)/eps_y(0) per turn
```

Run
---
One arm/seed (from the project root):

```bash
OCTOPUS_EMIT_SCHEME=quadratic OCTOPUS_EMIT_SEED=1 \
  julia --threads=8 --project=. validation/slice_interpolation_emittance_growth.jl
```

All arms and seeds in parallel, then aggregate:

```bash
julia --project=. validation/slice_interpolation_emittance_growth_summary.jl
```

Overrides: `OCTOPUS_EMIT_SCHEME` (`linear`/`quadratic`), `OCTOPUS_EMIT_NSLICES`,
`OCTOPUS_EMIT_DEPOSIT` (`CIC`/`TSC`), `OCTOPUS_EMIT_GRIDMODE`
(`slice_pair`/`source_slice`/`node`), `OCTOPUS_EMIT_SEED`, `OCTOPUS_EMIT_TURNS`,
`OCTOPUS_EMIT_NPART`, `OCTOPUS_EMIT_GRID`, `OCTOPUS_EMIT_TAG`.

Outputs (under `result/`)
-------------------------
- `emittance_growth_<tag>.tsv`      -- per-turn eps_x, eps_y, eps_z for both beams
- `emittance_growth_<tag>.meta.tsv` -- one summary row (growth rates, validity)
"""

# Uses the precompiled package rather than `include`-ing the source: this script
# is launched once per arm/seed, and 20 concurrent source compilations is pure
# waste. Run `Pkg.precompile()` first if the package has changed.
using Octopus
using DelimitedFiles
using Printf

const O = Octopus

_envi(k, d) = parse(Int, get(ENV, k, string(d)))
_envs(k, d) = Symbol(get(ENV, k, string(d)))

config = (
    scheme    = _envs("OCTOPUS_EMIT_SCHEME", :linear),
    nslices   = _envi("OCTOPUS_EMIT_NSLICES", 15),
    deposit   = _envs("OCTOPUS_EMIT_DEPOSIT", :CIC),
    seed      = _envi("OCTOPUS_EMIT_SEED", 1),
    turns     = _envi("OCTOPUS_EMIT_TURNS", 600),
    npart     = _envi("OCTOPUS_EMIT_NPART", 30_000),
    grid      = _envi("OCTOPUS_EMIT_GRID", 64),
    gridmode  = _envs("OCTOPUS_EMIT_GRIDMODE", :slice_pair),
)
tag = get(ENV, "OCTOPUS_EMIT_TAG",
          "$(config.scheme)_n$(config.nslices)_$(lowercase(String(config.deposit)))" *
          (config.gridmode === :slice_pair ? "" : "_srcgrid") * "_s$(config.seed)")

result_dir = normpath(joinpath(@__DIR__, "..", "result"))
mkpath(result_dir)

# --------------------------------------------------------------- physics -----
# EIC-like flat pair, head-on. Tunes carry the synchrotron motion that sweeps
# particles across slice boundaries; nothing else is nonlinear.
ele = (charge=-1.0, mass=EMASS_EV, energy=10.0e9, n_particle=1.7203e11, cutoff=5.0,
       sigma=(106.0e-6, 9.5e-6, 0.7e-2), beta=(0.55, 0.056, 0.7e-2 / 5.5e-4),
       alpha=(0.0, 0.0, 0.0), tune=(0.08, 0.14, -0.069))
pro = (charge=1.0, mass=PMASS_EV, energy=275.0e9, n_particle=0.6881e11, cutoff=5.0,
       sigma=(95.0e-6, 8.5e-6, 6.0e-2), beta=(0.8, 0.072, 6.0e-2 / 6.6e-4),
       alpha=(0.0, 0.0, 0.0), tune=(0.228, 0.210, -0.01))

set_global_rng!(seed=config.seed * 1_000_003 + 17, method=:philox)

policy = CPUThreadsExecutionPolicy()
beam_ele = Beam(config.npart, policy, Float64;
    beta=ele.beta, alpha=ele.alpha, sigma=ele.sigma, cutoff=ele.cutoff,
    rng_id=1, charge=ele.charge, mc2=ele.mass, E0=ele.energy,
    r0=RE * ME0 / ele.mass, npart=ele.n_particle)
beam_pro = Beam(config.npart, policy, Float64;
    beta=pro.beta, alpha=pro.alpha, sigma=pro.sigma, cutoff=pro.cutoff,
    rng_id=2, charge=pro.charge, mc2=pro.mass, E0=pro.energy,
    r0=RE * ME0 / pro.mass, npart=pro.n_particle)

slicing = LongitudinalSlicing(; method=:normal_quantile, nslices=config.nslices,
                              center_position=:centroid)
solver = GaussianPoissonSolver(; slicing=slicing, longitudinal_kick=true)

ip = StrongStrongCollision(:ip; poisson_solver=solver)
ele_one_turn = Linear6DSpec{Float64}(; beta1=ele.beta, beta2=ele.beta,
    alpha1=ele.alpha, alpha2=ele.alpha, dmu=2pi .* ele.tune)
pro_one_turn = Linear6DSpec{Float64}(; beta1=pro.beta, beta2=pro.beta,
    alpha1=pro.alpha, alpha2=pro.alpha, dmu=2pi .* pro.tune)

task = StrongStrongTask((ip, ele_one_turn), (ip, pro_one_turn))

# ------------------------------------------------------------- emittance -----
function emittances(beam)
    r = beam.rep
    n = length(r.x)
    out = ntuple(3) do k
        q, p = k == 1 ? (r.x, r.px) : k == 2 ? (r.y, r.py) : (r.z, r.pz)
        sq = sp = sqq = spp = sqp = 0.0
        @inbounds for i in 1:n
            qi = q[i]; pi_ = p[i]
            sq += qi; sp += pi_
            sqq += qi * qi; spp += pi_ * pi_; sqp += qi * pi_
        end
        mq = sq / n; mp = sp / n
        vqq = sqq / n - mq * mq; vpp = spp / n - mp * mp; vqp = sqp / n - mq * mp
        sqrt(max(vqq * vpp - vqp * vqp, 0.0))
    end
    return out
end

"""Slice index of every particle, used to count boundary crossings per turn."""
function slice_indices(beam, slicing)
    sl = O.longitudinal_slices(beam.rep, slicing)
    idx = Vector{Int}(undef, length(beam.rep.z))
    for (s, list) in enumerate(sl.indices), i in list
        idx[i] = s
    end
    return idx
end

# ------------------------------------------------------------------ run ------
function run_turns(task, beam_ele, beam_pro, slicing, nturns)
    rows = Vector{Any}()
    cross_counts = Int[]
    prev_ele = slice_indices(beam_ele, slicing)
    prev_pro = slice_indices(beam_pro, slicing)
    push!(rows, [0, emittances(beam_ele)..., emittances(beam_pro)...])
    t0 = time()
    for turn in 1:nturns
        execute!(task, beam_ele, beam_pro; turns=1)
        push!(rows, [turn, emittances(beam_ele)..., emittances(beam_pro)...])
        if turn <= 50   # boundary-crossing validity check, sampled early
            cur_ele = slice_indices(beam_ele, slicing)
            cur_pro = slice_indices(beam_pro, slicing)
            push!(cross_counts, count(!=(0), cur_ele .- prev_ele) +
                                count(!=(0), cur_pro .- prev_pro))
            prev_ele = cur_ele; prev_pro = cur_pro
        end
    end
    return rows, cross_counts, time() - t0
end

rows, cross_counts, elapsed = run_turns(task, beam_ele, beam_pro, slicing, config.turns)

# ------------------------------------------------------------- analysis ------
"""Least-squares slope of `y` against `0:length(y)-1`, per step."""
function slope(y)
    n = length(y)
    xs = 0:(n - 1)
    mx = sum(xs) / n; my = sum(y) / n
    num = 0.0; den = 0.0
    for (x, v) in zip(xs, y)
        num += (x - mx) * (v - my); den += (x - mx)^2
    end
    return num / den
end

turns_col = [r[1] for r in rows]
ex = [r[2] for r in rows]; ey = [r[3] for r in rows]; ez = [r[4] for r in rows]
px_ = [r[5] for r in rows]; py_ = [r[6] for r in rows]; pz_ = [r[7] for r in rows]

gr_ele_y = slope(ey ./ ey[1])
gr_ele_x = slope(ex ./ ex[1])
gr_pro_y = slope(py_ ./ py_[1])
gr_pro_x = slope(px_ ./ px_[1])
cross_frac = isempty(cross_counts) ? 0.0 :
             sum(cross_counts) / (length(cross_counts) * 2 * config.npart)

open(joinpath(result_dir, "emittance_growth_$(tag).tsv"), "w") do io
    writedlm(io, ["turn" "ele_ex" "ele_ey" "ele_ez" "pro_ex" "pro_ey" "pro_ez"])
    writedlm(io, permutedims(hcat(rows...)))
end

meta = [tag String(config.scheme) config.nslices String(config.deposit) String(config.gridmode) config.seed config.turns config.npart config.grid gr_ele_y gr_ele_x gr_pro_y gr_pro_x ey[end]/ey[1] py_[end]/py_[1] cross_frac elapsed]
open(joinpath(result_dir, "emittance_growth_$(tag).meta.tsv"), "w") do io
    writedlm(io, ["tag" "scheme" "nslices" "deposit" "gridmode" "seed" "turns" "npart" "grid" "growth_ele_ey" "growth_ele_ex" "growth_pro_ey" "growth_pro_ex" "final_ratio_ele_ey" "final_ratio_pro_ey" "boundary_cross_fraction" "elapsed_s"])
    writedlm(io, meta)
end

@printf("%-28s ele_ey'=%+.3e pro_ey'=%+.3e  eps_y(end)/eps_y(0)=%.5f  cross=%.3f  %.0fs\n",
        tag, gr_ele_y, gr_pro_y, ey[end] / ey[1], cross_frac, elapsed)
