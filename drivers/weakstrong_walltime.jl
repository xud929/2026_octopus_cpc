#!/usr/bin/env julia
#=
Weak-strong companion wall time on the local GPU (manuscript Sec.
"Benchmark and scaling", A100 comparison sentence).

Loads the Octopus weak-strong example harness (which builds the EIC
weak-strong case with every-turn luminosity output and an every-turn moment
observer), lets its one-turn execution compile the pipeline, then times
five 100-turn windows on the live task after a 20-turn warm-up and reports
the per-window means and their median.  Timing only; the counter-based
excitation replay on re-execute! does not change the work per turn.

Env: OCTOPUS_ROOT, OCTOPUS_EXPECTED_COMMIT (provenance pin),
     OCTOPUS_N_MACRO (default 1024000).
=#

const OCTOPUS_ROOT = get(ENV, "OCTOPUS_ROOT") do
    error("set OCTOPUS_ROOT to the evaluated Octopus checkout")
end
git(args...) = strip(read(`git -C $OCTOPUS_ROOT $(args)`, String))
const EXPECTED = get(ENV, "OCTOPUS_EXPECTED_COMMIT") do
    error("set OCTOPUS_EXPECTED_COMMIT")
end
git("rev-parse", "HEAD") == EXPECTED || error("unexpected Octopus commit")
isempty(git("status", "--porcelain=v1")) || error("checkout must be clean")

ENV["OCTOPUS_TURNS"] = "1"
ENV["OCTOPUS_N_MACRO"] = get(ENV, "OCTOPUS_N_MACRO", "1024000")
ENV["OCTOPUS_USE_GPU"] = "1"

include(joinpath(OCTOPUS_ROOT, "test", "examples", "weak_strong_tracking.jl"))

using Statistics

execute!(task, beam; turns = 20)          # warm-up on the compiled pipeline
windows = Float64[]
for _ in 1:5
    push!(windows, @elapsed(execute!(task, beam; turns = 100)) / 100)
end
println("commit ", EXPECTED)
println("n_macro ", ENV["OCTOPUS_N_MACRO"])
println("window means (ms/turn): ",
        join([string(round(1e3 * w; digits = 3)) for w in windows], ", "))
println("median ms/turn = ", round(1e3 * median(windows); digits = 3))
