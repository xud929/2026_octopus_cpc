#!/usr/bin/env julia
#=
GPU wall-time table (manuscript Sec. "Benchmark and scaling").

Protocol, pinned here because the submitted campaign was never archived:
five configurations of the EIC crab-crossing production case (Octopus
test/examples/strong_strong_tracking.jl -- luminosity output every turn and
two HDF5 moment observers, exactly the observers the text describes).  Each
configuration is measured over independent PROCESSES (5 for the nominal
case, 3 otherwise).  Each process tracks WARMUP+WINDOW turns and reports the
MEDIAN s/turn over the window (turns WARMUP+1 .. WARMUP+WINDOW, 1-based);
compilation and CUDA context setup land in the warm-up.  With
OCTOPUS_MOMENT_CAPACITY=64 the two moment observers flush to HDF5 once
inside the window (buffer fills at turn 64; the next fill, 128, is outside),
so the window includes exactly one HDF5 observer flush, as the table caption
states.  The table entry is mean +- sample SD across the process medians.

Requires env:
  OCTOPUS_ROOT             clean Octopus checkout (worktree) to evaluate
  OCTOPUS_EXPECTED_COMMIT  full hash the run must be at (provenance guard)
Optional:
  PERF_OUT       output TSV (default: data/gpu_walltime_table.tsv)
  PERF_WORK      per-process logs/timings dir (default: work/perf)

The GPU must be otherwise idle; the driver aborts if nvidia-smi shows a
compute process before starting.
=#

using Printf
using Statistics

const ROOT = normpath(joinpath(@__DIR__, ".."))
const OCTOPUS_ROOT = get(ENV, "OCTOPUS_ROOT") do
    error("set OCTOPUS_ROOT to the evaluated Octopus checkout")
end
git(args...) = strip(read(`git -C $OCTOPUS_ROOT $(args)`, String))
const COMMIT = git("rev-parse", "HEAD")
const EXPECTED = get(ENV, "OCTOPUS_EXPECTED_COMMIT") do
    error("set OCTOPUS_EXPECTED_COMMIT to the full hash the run should use")
end
COMMIT == EXPECTED || error("unexpected Octopus commit: $COMMIT != $EXPECTED")
isempty(git("status", "--porcelain=v1")) || error("Octopus checkout must be clean")

const WARMUP = 20
const WINDOW = 100
const TURNS = WARMUP + WINDOW

const CONFIGS = [
    (id = "half_pop",       ele = 1_280_000, pro =   512_000, grid = 128, procs = 3),
    (id = "nominal_mesh64", ele = 2_560_000, pro = 1_024_000, grid =  64, procs = 3),
    (id = "nominal",        ele = 2_560_000, pro = 1_024_000, grid = 128, procs = 5),
    (id = "nominal_mesh256",ele = 2_560_000, pro = 1_024_000, grid = 256, procs = 3),
    (id = "double_pop",     ele = 5_120_000, pro = 2_048_000, grid = 128, procs = 3),
]

const WORK = get(ENV, "PERF_WORK", joinpath(ROOT, "work", "perf"))
const OUT = get(ENV, "PERF_OUT", joinpath(ROOT, "data", "gpu_walltime_table.tsv"))
mkpath(WORK)

# The submitted campaign tolerated an IDLE foreign CUDA context (documented
# in the manuscript: ~3.29 GiB, zero utilization). Reproduce that condition:
# abort only if the device shows actual activity; otherwise record the
# ambient contexts in the output header.
ambient = strip(read(`nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader`, String))
utils = Int[]
for _ in 1:3
    push!(utils, parse(Int, strip(read(
        `nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits`, String))))
    sleep(2)
end
maximum(utils) <= 5 || error(
    "GPU active (utilization sample $(utils)%; compute apps: $(ambient)); " *
    "measure on a quiet device")

device_name = strip(read(`nvidia-smi --query-gpu=name --format=csv,noheader`, String))
driver_ver = strip(read(`nvidia-smi --query-gpu=driver_version --format=csv,noheader`, String))

function run_process(cfg, p)
    tpath = joinpath(WORK, "$(cfg.id)_p$(p).tsv")
    lpath = joinpath(WORK, "$(cfg.id)_p$(p).log")
    env = copy(ENV)
    env["OCTOPUS_USE_GPU"] = "1"
    env["OCTOPUS_TURNS"] = string(TURNS)
    env["OCTOPUS_N_MACRO_ELE"] = string(cfg.ele)
    env["OCTOPUS_N_MACRO_PRO"] = string(cfg.pro)
    env["OCTOPUS_PIC_GRID"] = "$(cfg.grid),$(cfg.grid)"
    env["OCTOPUS_MOMENT_CAPACITY"] = "64"
    env["OCTOPUS_RECORD_TURN_TIMES"] = "1"
    env["OCTOPUS_TURN_TIMING_PATH"] = tpath
    cmd = setenv(`julia --startup-file=no --project=$OCTOPUS_ROOT
                  $(joinpath(OCTOPUS_ROOT, "test", "examples", "strong_strong_tracking.jl"))`,
                 env)
    open(lpath, "w") do io
        run(pipeline(cmd; stdout = io, stderr = io))
    end
    rows = [split(l, '\t') for l in readlines(tpath)[2:end]]
    secs = [parse(Float64, r[2]) for r in rows]
    length(secs) == TURNS || error("$(cfg.id) p$(p): $(length(secs)) turns, wanted $TURNS")
    med = median(secs[(WARMUP + 1):TURNS])
    @printf("  %s process %d: median %.4f s/turn (window %d..%d)\n",
            cfg.id, p, med, WARMUP + 1, TURNS)
    flush(stdout)
    return med
end

results = []
for cfg in CONFIGS
    @printf("== %s: ele=%d pro=%d grid=%d^2, %d processes\n",
            cfg.id, cfg.ele, cfg.pro, cfg.grid, cfg.procs)
    flush(stdout)
    medians = [run_process(cfg, p) for p in 1:cfg.procs]
    m = mean(medians)
    s = std(medians)
    push!(results, (cfg = cfg, medians = medians, mean = m, sd = s))
    @printf("== %s: %.4f +- %.4f s/turn\n", cfg.id, m, s)
    flush(stdout)
end

open(OUT, "w") do io
    println(io, "# Measured GPU wall time per turn, EIC crab-crossing production case,")
    println(io, "# luminosity output every turn + two HDF5 moment observers (capacity 64:")
    println(io, "# exactly one flush inside each measured window).")
    println(io, "# Per process: $(TURNS) turns, median over turns $(WARMUP + 1)..$(TURNS)")
    println(io, "# (first $(WARMUP) are warm-up). Entry = mean +- sample SD across")
    println(io, "# independent process medians (5 nominal, 3 others).")
    println(io, "# Octopus commit $(COMMIT)")
    println(io, "# device: $(device_name), driver $(driver_ver)")
    println(io, "# julia: $(VERSION)")
    println(io, "# ambient idle CUDA contexts during measurement (pid, memory): ",
            isempty(ambient) ? "none" : replace(ambient, '\n' => "; "))
    println(io, "config\ttotal_particles\tmesh\tprocesses\tmean_s_per_turn\tsd_s_per_turn\tprocess_medians")
    for r in results
        total = r.cfg.ele + r.cfg.pro
        @printf(io, "%s\t%.2e\t%d\t%d\t%.4f\t%.4f\t%s\n",
                r.cfg.id, total, r.cfg.grid, r.cfg.procs, r.mean, r.sd,
                join([@sprintf("%.4f", x) for x in r.medians], ","))
    end
end
println("wrote ", OUT)
