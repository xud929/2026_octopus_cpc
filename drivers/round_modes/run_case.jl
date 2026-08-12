#!/usr/bin/env julia

using Dates
using Printf
using Statistics

const OUTPUT_ROOT = get(ENV, "OCTOPUS_OUTPUT_ROOT") do
    error("set OCTOPUS_OUTPUT_ROOT to an output directory")
end
const OCTOPUS_ROOT = get(ENV, "OCTOPUS_ROOT") do
    error("set OCTOPUS_ROOT to the evaluated Octopus checkout")
end
git_output(args...) = strip(read(`git -C $OCTOPUS_ROOT $(args)`, String))
const OCTOPUS_COMMIT = git_output("rev-parse", "HEAD")
const OCTOPUS_TREE = git_output("rev-parse", "HEAD^{tree}")
const OCTOPUS_STATUS = git_output("status", "--porcelain=v1")
OCTOPUS_COMMIT == "c6c7a989a1bd234b54d1613b43db911a0e652720" ||
    error("unexpected Octopus commit")
OCTOPUS_TREE == "a33b153e7794a7567d21d9041bbc75545b1d6822" ||
    error("unexpected Octopus tree")
isempty(OCTOPUS_STATUS) || error("Octopus checkout must be clean")

function parse_args(args)
    out = Dict{String,String}()
    i = 1
    while i <= length(args)
        startswith(args[i], "--") || error("expected --key, got $(args[i])")
        i == length(args) && error("missing value after $(args[i])")
        out[args[i][3:end]] = args[i + 1]
        i += 2
    end
    return out
end

args = parse_args(ARGS)
required = ("case-id", "turns", "n-macro", "grid", "offset-sigma", "seed")
# --nslices added 2026-08-12: the frozen supplement runner hardcoded 1; the
# multislice figure arms (5/9/15 slices) used a parameterized descendant
# that was never archived. This restores the parameter.
for key in required
    haskey(args, key) || error("missing --$(key)")
end

case_id = args["case-id"]
occursin(r"^[a-z0-9_]+$", case_id) || error("unsafe case id $(repr(case_id))")
turns = parse(Int, args["turns"])
n_macro = parse(Int, args["n-macro"])
grid_n = parse(Int, args["grid"])
offset_sigma = parse(Float64, args["offset-sigma"])
seed = parse(Int, args["seed"])
device = parse(Int, get(args, "device", "0"))
turns > 0 || error("turns must be positive")
n_macro > 0 || error("n-macro must be positive")
grid_n >= 5 || error("grid must be at least 5")
offset_sigma > 0 || error("offset-sigma must be positive")

include(joinpath(OCTOPUS_ROOT, "src", "Octopus.jl"))
using .Octopus
import CUDA

CUDA.functional(true) || error("CUDA.functional(true) is false")
CUDA.device!(device)
CUDA.allowscalar(false)

const XI = 0.005
const ENERGY = 10.0e9
# --sigz added 2026-08-12 with --nslices: the multislice deck runs a LONG
# bunch (0.275 m, sigma_z/beta* ~ 0.5) where the frozen single-slice runner
# hardcoded 0.007. beta_z tracks sigma_z at fixed dp/p = 5.5e-4.
sigz = parse(Float64, get(args, "sigz", "0.7e-2"))
const BETA = (0.55, 0.55, sigz / 5.5e-4)
const SIGMA = (106.0e-6, 106.0e-6, sigz)
const TUNE = (0.31, 0.32, -0.01)
const CUTOFF = 5.0

gamma_rel = ENERGY / EMASS_EV
r0 = RE * ME0 / EMASS_EV
npart = XI * 4pi * gamma_rel * SIGMA[1]^2 / (r0 * BETA[1])
xi_x = npart * r0 * BETA[1] / (4pi * gamma_rel * SIGMA[1]^2)
xi_y = npart * r0 * BETA[2] / (4pi * gamma_rel * SIGMA[2]^2)

policy = CUDAExecutionPolicy(
    device=device,
    launch=CUDALaunchConfig(threads=256, blocks=:auto),
)
set_global_rng!(seed=seed, method=:philox)

offset1 = (
    offset_sigma * SIGMA[1], 0.0,
    offset_sigma * SIGMA[2], 0.0,
    0.0, 0.0,
)
beam1 = Beam(n_macro, policy, Float64;
    beta=BETA, alpha=(0.0, 0.0, 0.0), sigma=SIGMA, cutoff=CUTOFF,
    rng_id=1, charge=-1.0, mc2=EMASS_EV, E0=ENERGY, r0=r0,
    npart=npart, initial_offset=offset1)
beam2 = Beam(n_macro, policy, Float64;
    beta=BETA, alpha=(0.0, 0.0, 0.0), sigma=SIGMA, cutoff=CUTOFF,
    rng_id=2, charge=+1.0, mc2=EMASS_EV, E0=ENERGY, r0=r0,
    npart=npart)

nslices = parse(Int, get(args, "nslices", "1"))
slicing = LongitudinalSlicing(
    method=:normal_quantile,
    nslices=nslices,
    center_position=:centroid,
)
solver = PICPoissonSolver(
    slicing=slicing,
    grid=(grid_n, grid_n),
    deposit_method=:CIC,
    green_type=:integrated,
    green_cache=:slice_pair,
    field_derivative=:second,
    slice_interpolation=:linear,
    interaction_grid=:slice_pair,
    grid_extent=:extrema,
    grid_extent_sigma=6.0,
    min_transverse_extent=(0.0, 0.0),
    grid_quantize=0.0,
    slice_pair_green_min_ratio=0.50,
    slice_pair_green_growth=0.25,
    longitudinal_kick=false,
    batch_mode=:wavefront,
    cuda_async=true,
    cuda_batch_fft=true,
    cuda_wavefront_fft=true,
    cuda_indexed_wavefront=true,
    luminosity_grid=nothing,
    luminosity_deposit_method=nothing,
    luminosity_schedule=nothing,
)
ip = StrongStrongCollision(:ip; poisson_solver=solver)
one_turn = Linear6DSpec{Float64}(
    beta1=BETA,
    beta2=BETA,
    alpha1=(0.0, 0.0, 0.0),
    alpha2=(0.0, 0.0, 0.0),
    dmu=2pi .* TUNE,
)
task = StrongStrongTask((ip, one_turn), (ip, one_turn); policy=policy)

raw_path = joinpath(OUTPUT_ROOT, "raw", case_id * ".tsv")
config_path = joinpath(OUTPUT_ROOT, "configs", case_id * ".tsv")
report_path = joinpath(OUTPUT_ROOT, "configs", case_id * ".configuration.txt")
mkpath(dirname(raw_path))
mkpath(dirname(config_path))

function device_mean(values)
    return Float64(sum(values) / length(values))
end

function write_config(status, elapsed, completed_turns, error_text="")
    pairs = [
        "case_id" => case_id,
        "status" => status,
        "timestamp_utc" => string(now(UTC)),
        "octopus_commit" => OCTOPUS_COMMIT,
        "octopus_tree" => OCTOPUS_TREE,
        "julia_version" => string(VERSION),
        "cuda_jl_version" => string(pkgversion(CUDA)),
        "cuda_runtime" => string(CUDA.runtime_version()),
        "cuda_driver" => string(CUDA.driver_version()),
        "cuda_device" => string(device),
        "cuda_device_name" => CUDA.name(CUDA.device()),
        "float_type" => "Float64",
        "turns_requested" => string(turns),
        "turns_completed" => string(completed_turns),
        "n_macro_per_beam" => string(n_macro),
        "grid" => "$(grid_n)x$(grid_n)",
        "offset_sigma" => string(offset_sigma),
        "seed" => string(seed),
        "rng_method" => "philox",
        "rng_id_beam1" => "1",
        "rng_id_beam2" => "2",
        "xi_x" => repr(xi_x),
        "xi_y" => repr(xi_y),
        "npart" => repr(npart),
        "solver" => "PICPoissonSolver",
        "deposit_method" => "CIC",
        "green_type" => "integrated",
        "green_cache" => "slice_pair",
        "field_derivative" => "second",
        "slice_interpolation" => "linear",
        "interaction_grid" => "slice_pair",
        "grid_extent" => "extrema",
        "slice_pair_green_min_ratio" => "0.50",
        "slice_pair_green_growth" => "0.25",
        "longitudinal_kick" => "false",
        "batch_mode" => "wavefront",
        "cuda_async" => "true",
        "cuda_batch_fft" => "true",
        "cuda_wavefront_fft" => "true",
        "cuda_indexed_wavefront" => "true",
        "luminosity_schedule" => "every_turn_default",
        "elapsed_seconds" => repr(elapsed),
        "error" => replace(error_text, '\n' => ' '),
    ]
    open(config_path, "w") do io
        println(io, "key\tvalue")
        for (key, value) in pairs
            println(io, key, '\t', value)
        end
    end
end

open(report_path, "w") do io
    println(io, "configuration_report(task, beam1, beam2):")
    show(io, MIME("text/plain"), configuration_report(task, beam1, beam2))
    println(io)
    println(io, "\nsolver repr:")
    show(io, MIME("text/plain"), solver)
    println(io)
end

println("case=$(case_id) turns=$(turns) n_macro=$(n_macro) grid=$(grid_n)x$(grid_n) offset=$(offset_sigma) seed=$(seed)")
println("Octopus commit ", OCTOPUS_COMMIT)
println("Julia $(VERSION), CUDA.jl $(pkgversion(CUDA)), runtime $(CUDA.runtime_version()), driver $(CUDA.driver_version())")
println("device $(device): $(CUDA.name(CUDA.device()))")
println("xi=($(repr(xi_x)), $(repr(xi_y))) npart=$(repr(npart))")
flush(stdout)

completed = Ref(0)
started_ns = time_ns()
write_config("started", 0.0, completed[])

try
    open(raw_path, "w") do io
        println(io, "# case_id=$(case_id)")
        println(io, "# records include initial turn 0; primary estimator uses turns 1..N")
        println(io, "# units: centroids in metres")
        println(io, "turn\tx1\tx2\ty1\ty2")
        @printf(io, "%d\t%.17g\t%.17g\t%.17g\t%.17g\n", 0,
                device_mean(beam1.rep.x), device_mean(beam2.rep.x),
                device_mean(beam1.rep.y), device_mean(beam2.rep.y))
        flush(io)
        for turn in 1:turns
            execute!(task, beam1, beam2; turns=1)
            @printf(io, "%d\t%.17g\t%.17g\t%.17g\t%.17g\n", turn,
                    device_mean(beam1.rep.x), device_mean(beam2.rep.x),
                    device_mean(beam1.rep.y), device_mean(beam2.rep.y))
            completed[] = turn
            if turn % 256 == 0
                flush(io)
            end
            if turn % 1024 == 0 || turn == turns
                elapsed = (time_ns() - started_ns) / 1.0e9
                println("progress $(turn)/$(turns), elapsed=$(round(elapsed; digits=1)) s")
                flush(stdout)
            end
        end
    end
    CUDA.synchronize()
    elapsed = (time_ns() - started_ns) / 1.0e9
    write_config("completed", elapsed, completed[])
    println("completed $(case_id) in $(round(elapsed; digits=3)) s; raw=$(raw_path)")
catch err
    elapsed = (time_ns() - started_ns) / 1.0e9
    detail = sprint(showerror, err, catch_backtrace())
    write_config("failed", elapsed, completed[], detail)
    println(stderr, detail)
    rethrow()
end
