#!/usr/bin/env julia
#=
Green-cache ablation at the nominal production point (manuscript Sec. 6.1).

Same protocol as drivers/perf_walltime.jl (120 turns/process, median over
turns 21..120, moment capacity 64, three processes per configuration), at
the nominal size (2.56M/1.024M, 128^2), comparing:
  none        green_cache = :none (Green FFTs rebuilt for every pair)
  default     :slice_pair, min_ratio 0.50, growth 0.25
  tight       :slice_pair, min_ratio 0.95, growth 0.05 (production)

Env: OCTOPUS_ROOT, OCTOPUS_EXPECTED_COMMIT.  Output:
data/green_cache_ablation.tsv.
=#

using Printf
using Statistics

const ROOT = normpath(joinpath(@__DIR__, ".."))
const OCTOPUS_ROOT = get(ENV, "OCTOPUS_ROOT") do
    error("set OCTOPUS_ROOT")
end
git(args...) = strip(read(`git -C $OCTOPUS_ROOT $(args)`, String))
const COMMIT = git("rev-parse", "HEAD")
COMMIT == get(ENV, "OCTOPUS_EXPECTED_COMMIT") do
    error("set OCTOPUS_EXPECTED_COMMIT")
end || error("unexpected Octopus commit")
isempty(git("status", "--porcelain=v1")) || error("checkout must be clean")

const WARMUP, WINDOW = 20, 100
const TURNS = WARMUP + WINDOW
const PROCS = 3

const CONFIGS = [
    (id = "none",    cache = "none",       ratio = "",     growth = ""),
    (id = "default", cache = "slice_pair", ratio = "0.50", growth = "0.25"),
    (id = "tight",   cache = "slice_pair", ratio = "0.95", growth = "0.05"),
]

const WORK = joinpath(ROOT, "work", "greencache")
mkpath(WORK)

utils = Int[]
for _ in 1:3
    push!(utils, parse(Int, strip(read(
        `nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits`, String))))
    sleep(2)
end
maximum(utils) <= 5 || error("GPU active (utilization $(utils)%)")

function run_process(cfg, p)
    tpath = joinpath(WORK, "$(cfg.id)_p$(p).tsv")
    env = copy(ENV)
    env["OCTOPUS_USE_GPU"] = "1"
    env["OCTOPUS_TURNS"] = string(TURNS)
    env["OCTOPUS_N_MACRO_ELE"] = "2560000"
    env["OCTOPUS_N_MACRO_PRO"] = "1024000"
    env["OCTOPUS_MOMENT_CAPACITY"] = "64"
    env["OCTOPUS_RECORD_TURN_TIMES"] = "1"
    env["OCTOPUS_TURN_TIMING_PATH"] = tpath
    env["OCTOPUS_PIC_GREEN_CACHE"] = cfg.cache
    if cfg.cache == "slice_pair"
        env["OCTOPUS_CUDA_PIC_SLICE_PAIR_GREEN_MIN_RATIO"] = cfg.ratio
        env["OCTOPUS_CUDA_PIC_SLICE_PAIR_GREEN_GROWTH"] = cfg.growth
    end
    cmd = setenv(`julia --startup-file=no --project=$OCTOPUS_ROOT
                  $(joinpath(OCTOPUS_ROOT, "test", "examples", "strong_strong_tracking.jl"))`,
                 env)
    open(joinpath(WORK, "$(cfg.id)_p$(p).log"), "w") do io
        run(pipeline(cmd; stdout = io, stderr = io))
    end
    secs = [parse(Float64, split(l, '\t')[2]) for l in readlines(tpath)[2:end]]
    length(secs) == TURNS || error("$(cfg.id) p$(p): $(length(secs)) turns")
    med = median(secs[(WARMUP + 1):TURNS])
    @printf("  %s p%d: median %.4f s/turn\n", cfg.id, p, med)
    flush(stdout)
    return med
end

results = []
for cfg in CONFIGS
    @printf("== %s (cache=%s ratio=%s growth=%s)\n",
            cfg.id, cfg.cache, cfg.ratio, cfg.growth)
    flush(stdout)
    meds = [run_process(cfg, p) for p in 1:PROCS]
    push!(results, (cfg = cfg, meds = meds, mean = mean(meds), sd = std(meds)))
    @printf("== %s: %.4f +- %.4f s/turn\n", cfg.id, mean(meds), std(meds))
    flush(stdout)
end

open(joinpath(ROOT, "data", "green_cache_ablation.tsv"), "w") do io
    println(io, "# Green-cache ablation, nominal production point (2.56M/1.024M,")
    println(io, "# 128^2, 15 slices, every-turn luminosity + two moment observers).")
    println(io, "# Protocol as data/gpu_walltime_table.tsv: 120 turns/process,")
    println(io, "# median over turns 21..120, mean +- sample SD over 3 process medians.")
    println(io, "# Octopus commit $(COMMIT)")
    println(io, "config\tgreen_cache\tmin_ratio\tgrowth\tmean_s_per_turn\tsd_s_per_turn\tprocess_medians")
    for r in results
        @printf(io, "%s\t%s\t%s\t%s\t%.4f\t%.4f\t%s\n",
                r.cfg.id, r.cfg.cache,
                isempty(r.cfg.ratio) ? "-" : r.cfg.ratio,
                isempty(r.cfg.growth) ? "-" : r.cfg.growth,
                r.mean, r.sd, join([@sprintf("%.4f", m) for m in r.meds], ","))
    end
end
println("wrote data/green_cache_ablation.tsv")
