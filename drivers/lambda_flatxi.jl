# Yokoya-factor seed scatter for the paper's error bars.
# Reuses the measurement pattern of validation/coherent_mode_scans.jl with a
# variable RNG seed. Converged settings (8192 turns, 1e5/beam) x 3 seeds for
# PIC and soft-Gaussian; scan settings (2048 turns, 2e4/beam) x 5 seeds for PIC.
# Octopus is provided by this repository's project environment, pinned in
# Project.toml — see README "Running the drivers".
using Octopus
using Statistics
import FFTW

function fractional_tune(signal)
    n = length(signal)
    w = [0.5 - 0.5 * cospi(2 * (i - 1) / n) for i in 1:n]
    a = abs.(FFTW.rfft((signal .- mean(signal)) .* w))
    k = argmax(a[2:(end - 1)]) + 1
    y1, y2, y3 = a[k - 1], a[k], a[k + 1]
    d = y1 - 2y2 + y3
    return (k - 1 + (d == 0 ? 0.0 : 0.5 * (y1 - y3) / d)) / n
end

function measure(; solver_kind, seed, turns, n_macro, xi=0.005, aspect=1.0)
    set_global_rng!(seed=seed, method=:philox)
    policy = CPUThreadsExecutionPolicy()
    energy = 10.0e9
    gamma_rel = energy / EMASS_EV
    r0 = RE * ME0 / EMASS_EV
    sig = 106.0e-6
    beta = (0.55, 0.55, 0.7e-2 / 5.5e-4)
    r_asp = aspect
    sigy = r_asp * sig
    sigma = (sig, sigy, 0.7e-2)
    npart = xi * 2pi * gamma_rel * sig * (sig + sigy) / (r0 * beta[1])
    b1 = Beam(n_macro, policy, Float64;
        beta=beta, alpha=(0.0, 0.0, 0.0), sigma=sigma, cutoff=5.0, rng_id=1,
        charge=-1.0, mc2=EMASS_EV, E0=energy, r0=r0, npart=npart,
        initial_offset=(0.1 * sig, 0.0, 0.1 * sigy, 0.0, 0.0, 0.0))
    b2 = Beam(n_macro, policy, Float64;
        beta=beta, alpha=(0.0, 0.0, 0.0), sigma=sigma, cutoff=5.0, rng_id=2,
        charge=+1.0, mc2=EMASS_EV, E0=energy, r0=r0, npart=npart)
    slicing = LongitudinalSlicing(; method=:normal_quantile, nslices=1,
                                  center_position=:centroid)
    solver = solver_kind === :gaussian ?
        GaussianPoissonSolver(; slicing=slicing, longitudinal_kick=false) :
        PICPoissonSolver(; slicing=slicing, grid=(128, 128), deposit_method=:CIC,
            green_type=:integrated, green_cache=:slice_pair,
            longitudinal_kick=false)
    ip = StrongStrongCollision(:ip; poisson_solver=solver)
    ot = Linear6DSpec{Float64}(; beta1=beta, beta2=beta,
        alpha1=(0.0, 0.0, 0.0), alpha2=(0.0, 0.0, 0.0),
        dmu=2pi .* (0.31, 0.32, -0.01))
    task = StrongStrongTask((ip, ot), (ip, ot); policy=policy)
    x1 = Vector{Float64}(undef, turns); x2 = similar(x1)
    y1 = similar(x1); y2 = similar(x1)
    for t in 1:turns
        execute!(task, b1, b2; turns=1)
        x1[t] = mean(b1.rep.x); x2[t] = mean(b2.rep.x)
        y1[t] = mean(b1.rep.y); y2[t] = mean(b2.rep.y)
    end
    Lx = (fractional_tune(x1 .- x2) - fractional_tune(x1 .+ x2)) / xi
    Ly = (fractional_tune(y1 .- y2) - fractional_tune(y1 .+ y2)) / xi
    return Lx, Ly
end

function report(tag, vals)
    lx = [v[1] for v in vals]; ly = [v[2] for v in vals]
    println(tag, ":")
    println("  Lambda_x per seed = ", join(round.(lx; digits=4), ", "),
            "   mean=", round(mean(lx); digits=4), " std=", round(std(lx); sigdigits=2))
    println("  Lambda_y per seed = ", join(round.(ly; digits=4), ", "),
            "   mean=", round(mean(ly); digits=4), " std=", round(std(ly); sigdigits=2))
end

seeds3 = (20260727, 314159, 271828)
seeds5 = (20260727, 314159, 271828, 1618033, 1414213)

# Flat-beam Yokoya factor versus beam-beam parameter: does the wide-plane
# plateau approach the 1D flat limit 1.33 as finite-xi effects are removed?
# Longer runs at small xi because the pi-sigma splitting scales with xi.
for r in (0.09, 0.05)
    for xi in (0.005, 0.002, 0.001)
        turns = xi >= 0.005 ? 4096 : (xi >= 0.002 ? 8192 : 16384)
        @time (Lx, Ly) = measure(solver_kind=:pic, seed=1, turns=turns,
                                 n_macro=50000, aspect=r, xi=xi)
        println("flatxi r=", r, "  xi=", xi, "  turns=", turns,
                "  Lambda_x=", round(Lx; digits=4))
        flush(stdout)
    end
end
