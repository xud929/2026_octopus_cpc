#!/usr/bin/env python3
"""Recompute every numerical claim in the submitted manuscript from data/.

Rescoped 2026-08-12: the previous version's phrase lists and frozen-snapshot
check policed the expanded working draft (nine figures, editing rounds 20-25);
the submitted CPC manuscript is a different, shorter document.  This version
derives each number the submitted paper actually states from the archived
data and asserts the manuscript states it.

Categories printed:
  DERIVED    - recomputed from archived data; the manuscript must state the
               recomputed value (a mismatch is a failure)
  FLAG       - two in-repo statements disagree with each other (failure)
  UNARCHIVED - claims whose source data is not in data/ (informational; these
               are single-run or supplement-era statements awaiting either
               regeneration or explicit acceptance)
  FIGURE/OFF-AXIS - structural figure checks (failures)

Whitespace is normalized before searching so LaTeX line-wrapping cannot hide
a phrase.
"""
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "manuscript", "main.tex")
DATA = os.path.join(HERE, "data")
flat = re.sub(r"\s+", " ", open(SRC).read())

bad = 0
unarchived = []


def want(pattern, label, literal=True):
    """Assert the manuscript contains `pattern` (whitespace-normalized)."""
    global bad
    pat = re.sub(r"\s+", " ", pattern)
    hit = (pat in flat) if literal else re.search(pattern, flat)
    if not hit:
        print(f"DERIVED      : {label} -> manuscript lacks {pat[:60]}")
        bad += 1


def flag(msg):
    global bad
    print(f"FLAG         : {msg}")
    bad += 1


def read_tsv(path, skip_comments=True):
    rows = []
    for line in open(path):
        if skip_comments and line.startswith("#"):
            continue
        f = line.split()
        if f:
            rows.append(f)
    return rows


def mean(v):
    return sum(v) / len(v)


def sd(v):
    m = mean(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


# ---------------------------------------------------------------- estimator
def hann_peaks(series, q0, band=(-0.004, 0.010), thresh=0.01):
    """The manuscript's spectral estimator: symmetric Hann window, search
    [Q0-0.004, Q0+0.010], local maxima above `thresh` of the in-band maximum,
    three-bin parabolic refinement."""
    import numpy as np
    n = len(series)
    amp = np.abs(np.fft.rfft(series * np.hanning(n)))
    q = np.fft.rfftfreq(n)
    idx = np.where((q >= q0 + band[0]) & (q <= q0 + band[1]))[0]
    cutoff = thresh * amp[idx].max()
    out = []
    for i in idx:
        if amp[i] < cutoff or i == 0 or i + 1 >= len(amp):
            continue
        if amp[i] >= amp[i - 1] and amp[i] >= amp[i + 1]:
            a, b, c = amp[i - 1], amp[i], amp[i + 1]
            den = a - 2 * b + c
            out.append(q[i] + (0.5 * (a - c) / den if den else 0.0) * (q[1] - q[0]))
    return np.array(out)


def top_peak(series, lo, hi):
    """Largest-amplitude Hann-windowed peak in [lo, hi], parabolic-refined."""
    import numpy as np
    n = len(series)
    amp = np.abs(np.fft.rfft(series * np.hanning(n)))
    q = np.fft.rfftfreq(n)
    idx = np.where((q >= lo) & (q <= hi))[0]
    i = idx[np.argmax(amp[idx])]
    a, b, c = amp[i - 1], amp[i], amp[i + 1]
    den = a - 2 * b + c
    return q[i] + (0.5 * (a - c) / den if den else 0.0) * (q[1] - q[0])


# ------------------------------------------------- Sec 5.2/5.3: Yokoya table
def check_yokoya():
    rows = read_tsv(os.path.join(DATA, "lambda_round_converged.tsv"))[1:]
    lx = [float(r[4]) for r in rows]
    ly = [float(r[5]) for r in rows]
    if len(lx) != 3:
        flag(f"lambda_round_converged has {len(lx)} seeds, table says three")
    want(f"${mean(lx):.4f}\\pm{sd(lx):.4f}$", "Yokoya PIC x mean+-sd")
    want(f"${mean(ly):.4f}\\pm{sd(ly):.4f}$", "Yokoya PIC y mean+-sd")

    # BeamBeam3D row, recomputed from the archived raw centroids with the
    # analyze.jl estimator (mean-subtracted Hann, sigma band [Q0-xi/2,Q0+xi/2],
    # pi band [Q0+xi/2,Q0+2xi], three-bin parabola).  The fort files include
    # turn 0; the reduction uses turns 1..8192 -- with all 8193 rows the FFT
    # bin grid shifts every Lambda by ~4e-4.
    import numpy as np

    def col2(name):
        return np.array([float(l.split()[1]) for l in
                         open(os.path.join(DATA, "bb3d_decks", name))])[1:]

    def mode_peak(sig, q0, mode, xi=0.005):
        n = len(sig)
        w = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(n) / n)
        amp = np.abs(np.fft.rfft((sig - sig.mean()) * w))
        q = np.arange(len(amp)) / n
        lo, hi = ((q0 - .5 * xi, q0 + .5 * xi) if mode == "s"
                  else (q0 + .5 * xi, q0 + 2 * xi))
        idx = np.where((q >= lo) & (q <= hi))[0]
        k = idx[np.argmax(amp[idx])]
        a1, a2, a3 = amp[k - 1], amp[k], amp[k + 1]
        den = a1 - 2 * a2 + a3
        return q[k] + (0.5 * (a1 - a3) / den if den else 0.0) / n

    x1, x2 = col2("singleslice_fort.24"), col2("singleslice_fort.34")
    y1, y2 = col2("singleslice_fort.25"), col2("singleslice_fort.35")
    qs_x, qp_x = mode_peak(x1 + x2, 0.31, "s"), mode_peak(x1 - x2, 0.31, "p")
    qs_y, qp_y = mode_peak(y1 + y2, 0.32, "s"), mode_peak(y1 - y2, 0.32, "p")
    bx, by = (qp_x - qs_x) / 0.005, (qp_y - qs_y) / 0.005
    want(f"{bx:.4f}", "BB3D Lambda_x (nominal xi)")
    want(f"{by:.4f}", "BB3D Lambda_y (nominal xi)")
    conv = 0.005 / 0.0049932095
    want(f"({bx * conv:.4f},{by * conv:.4f})", "BB3D Lambda under logged xi")
    if abs(100 * (conv - 1) - 0.136) > 0.0005:
        flag(f"logged-xi normalization change is {100 * (conv - 1):.3f}%, "
             "manuscript says 0.136%")
    # cross-code differences from the three-seed Octopus mean
    dx, dy = abs(bx - mean(lx)), abs(by - mean(ly))
    want(f"{dx:.5f}", "cross-code |dLambda_x|")
    want(f"{dy:.5f}", "cross-code |dLambda_y|")
    qs_oct_x = mean([float(r[6]) for r in rows])
    if not abs(qs_x - qs_oct_x) < 4e-6:
        flag(f"Q_sigma_x cross-code difference {abs(qs_x - qs_oct_x):.2e} "
             "exceeds the manuscript's <4e-6")
    # solver rows and one-at-a-time deltas, from the archived sensitivity TSV
    sens = {}
    for r in read_tsv(os.path.join(DATA, "lambda_sensitivity.tsv"))[1:]:
        sens.setdefault(r[0], []).append((float(r[2]), float(r[3])))
    sx = {v: mean([p[0] for p in pts]) for v, pts in sens.items()}
    sy = {v: mean([p[1] for p in pts]) for v, pts in sens.items()}
    want(f"{sx['soft']:.3f} & {sy['soft']:.3f}", "soft-Gaussian table row")
    want(f"{sx['hybrid']:.3f} & {sy['hybrid']:.3f}", "hybrid table row")
    for v, label in (("grid256", "grid delta"), ("offset025", "offset delta"),
                     ("turns16384", "turns delta")):
        want(f"({sx[v] - mean(lx):+.4f},{sy[v] - mean(ly):+.4f})",
             f"one-at-a-time {label}")
    hyb_dist = 100 * (1.2144 - sx["hybrid"]) / sx["hybrid"]
    if f"{hyb_dist:.2f}\\%" not in flat:
        flag(f"hybrid max distance recomputes to {hyb_dist:.2f}% "
             "(measured denominator); table states a different value")

    # abstract/summary/table 'within X%' statements are BOUNDS on the distance
    # from the Vlasov reference: they must cover the recomputed maximum and be
    # within 0.05 pp of tight.
    vl = 1.2144
    fam = {"PIC x": mean(lx), "PIC y": mean(ly), "hybrid x": sx["hybrid"],
           "hybrid y": sy["hybrid"], "BB3D x": bx, "BB3D y": by}
    dist = max(abs(vl - v) / vl * 100 for v in fam.values())
    m = re.search(r"lie within \$?([\d.]+)\\%\$? of the\s*Vlasov", flat)
    if m:
        bound = float(m.group(1))
        if not (dist <= bound <= dist + 0.05):
            flag(f"'within {bound}%' of Vlasov: recomputed max distance is "
                 f"{dist:.3f}% (worst {max(fam, key=lambda k: abs(vl-fam[k])):s})")
    cross = 100 * max(dx / mean(lx), dy / mean(ly))
    if "0.31\\%" in flat and round(cross, 2) != 0.31:
        flag(f"largest same-setting cross-code difference recomputes to "
             f"{cross:.2f}%, manuscript says 0.31%")


# ------------------------------------------ Sec 4.1: noise-floor text medians
def check_noise_floor():
    det = {}
    fam = None
    for line in open(os.path.join(DATA, "flat_beam_noise_floor.tsv")):
        if line.startswith("# family="):
            fam = "round" if "round" in line else "flat"
            continue
        if line.startswith(("#", "family_case")):
            continue
        f = line.split()
        if f[0] == "deterministic":
            det[fam] = [float(x) for x in f[1:5]]
    # columns: soft_gaussian, pic(128), hybrid(64), spectral
    for famname, col, label in (("round", 2, "hybrid round"),
                                ("flat", 2, "hybrid flat"),
                                ("round", 1, "PIC round"),
                                ("flat", 1, "PIC flat")):
        v = det[famname][col]
        mant, expo = f"{v:.2e}".split("e")
        want(f"${mant}\\times10^{{{int(expo)}}}$", f"deterministic median, {label}")


# --------------------------------------- Sec 4.2: decomposition table Panel A
def check_decomposition():
    import glob
    blocks = sorted(glob.glob(os.path.join(DATA, "kick_decomposition_R100*.tsv")))
    blocks = [b for b in blocks if "ensemble_spread" not in b]
    if len(blocks) != 19:
        flag(f"found {len(blocks)} R=100 blocks, table says 19")
    stats = {"round": [], "flat11": []}
    for b in blocks:
        d = {}
        for r in read_tsv(b)[1:]:
            if r[2] == "CIC":
                d[(r[0], r[1])] = (float(r[5]), float(r[6]), float(r[8]))
        for famname in stats:
            b64, s64, _ = d[(famname, "64")]
            b256, s256, floor256 = d[(famname, "256")]
            stats[famname].append((b64, b256, s256 / s64 - 1, b256 <= floor256))
    for famname, b64s, b256s, incs in (
            (f, [t[0] for t in stats[f]], [t[1] for t in stats[f]],
             [t[2] for t in stats[f]])
            for f in ("round", "flat11")):
        scale = 1e4 if famname == "round" else 1e3
        expo = -4 if famname == "round" else -3
        want(f"$({mean(b64s) * scale:.3f}\\pm{sd(b64s) * scale:.3f})"
             f"\\times10^{{{expo}}}$", f"Panel A B64 {famname}")
        want(f"$({mean(b256s) * 1e4:.3f}\\pm{sd(b256s) * 1e4:.3f})"
             f"\\times10^{{-4}}$", f"Panel A B256 {famname}")
        want(f"${mean(b64s) / mean(b256s):.3f}$", f"Panel A ratio {famname}")
        want(f"$({100 * mean(incs):.3f}\\pm{100 * sd(incs):.3f})\\%$",
             f"Panel A S-increase {famname}")
    r_round = mean([t[0] for t in stats["round"]]) / mean([t[1] for t in stats["round"]])
    r_flat = mean([t[0] for t in stats["flat11"]]) / mean([t[1] for t in stats["flat11"]])
    want(f"{r_round:.2f}", "descriptive ratio round (text)")
    want(f"{r_flat:.2f}", "descriptive ratio flat (text)")
    # Panel B pooled statistics, from the archived pooled-analysis TSV
    # (drivers/kd_pooled_analysis.py over the 19-ensemble dumps).
    pooled = {(r[0], r[1]): r for r in
              read_tsv(os.path.join(DATA, "kd_pooled_panelB.tsv"))[1:]}
    for fam, tag in (("round", "round"), ("flat11", "flat")):
        b64 = float(pooled[(fam, "64")][2])
        s64 = float(pooled[(fam, "64")][3])
        r256 = pooled[(fam, "256")]
        b256, s256 = float(r256[2]), float(r256[3])
        want(f"${b64 * 1e4:.3f}$ & ${b256 * 1e4:.3f}$ & ${s64 * 1e4:.3f}$ & "
             f"${s256 * 1e4:.3f}$", f"Panel B row {tag}")
        want(f"[{float(r256[4]) * 1e4:.3f}, {float(r256[5]) * 1e4:.3f}]",
             f"Panel B delete-one B256 interval {tag}")
        want(f"[{float(r256[6]) * 1e4:.3f}, {float(r256[7]) * 1e4:.3f}]",
             f"Panel B delete-one S256 interval {tag}")
        mant, expo = f"{float(r256[8]):.3e}".split("e")
        want(f"{mant}\\times10^{{{int(expo)}}}", f"Panel B null 95th {tag}")
        mantB, expoB = f"{b256:.3e}".split("e")
        want(f"B_{{256}}={mantB}\\times10^{{{int(expoB)}}}$",
             f"Panel B pooled B256 in text, {tag}")


# --------------------------------- Sec 3.3 + 4.3: boundary and z-interp jumps
def check_boundary():
    def rows(path):
        return read_tsv(path)[1:]
    cic = rows(os.path.join(DATA, "slice_longitudinal_zscan_jumps.tsv"))
    tsc = rows(os.path.join(DATA, "slice_longitudinal_zscan_tsc_jumps.tsv"))

    def rng(rws, mode, col):
        v = [float(r[col]) for r in rws if r[3] == mode and r[col] != "NaN"]
        return min(v), max(v)

    for mode, col, scale, label in (
            ("node_grid", 4, 1e9, "frozen node-indexed x jumps (1e-9)"),
            ("node_grid", 5, 1e8, "frozen node-indexed y jumps (1e-8)"),
            ("node_source_evolution", 4, 1e5, "live node x jumps (1e-5)"),
            ("node_source_evolution", 5, 1e5, "live node y jumps (1e-5)")):
        lo, hi = rng(cic, mode, col)
        want(f"${lo * scale:.1f}$--${hi * scale:.1f}", label)

    # z-interp: on the common grid, worst linear jump (either stencil) vs the
    # worst quadratic+TSC jump
    worst_lin = max(rng(cic, "common_grid", 6)[1], rng(tsc, "common_grid", 6)[1])
    best_quad = rng(tsc, "common_grid", 9)[1]
    if not (0.545 <= worst_lin <= 0.555):
        flag(f"worst common-grid linear pz jump is {worst_lin:.3f}, "
             "manuscript says 55%")
    mant, expo = f"{best_quad:.1e}".split("e")
    want(f"${mant}\\times10^{{{int(expo)}}}$", "quadratic+TSC pz jump")


# ------------------------------------------------ Sec 5.5: luminosity anchor
def check_lum_anchor():
    # exact discrete reference, ported from validation/crossing_luminosity_anchor.jl
    from math import erf, exp, pi, sqrt, tan
    def erfinv(y, lo=-10.0, hi=10.0):
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if erf(mid) < y:
                lo = mid
            else:
                hi = mid
        return 0.5 * (lo + hi)
    # The manuscript quotes both numbers in the phi = 2.5 (exact) convention;
    # the validation script uses tan(12.5 mrad) directly, which lowers the
    # discrete sum in the fifth digit (its header states 0.36926).
    n, sigx, sigz = 15, 100e-6, 0.02
    edges = [sqrt(2.0) * erfinv(2 * (i / n) - 1) for i in range(n + 1)]
    centers = [n * (exp(-edges[i] ** 2 / 2) - exp(-edges[i + 1] ** 2 / 2))
               / sqrt(2 * pi) * sigz for i in range(n)]

    def rdisc_for(tantheta):
        return sum(exp(-(tantheta * (z1 - z2)) ** 2 / (4 * sigx ** 2))
                   for z1 in centers for z2 in centers) / n ** 2

    phi = 2.5
    rcont = 1 / sqrt(1 + phi ** 2)
    rdisc = rdisc_for(phi * sigx / sigz)
    want(f"{rcont:.6f}", "analytic crossing factor R (phi=2.5 exact)")
    if f"{rdisc:.6f}" not in flat:
        flag(f"centroid-only 15-slice quadrature (phi=2.5 exact) recomputes "
             f"to {rdisc:.6f}; manuscript states a different value")
    hdr = open(os.path.join(DATA, "crossing_lum_anchor.tsv")).read()
    m = re.search(r"R_discrete_15slice = ([0-9.]+)", hdr)
    if m and abs(float(m.group(1)) - rdisc_for(tan(12.5e-3))) > 5e-6:
        flag(f"crossing_lum_anchor.tsv header says R_discrete={m.group(1)}, "
             f"tan-convention quadrature gives {rdisc_for(tan(12.5e-3)):.6f}")
    # five-seed spread and slice/grid scan, from the archived robustness TSV
    rows = read_tsv(os.path.join(DATA, "crossing_anchor_robustness.tsv"))[1:]
    five = [(float(r[3]), float(r[4])) for r in rows
            if r[1] == "15" and r[2] == "128"]
    if len(five) != 5:
        flag(f"anchor robustness TSV has {len(five)} seeds at 15/128, not 5")
    want(f"{mean([x for x, _ in five]):.6f}\\pm{sd([x for x, _ in five]):.6f}$",
         "anchor five-seed no-crab")
    want(f"{mean([c for _, c in five]):.6f}\\pm{sd([c for _, c in five]):.6f}$",
         "anchor five-seed crab")
    scan = [float(r[3]) for r in rows if r[0] == "20260728"]
    want(f"{min(scan):.5f}--{max(scan):.5f}", "anchor scan span")


# --------------------------------------- Sec 5.4: multi-slice benchmark stats
def check_multislice():
    import numpy as np
    def diff_mode(name):
        rows = [l.split() for l in open(os.path.join(DATA, name))
                if not l.startswith(("#", "turn"))]
        a = np.array(rows, dtype=float)
        return a[:, 1] - a[:, 2]
    oct_x = hann_peaks(diff_mode("multislice_centroids_octopus_noise.tsv"), 0.31)
    bb_x = hann_peaks(diff_mode("multislice_centroids_bb3d.tsv"), 0.31)
    if len(oct_x) != 6 or len(bb_x) != 6:
        flag(f"multislice peak counts (octopus {len(oct_x)}, bb3d {len(bb_x)}) "
             "differ from the manuscript's six each")
        return
    d = abs(np.sort(oct_x) - np.sort(bb_x))
    med, mx = float(np.median(d)), float(d.max())
    want(f"({med * 1e4:.2f},{mx * 1e4:.2f})\\times10^{{-4}}", "multislice |dQ| stats")
    if f"{mx * 4096:.1f} raw" not in flat:
        flag(f"multislice max |dQ| is {mx * 4096:.1f} raw FFT bins, "
             "manuscript states a different bin count")


# ------------------------------------------------- Sec 5.6: EIC emittance table
def check_eic():
    def series(name):
        rows = {int(r[0]): [float(x) for x in r[1:5]]
                for r in read_tsv(os.path.join(DATA, name))[1:]}
        return rows
    oc, bb = series("eic_emittance_octopus.tsv"), series("eic_emittance_bb3d.tsv")
    turns = [t for t in sorted(oc) if 6144 <= t <= 8176 and t in bb]
    if len(turns) != 128:
        flag(f"late-time window has {len(turns)} common records, table says 128")
    ex_d, ey_d = (106e-6) ** 2 / 0.55, (9.5e-6) ** 2 / 0.056
    def pct(rows, col, ref):
        return 100 * (mean([rows[t][col] for t in turns]) / ref - 1)
    vals = {}
    for tag, rows in (("oct", oc), ("bb", bb)):
        first = rows[min(rows)]
        vals[tag] = [pct(rows, 0, ex_d), pct(rows, 1, ey_d),
                     pct(rows, 2, first[2]), pct(rows, 3, first[3])]
    for i, (label, digits) in enumerate((("electron x", 2), ("electron y", 2),
                                         ("proton x", 3), ("proton y", 3))):
        o, b = vals["oct"][i], vals["bb"][i]
        want(f"+{o:.{digits}f}\\%", f"EIC table Octopus {label}")
        want(f"+{b:.{digits}f}\\%", f"EIC table BB3D {label}")
        d = o - b
        want(f"{'+' if d >= 0 else '-'}{abs(d):.{2 if i < 2 else 3}f}$~pp",
             f"EIC table difference {label}")
    frac = 100 * (vals["oct"][1] - vals["bb"][1]) / vals["bb"][1]
    if f"{frac:.0f}\\%" not in flat:
        flag(f"electron-y difference / BB3D induced excess recomputes to "
             f"{frac:.0f}%, manuscript says 31%")


# ------------------------------------------------------- Sec 6: timing table
def check_timing():
    path = os.path.join(DATA, "gpu_walltime_table.tsv")
    if not os.path.exists(path):
        unarchived.append("GPU wall-time table (0.2350/0.3068/0.3386/0.5586/"
                          "0.5467 s/turn, process-median protocol) - the "
                          "submitted campaign was never archived and predates "
                          "the 2026-08-11 performance work; re-measure on "
                          "paper-cpc and commit as data/gpu_walltime_table.tsv")
        return
    # columns: config total_particles mesh processes mean sd process_medians
    #          mean_of_process_means sd_of_process_means
    for r in read_tsv(path)[1:]:
        want(f"${float(r[4]):.4f}\\pm{float(r[5]):.4f}$",
             f"timing row {r[0]}")
        if r[0] == "nominal":
            want(f"${float(r[7]):.4f}\\pm{float(r[8]):.4f}$",
                 "nominal process means")
            want(f"{float(r[7]) * 1e5 / 3600:.2f} GPU-hours",
                 "GPU-hour extrapolation from process mean")
    # weak-strong companion number in the A100 sentence
    import statistics as _st
    ws = [float(r[1]) for r in
          read_tsv(os.path.join(DATA, "weakstrong_walltime.tsv"))[1:]]
    want(f"measures {round(_st.median(ws))}~ms/turn", "weak-strong companion wall time")


# ------------------------------------------------------- structural figure QA
def content_hash(path):
    import hashlib
    raw = open(path, "rb").read()
    raw = re.sub(rb"/(CreationDate|ModDate)\s*\([^)]*\)", b"", raw)
    raw = re.sub(rb"/ID\s*\[[^\]]*\]", b"", raw)
    return hashlib.sha256(raw).hexdigest()


PAPER_FIGS = ("fig_noise_floor", "fig_boundary_jump", "fig_coherent_fft",
              "fig_multislice_spectra", "fig_eic_emittance")


def check_figures():
    """figs/ must be byte-reproducible from data/, and manuscript/figs must
    carry exactly those files for the five figures the paper includes."""
    import glob
    import subprocess
    n = 0
    before = {f: content_hash(f)
              for f in sorted(glob.glob(os.path.join(HERE, "figs", "*.pdf")))}
    r = subprocess.run([sys.executable, os.path.join(HERE, "make_figures.py")],
                       capture_output=True, cwd=HERE)
    if r.returncode != 0:
        print("FIGURES      : make_figures.py failed")
        return 1
    for f, h in before.items():
        if content_hash(f) != h:
            print(f"FIGURE STALE : {os.path.basename(f)} is not what its data produces")
            n += 1
    for name in PAPER_FIGS:
        a = os.path.join(HERE, "figs", name + ".pdf")
        b = os.path.join(HERE, "manuscript", "figs", name + ".pdf")
        if content_hash(a) != content_hash(b):
            print(f"FIGURE DESYNC: manuscript/figs/{name}.pdf differs from "
                  "the regenerated figs/ copy")
            n += 1
    return n


def check_axis_limits():
    """Flag data drawn outside the limits finally set on its Axes.

    Walks the artists actually attached to each Axes at savefig time (plot,
    errorbar, scatter, step alike).  A handful of points beyond the axis is
    hidden data whichever way it was drawn; a dense series running past the
    frame is deliberate range selection.
    """
    import runpy
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.figure as _figure
    import numpy as _np
    from matplotlib.collections import PathCollection

    problems = []
    orig_savefig = _figure.Figure.savefig
    NOMARKER = (None, "None", "none", "", " ")

    def series(ax):
        out = []
        for ln in ax.lines:
            if ln.get_transform() is not ax.transData:
                continue
            marked = ln.get_marker() not in NOMARKER
            out.append(("marker" if marked else "line",
                        _np.asarray(ln.get_xdata(), dtype=float),
                        _np.asarray(ln.get_ydata(), dtype=float), marked))
        for col in ax.collections:
            if not isinstance(col, PathCollection):
                continue
            if col.get_transform() is not ax.transData:
                continue
            off = _np.asarray(col.get_offsets(), dtype=float)
            if off.size:
                out.append(("scatter", off[:, 0], off[:, 1], True))
        return out

    def savefig(self, *a, **k):
        name = os.path.basename(str(a[0])) if a else "<figure>"
        for i, ax in enumerate(self.axes):
            bounds = (("x", ax.get_xlim()), ("y", ax.get_ylim()))
            for kind, xs, ys, strict in series(ax):
                for (axis, (lo, hi)), v in zip(bounds, (xs, ys)):
                    v = v[_np.isfinite(v)]
                    if not v.size:
                        continue
                    lo, hi = min(lo, hi), max(lo, hi)
                    pad = 1e-9 * (hi - lo)
                    outside = (v > hi + pad) | (v < lo - pad)
                    frac = outside.sum() / outside.size
                    hidden_points = 0.0 < frac <= 0.10
                    if outside.all() or hidden_points or (strict and outside.any()):
                        problems.append(
                            f"OFF-AXIS     : {name} ax{i} {kind} {axis} "
                            f"{'lies entirely' if outside.all() else 'has hidden point(s)'} "
                            f"outside {axis}lim ({lo:.4g}, {hi:.4g}); series "
                            f"spans [{v.min():.4g}, {v.max():.4g}]")
        return orig_savefig(self, *a, **k)

    _figure.Figure.savefig = savefig
    cwd = os.getcwd()
    try:
        os.chdir(HERE)
        runpy.run_path(os.path.join(HERE, "make_figures.py"), run_name="__main__")
    finally:
        os.chdir(cwd)
        _figure.Figure.savefig = orig_savefig
    for p in sorted(set(problems)):
        print(p)
    return len(set(problems))


check_yokoya()
check_noise_floor()
check_decomposition()
check_boundary()
check_lum_anchor()
check_multislice()
check_eic()
check_timing()
unarchived.extend([
    "structural-check numbers (symplectic defects 7.91e-8->7.90e-10 / "
    "4.24e-8->4.24e-10, boost identity 8.3e-19) - test-suite outputs",
    "CPU/CUDA regression tolerances (1e-10 / 1e-9 / 1e-18, 'six also passed') "
    "- test-suite outputs",
    "hybrid neutralization bounds (|1-alpha| <= 2.09e-7 five-sigma, 6.80e-3 "
    "no-margin, six sources) - supplement-era analysis",
    "Sec 4.1 perturbation-test ordering claims (30% narrow component, coupled "
    "offset mixture) - supplement-era analysis",
])
bad += check_figures()
bad += check_axis_limits()
if unarchived:
    print("\n-- UNARCHIVED claims (informational; regenerate or accept) --")
    for u in unarchived:
        print(f"UNARCHIVED   : {u}")
print("\nALL CHECKS PASS" if bad == 0 else f"\n{bad} problem(s)")
sys.exit(1 if bad else 0)
