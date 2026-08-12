#!/usr/bin/env julia

using Statistics
import FFTW

const ROOT = normpath(joinpath(@__DIR__, "..", "..", "validation", "round_modes"))
const RAW = joinpath(ROOT, "raw")
const TABLES = joinpath(ROOT, "tables")
const BB3D = joinpath(ROOT, "raw", "beambeam3d")
const XI = 0.005
const BB3D_XI_DECK = 0.0049932095
const Q0 = Dict("x" => 0.31, "y" => 0.32)

function read_cases()
    return read_tsv_dicts(joinpath(ROOT, "cases.tsv"))
end

function read_tsv_dicts(path)
    lines = readlines(path)
    header = split(lines[1], '\t')
    return [Dict(header .=> split(line, '\t')) for line in lines[2:end] if !isempty(line)]
end

function read_octopus(case_id)
    turns = Int[]
    x1 = Float64[]; x2 = Float64[]; y1 = Float64[]; y2 = Float64[]
    for line in eachline(joinpath(RAW, case_id * ".tsv"))
        (startswith(line, "#") || startswith(line, "turn")) && continue
        fields = split(line)
        push!(turns, parse(Int, fields[1]))
        push!(x1, parse(Float64, fields[2])); push!(x2, parse(Float64, fields[3]))
        push!(y1, parse(Float64, fields[4])); push!(y2, parse(Float64, fields[5]))
    end
    turns == collect(0:(length(turns) - 1)) || error("non-contiguous turns in $(case_id)")
    return Dict("turn" => turns, "x1" => x1, "x2" => x2, "y1" => y1, "y2" => y2)
end

function read_bb3d(path)
    turns = Int[]
    values = Float64[]
    for line in eachline(path)
        isempty(strip(line)) && continue
        fields = split(line)
        push!(turns, round(Int, parse(Float64, fields[1])))
        push!(values, parse(Float64, fields[2]))
    end
    return turns, values
end

function mode_peak(signal, q0, mode)
    n = length(signal)
    j = collect(0:(n - 1))
    window = 0.5 .- 0.5 .* cos.(2pi .* j ./ n)
    amplitude = abs.(FFTW.rfft((signal .- mean(signal)) .* window))
    frequency = collect(0:(length(amplitude) - 1)) ./ n
    low, high = if mode == "sigma"
        (q0 - 0.5XI, q0 + 0.5XI)
    elseif mode == "pi"
        (q0 + 0.5XI, q0 + 2.0XI)
    else
        error("unknown mode $(mode)")
    end
    indices = findall(q -> low <= q <= high, frequency)
    k = indices[argmax(view(amplitude, indices))]
    a1, a2, a3 = amplitude[k - 1], amplitude[k], amplitude[k + 1]
    denominator = a1 - 2a2 + a3
    delta = denominator == 0 ? 0.0 : 0.5 * (a1 - a3) / denominator
    noise_indices = filter(i -> abs(i - k) > 3, indices)
    noise = median(view(amplitude, noise_indices))
    snr = noise == 0 ? Inf : amplitude[k] / noise
    local_max = a2 >= a1 && a2 >= a3
    away_from_edge = indices[2] <= k <= indices[end - 1]
    delta_ok = abs(delta) <= 1.0
    snr_ok = snr >= 10.0
    return Dict{String,Any}(
        "q" => ((k - 1) + delta) / n,
        "bin" => k - 1,
        "delta_bin" => delta,
        "peak" => amplitude[k],
        "noise_median" => noise,
        "snr" => snr,
        "valid" => local_max && away_from_edge && delta_ok && snr_ok,
        "local_max" => local_max,
        "away_from_edge" => away_from_edge,
        "delta_ok" => delta_ok,
        "snr_ok" => snr_ok,
        "window_low" => low,
        "window_high" => high,
        "n" => n,
        "bin_width" => 1.0 / n,
    )
end

function analyze_signals(case_id, view_name, source, start_turn, stop_turn; xi=XI)
    indices = findall(t -> start_turn <= t <= stop_turn, source["turn"])
    n = length(indices)
    n == stop_turn - start_turn + 1 || error(
        "$(case_id)/$(view_name): expected $(stop_turn-start_turn+1), got $(n)")
    out = Dict{String,Any}[]
    for plane in ("x", "y")
        c1 = source[plane * "1"][indices]
        c2 = source[plane * "2"][indices]
        sigma = mode_peak(c1 .+ c2, Q0[plane], "sigma")
        pi_mode = mode_peak(c1 .- c2, Q0[plane], "pi")
        valid = sigma["valid"] && pi_mode["valid"] && pi_mode["q"] > sigma["q"]
        push!(out, Dict{String,Any}(
            "case_id" => case_id,
            "view" => view_name,
            "plane" => plane,
            "start_turn" => start_turn,
            "stop_turn" => stop_turn,
            "n_records" => n,
            "bin_width" => 1.0 / n,
            "q_sigma" => sigma["q"],
            "q_pi" => pi_mode["q"],
            "lambda" => (pi_mode["q"] - sigma["q"]) / xi,
            "xi_normalization" => xi,
            "sigma_bin" => sigma["bin"],
            "pi_bin" => pi_mode["bin"],
            "sigma_delta_bin" => sigma["delta_bin"],
            "pi_delta_bin" => pi_mode["delta_bin"],
            "sigma_snr" => sigma["snr"],
            "pi_snr" => pi_mode["snr"],
            "sigma_valid" => sigma["valid"],
            "pi_valid" => pi_mode["valid"],
            "mode_pair_valid" => valid,
        ))
    end
    return out
end

function bb3d_source()
    paths = Dict("x1" => "fort.24", "y1" => "fort.25",
                 "x2" => "fort.34", "y2" => "fort.35")
    parsed = Dict(key => read_bb3d(joinpath(BB3D, name)) for (key, name) in paths)
    turns = parsed["x1"][1]
    for (key, (other_turns, _)) in parsed
        other_turns == turns || error("BeamBeam3D turn mismatch in $(key)")
    end
    return Dict("turn" => turns,
                (key => parsed[key][2] for key in ("x1", "x2", "y1", "y2"))...)
end

function format_value(value)
    value isa Float64 && return repr(value)
    return string(value)
end

function write_tsv(path, rows, fields)
    open(path, "w") do io
        println(io, join(fields, '\t'))
        for row in rows
            println(io, join((format_value(row[field]) for field in fields), '\t'))
        end
    end
end

function lookup(results, case_id, view_name, plane)
    matches = filter(row -> row["case_id"] == case_id && row["view"] == view_name &&
                            row["plane"] == plane, results)
    length(matches) == 1 || error("lookup mismatch: $((case_id, view_name, plane, length(matches)))")
    return only(matches)
end

function main()
    mkpath(TABLES)
    cases = read_cases()
    results = Dict{String,Any}[]
    for case in cases
        case_id = case["case_id"]
        source = read_octopus(case_id)
        turns = parse(Int, case["turns"])
        if turns == 16384
            append!(results, analyze_signals(case_id, "prefix8192", source, 1, 8192))
            append!(results, analyze_signals(case_id, "second8192", source, 8193, 16384))
            append!(results, analyze_signals(case_id, "full16384", source, 1, 16384))
        else
            append!(results, analyze_signals(case_id, "full8192", source, 1, 8192))
        end
    end

    bb3d = bb3d_source()
    append!(results, analyze_signals("beambeam3d", "turns1_8192_nominal_xi", bb3d, 1, 8192; xi=XI))
    append!(results, analyze_signals("beambeam3d", "turns0_8191_nominal_xi", bb3d, 0, 8191; xi=XI))
    append!(results, analyze_signals("beambeam3d", "turns1_8192_deck_xi", bb3d, 1, 8192; xi=BB3D_XI_DECK))

    spectral_fields = ["case_id", "view", "plane", "start_turn", "stop_turn",
        "n_records", "bin_width", "q_sigma", "q_pi", "lambda", "xi_normalization",
        "sigma_bin", "pi_bin", "sigma_delta_bin", "pi_delta_bin", "sigma_snr",
        "pi_snr", "sigma_valid", "pi_valid", "mode_pair_valid"]
    write_tsv(joinpath(TABLES, "spectral_results.tsv"), results, spectral_fields)

    baseline_cases = [
        ("baseline_s20260727_t16384", "prefix8192"),
        ("baseline_s20260728_t8192", "full8192"),
        ("baseline_s20260729_t8192", "full8192"),
    ]
    baseline_summary = Dict{String,Any}[]
    t975_df2 = 4.302652729911275
    for plane in ("x", "y")
        values = [lookup(results, case_id, view_name, plane)["lambda"]
                  for (case_id, view_name) in baseline_cases]
        value_mean = mean(values)
        value_sd = std(values)
        sem = value_sd / sqrt(length(values))
        push!(baseline_summary, Dict{String,Any}(
            "plane" => plane,
            "n_seeds" => length(values),
            "mean_lambda" => value_mean,
            "sample_sd" => value_sd,
            "minimum" => minimum(values),
            "maximum" => maximum(values),
            "range" => maximum(values) - minimum(values),
            "t95_low_df2" => value_mean - t975_df2 * sem,
            "t95_high_df2" => value_mean + t975_df2 * sem,
            "all_modes_valid" => all(lookup(results, case_id, view_name, plane)["mode_pair_valid"]
                                     for (case_id, view_name) in baseline_cases),
        ))
    end
    baseline_fields = ["plane", "n_seeds", "mean_lambda", "sample_sd", "minimum",
        "maximum", "range", "t95_low_df2", "t95_high_df2", "all_modes_valid"]
    write_tsv(joinpath(TABLES, "baseline_seed_summary.tsv"), baseline_summary, baseline_fields)

    base_case, base_view = baseline_cases[1]
    axes = [
        ("mesh", [("64", "mesh64_s20260727_t8192", "full8192"),
                  ("128", base_case, base_view),
                  ("256", "mesh256_s20260727_t8192", "full8192")]),
        ("n_macro", [("50000", "nmacro50000_s20260727_t8192", "full8192"),
                     ("100000", base_case, base_view),
                     ("200000", "nmacro200000_s20260727_t8192", "full8192")]),
        ("offset_sigma", [("0.025", "offset0025_s20260727_t8192", "full8192"),
                          ("0.05", "offset0050_s20260727_t8192", "full8192"),
                          ("0.1", base_case, base_view)]),
        ("record_length", [("8192_prefix", base_case, "prefix8192"),
                           ("8192_second", base_case, "second8192"),
                           ("16384_full", base_case, "full16384")]),
    ]
    baseline_sd = Dict(row["plane"] => row["sample_sd"] for row in baseline_summary)
    sensitivity = Dict{String,Any}[]
    for (axis, entries) in axes
        for plane in ("x", "y")
            base_lambda = lookup(results, base_case, base_view, plane)["lambda"]
            values = Float64[]
            new_rows = Dict{String,Any}[]
            for (level, case_id, view_name) in entries
                result = lookup(results, case_id, view_name, plane)
                push!(values, result["lambda"])
                delta = result["lambda"] - base_lambda
                push!(new_rows, Dict{String,Any}(
                    "axis" => axis,
                    "level" => level,
                    "case_id" => case_id,
                    "view" => view_name,
                    "plane" => plane,
                    "lambda" => result["lambda"],
                    "delta_from_seedA_8192_baseline" => delta,
                    "abs_delta_over_baseline_seed_sd" => baseline_sd[plane] > 0 ?
                        abs(delta) / baseline_sd[plane] : Inf,
                    "mode_pair_valid" => result["mode_pair_valid"],
                ))
            end
            envelope = maximum(values) - minimum(values)
            for row in new_rows
                row["axis_envelope"] = envelope
            end
            append!(sensitivity, new_rows)
        end
    end
    sensitivity_fields = ["axis", "level", "case_id", "view", "plane", "lambda",
        "delta_from_seedA_8192_baseline", "abs_delta_over_baseline_seed_sd",
        "mode_pair_valid", "axis_envelope"]
    write_tsv(joinpath(TABLES, "sensitivity_summary.tsv"), sensitivity, sensitivity_fields)

    oct_mean = Dict(row["plane"] => row["mean_lambda"] for row in baseline_summary)
    oct_sd = Dict(row["plane"] => row["sample_sd"] for row in baseline_summary)
    comparison = Dict{String,Any}[]
    for view_name in ("turns1_8192_nominal_xi", "turns0_8191_nominal_xi", "turns1_8192_deck_xi")
        for plane in ("x", "y")
            result = lookup(results, "beambeam3d", view_name, plane)
            delta = result["lambda"] - oct_mean[plane]
            push!(comparison, Dict{String,Any}(
                "bb3d_view" => view_name,
                "plane" => plane,
                "octopus_baseline_mean" => oct_mean[plane],
                "octopus_baseline_sample_sd" => oct_sd[plane],
                "bb3d_lambda" => result["lambda"],
                "bb3d_minus_octopus" => delta,
                "abs_difference_over_octopus_seed_sd" => oct_sd[plane] > 0 ?
                    abs(delta) / oct_sd[plane] : Inf,
                "bb3d_mode_pair_valid" => result["mode_pair_valid"],
            ))
        end
    end
    comparison_fields = ["bb3d_view", "plane", "octopus_baseline_mean",
        "octopus_baseline_sample_sd", "bb3d_lambda", "bb3d_minus_octopus",
        "abs_difference_over_octopus_seed_sd", "bb3d_mode_pair_valid"]
    write_tsv(joinpath(TABLES, "beambeam3d_comparison.tsv"), comparison, comparison_fields)

    primary_cases = [
        ("baseline_s20260727_t16384", "prefix8192"),
        ("baseline_s20260728_t8192", "full8192"),
        ("baseline_s20260729_t8192", "full8192"),
        ("mesh64_s20260727_t8192", "full8192"),
        ("mesh256_s20260727_t8192", "full8192"),
        ("nmacro50000_s20260727_t8192", "full8192"),
        ("nmacro200000_s20260727_t8192", "full8192"),
        ("offset0025_s20260727_t8192", "full8192"),
        ("offset0050_s20260727_t8192", "full8192"),
    ]
    headline = Dict{String,Any}[]
    for plane in ("x", "y")
        primary_values = [lookup(results, case_id, view_name, plane)["lambda"]
                          for (case_id, view_name) in primary_cases]
        mesh64 = lookup(results, "mesh64_s20260727_t8192", "full8192", plane)["lambda"]
        mesh128 = lookup(results, base_case, base_view, plane)["lambda"]
        mesh256 = lookup(results, "mesh256_s20260727_t8192", "full8192", plane)["lambda"]
        n50 = lookup(results, "nmacro50000_s20260727_t8192", "full8192", plane)["lambda"]
        n200 = lookup(results, "nmacro200000_s20260727_t8192", "full8192", plane)["lambda"]
        off025 = lookup(results, "offset0025_s20260727_t8192", "full8192", plane)["lambda"]
        off05 = lookup(results, "offset0050_s20260727_t8192", "full8192", plane)["lambda"]
        full16 = lookup(results, base_case, "full16384", plane)["lambda"]
        second8 = lookup(results, base_case, "second8192", plane)["lambda"]
        bb = lookup(results, "beambeam3d", "turns1_8192_nominal_xi", plane)["lambda"]
        octopus_rows = filter(row -> row["case_id"] != "beambeam3d", results)
        min_snr = minimum(min(row["sigma_snr"], row["pi_snr"])
                          for row in octopus_rows if row["plane"] == plane)
        push!(headline, Dict{String,Any}(
            "plane" => plane,
            "baseline_mean" => oct_mean[plane],
            "baseline_sample_sd" => oct_sd[plane],
            "required_8192_primary_minimum" => minimum(primary_values),
            "required_8192_primary_maximum" => maximum(primary_values),
            "required_8192_primary_envelope" => maximum(primary_values) - minimum(primary_values),
            "mesh64" => mesh64,
            "mesh128_seedA" => mesh128,
            "mesh256" => mesh256,
            "mesh256_minus_mesh128" => mesh256 - mesh128,
            "nmacro50000" => n50,
            "nmacro100000_seedA" => mesh128,
            "nmacro200000" => n200,
            "nmacro200000_minus_100000" => n200 - mesh128,
            "offset0025" => off025,
            "offset0050" => off05,
            "offset0100_seedA" => mesh128,
            "offset0025_minus_0100" => off025 - mesh128,
            "record_prefix8192" => mesh128,
            "record_second8192" => second8,
            "record_full16384" => full16,
            "record_full16384_minus_prefix8192" => full16 - mesh128,
            "beambeam3d_nominal_xi" => bb,
            "beambeam3d_minus_baseline_mean" => bb - oct_mean[plane],
            "minimum_octopus_mode_snr" => min_snr,
        ))
    end
    headline_fields = ["plane", "baseline_mean", "baseline_sample_sd",
        "required_8192_primary_minimum", "required_8192_primary_maximum",
        "required_8192_primary_envelope", "mesh64", "mesh128_seedA", "mesh256",
        "mesh256_minus_mesh128", "nmacro50000", "nmacro100000_seedA", "nmacro200000",
        "nmacro200000_minus_100000", "offset0025", "offset0050", "offset0100_seedA",
        "offset0025_minus_0100", "record_prefix8192", "record_second8192",
        "record_full16384", "record_full16384_minus_prefix8192",
        "beambeam3d_nominal_xi", "beambeam3d_minus_baseline_mean",
        "minimum_octopus_mode_snr"]
    write_tsv(joinpath(TABLES, "headline_summary.tsv"), headline, headline_fields)

    failures = filter(row -> !row["mode_pair_valid"], results)
    println("wrote $(length(results)) plane/view spectral rows")
    println("mode-identification failures: $(length(failures))")
    for row in failures
        println(join((row["case_id"], row["view"], row["plane"],
                      row["sigma_snr"], row["pi_snr"]), '\t'))
    end
end

if abspath(PROGRAM_FILE) == @__FILE__
    main()
end
