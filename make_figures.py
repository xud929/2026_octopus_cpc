#!/usr/bin/env python3
"""Generate the vector figures for the Octopus CPC paper from the validation TSVs.

Data sources (read-only):
  - <slides>/data/flat_beam_noise_floor.tsv        -> fig_noise_floor.pdf
  - <octopus>/result/yokoya_vs_aspect{,_measured}.tsv
    <octopus>/result/yokoya_vs_xi_{theory,measured}.tsv -> fig_yokoya_scans.pdf
  - <octopus>/result/gaussian_pic_field_validation_summary.tsv -> fig_error_vs_grid.pdf
  - <octopus>/result/pic_gaussian_field_validation_random_summary.tsv -> fig_error_vs_aspect.pdf
  - <octopus>/result/eic_mode_spectra.tsv          -> fig_eic_modes.pdf

Output: figs/*.pdf (vector, single-column friendly).
"""

import csv
import glob
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OCT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SLIDES = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
os.makedirs(OUT, exist_ok=True)

# ---- palette (validated reference palette, light mode) ----------------------
BLUE = "#2a78d6"     # slot 1  -> PIC / measurement / electron
ORANGE = "#eb6834"   # slot 2  -> soft-Gaussian / proton
AQUA = "#1baf7a"     # slot 3  -> Gaussian-subtracted hybrid
YELLOW = "#eda100"   # slot 4  -> spectral (sub-3:1 on white: always direct-labeled/legended)
BAND = "#cde2fb"     # light blue wash (reference bands)
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

SOLVER_COLOR = {
    "soft_gaussian": ORANGE,
    "pic": BLUE,
    "hybrid": AQUA,
    "spectral": YELLOW,
}
SOLVER_LABEL = {
    "soft_gaussian": "soft-Gaussian",
    "pic": "PIC $128^2$",
    "hybrid": "hybrid $64^2$",
    "spectral": "spectral",
}
SOLVER_ORDER = ["pic", "soft_gaussian", "hybrid", "spectral"]

plt.rcParams.update({
    "font.size": 8.0,
    "axes.labelsize": 8.5,
    "axes.titlesize": 8.5,
    "axes.edgecolor": AXIS,
    "axes.linewidth": 0.7,
    "axes.labelcolor": INK2,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5,
    "legend.frameon": False,
    "pdf.fonttype": 42,
})


def style_axis(ax, ygrid=True):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if ygrid:
        ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=0.7)


# ============================================================================
# 1. Noise floor: field error vs macroparticle number, round + flat 11:1
# ============================================================================
# measured six-seed repeat scatter of the median (relative), per family/N/solver
REL_SCATTER = {
    ("round", "1e4"): {"soft": 0.18, "pic": 0.10, "hyb": 0.12, "spec": 0.10},
    ("round", "1e5"): {"soft": 0.22, "pic": 0.15, "hyb": 0.17, "spec": 0.10},
    ("round", "1e6"): {"soft": 0.28, "pic": 0.16, "hyb": 0.18, "spec": 0.02},
    ("flat", "1e4"): {"soft": 0.23, "pic": 0.14, "hyb": 0.20, "spec": 0.10},
    ("flat", "1e5"): {"soft": 0.26, "pic": 0.05, "hyb": 0.13, "spec": 0.04},
    ("flat", "1e6"): {"soft": 0.41, "pic": 0.05, "hyb": 0.20, "spec": 0.03},
}


def fig_noise_floor():
    path = os.path.join(SLIDES, "data", "flat_beam_noise_floor.tsv")
    families, current = {}, None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("# family="):
                current = "round" if "round" in line else "flat"
                families[current] = {}
            elif line and not line.startswith("#") and current:
                parts = line.split("\t")
                if parts[0] == "family_case":
                    continue
                families[current][parts[0]] = [float(v) for v in parts[1:]]

    fig, axes = plt.subplots(1, 2, figsize=(6.3, 3.0), sharey=True)
    nmac = np.array([1e4, 1e5, 1e6])
    for ax, fam, title in zip(axes, ["round", "flat"],
                              ["round beam", "flat $11{:}1$ beam"]):
        data = families[fam]
        cols = ["soft_gaussian", "pic", "hybrid", "spectral"]
        for s in SOLVER_ORDER:
            j = cols.index(s)
            y = np.array([data["1e+04"][j], data["1e+05"][j], data["1e+06"][j]])
            floor = data["deterministic"][j]
            c = SOLVER_COLOR[s]
            short = {"soft_gaussian": "soft", "pic": "pic",
                     "hybrid": "hyb", "spectral": "spec"}[s]
            rel = np.array([REL_SCATTER[(fam, k)][short]
                            for k in ("1e4", "1e5", "1e6")])
            ax.errorbar(nmac, y, yerr=y * rel, fmt="-o", color=c,
                        linewidth=1.6, markersize=4.5, capsize=2.0,
                        elinewidth=0.8, label=SOLVER_LABEL[s], zorder=3)
            ax.hlines(floor, nmac[0], nmac[-1], color=c, linewidth=1.0,
                      linestyle=(0, (4, 3)), alpha=0.65, zorder=2)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("macroparticles per slice")
        ax.set_title(title, color=INK, fontsize=8.5)
        style_axis(ax)
    # 1/sqrt(N) slope guide, left panel only
    ref = 2.0e-3 * np.sqrt(1e4 / nmac)
    axes[0].plot(nmac, ref, color=MUTED, linewidth=0.9, linestyle=":", zorder=1)
    axes[0].text(4.0e5, 2.1e-4, r"$\propto N^{-1/2}$", color=MUTED, fontsize=7)
    axes[0].set_ylabel("median relative kick error")
    axes[1].text(1.1e4, 1.05e-4, "dashed: det.-source\nupper bound",
                 color=INK2, fontsize=7)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4,
               handlelength=1.6, columnspacing=1.6, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(w_pad=1.6, rect=(0, 0.09, 1, 1))
    fig.savefig(os.path.join(OUT, "fig_noise_floor.pdf"))
    plt.close(fig)


# ============================================================================
# 2. Yokoya scans: Lambda vs aspect ratio and vs xi
# ============================================================================
def read_tsv(path):
    rows = []
    with open(path) as f:
        rdr = csv.reader(f, delimiter="\t")
        header = None
        for row in rdr:
            if not row or row[0].startswith("#"):
                continue
            if header is None:
                header = row
                continue
            rows.append([float(v) for v in row])
    return header, np.array(rows)


# The reduced-Vlasov driver's origin-region quadrature is unconverged at small
# s_t = sqrt(2)*r, where `normalized_equilibrium` departs from the exact
# reduced-model gradient.  Those Lambda values are numerics, not physics, so
# they are NOT plotted; the rows stay in the archived TSV and the mask is here
# so the figure cannot show them.  The threshold is the driver's own
# self-check 4 (validation/coherent_mode_vlasov_theory.jl), which FAILS only
# for r <= 0.3 and PASSES at r = 0.5, 0.7, 0.85, 1.0 -- and on the
# narrow-plane side at r = 5 and 11.111.  0.5 is therefore the first archived
# row the primary check supports.  An earlier version of this comment said the
# check fails for r <= 0.7 and masked at 0.8; both were wrong -- the mask was
# conservative past the data, on the strength of a false statement about the
# model's own validity range.
VLASOV_CONVERGED_MIN_R = 0.5


def fig_yokoya_scans():
    _, th = read_tsv(os.path.join(OCT, "yokoya_vs_aspect.tsv"))
    th = th[th[:, 0] >= VLASOV_CONVERGED_MIN_R]
    _, ms = read_tsv(os.path.join(OCT, "yokoya_vs_aspect_measured.tsv"))
    _, xth = read_tsv(os.path.join(OCT, "yokoya_vs_xi_theory.tsv"))
    _, xms = read_tsv(os.path.join(OCT, "yokoya_vs_xi_measured.tsv"))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.3, 2.8))

    # --- (a) Lambda vs aspect ratio ---
    ax1.axhspan(1.2, 1.33, color=BAND, alpha=0.55, zorder=0)
    ax1.text(0.021, 1.315, "literature range 1.2–1.33\n(reproduced in neither plane; see text)", color="#104281",
             fontsize=7)
    ax1.axhline(1.0, color=MUTED, linewidth=0.9, linestyle=(0, (4, 3)))
    ax1.text(0.021, 1.02, r"rigid bunch ($\Lambda=1$)", color=MUTED, fontsize=7)
    # The two 1D reduced-model curves are NOT drawn: the manuscript does not
    # discuss them, and the driver that produces them states they are not a
    # quantitative instrument at the few-percent level.  Panel (a) shows the
    # measurement against the literature band only.
    ax1.plot([1.0], [1.198], marker="D", markersize=5.0, color="#7a4fb8",
             linestyle="none", zorder=5, label="converged $r=1$ (8192 turns)")
    ax1.errorbar(ms[:, 0], ms[:, 1], yerr=0.005, fmt="o", color=BLUE,
                 markersize=5, capsize=2, elinewidth=0.9,
                 label="2D strong–strong PIC", zorder=4)
    _, npl = read_tsv(os.path.join(OCT, "lambda_narrowplane.tsv"))
    ok = npl[:, 3] <= 0.06
    _off = 0.88   # drawn slightly offset in r for legibility (see caption)
    ax1.plot(npl[ok, 0] * _off, npl[ok, 2], "^", color=AQUA, markersize=5.5,
             markerfacecolor="white", markeredgewidth=1.3, zorder=6,
             label=r"narrow plane $\Lambda_y$ (single seed)")
    ax1.plot(npl[~ok, 0] * _off, npl[~ok, 2], "^", color=AQUA, markersize=5.5,
             markerfacecolor="white", markeredgewidth=1.3, alpha=0.45, zorder=6)
    ax1.annotate(r"$\xi_y{=}0.10$", xy=(npl[~ok, 0][0] * _off, npl[~ok, 2][0]),
                 xytext=(6, -1), textcoords="offset points", fontsize=6.2,
                 color=AQUA, va="center")
    ax1.set_xscale("log")
    ax1.set_xlabel(r"aspect ratio $r=\sigma_y/\sigma_x$")
    ax1.set_ylabel(r"Yokoya factor $\Lambda$")
    ax1.set_ylim(0.0, 1.6)
    ax1.legend(loc="lower right", handlelength=1.7, borderaxespad=0.2)
    style_axis(ax1)

    # --- (b) Lambda vs xi ---
    ax2.axhspan(1.2, 1.33, color=BAND, alpha=0.55, zorder=0)
    ax2.plot(xth[:, 0], xth[:, 1], color=INK2, linewidth=1.3,
             label=r"$\Lambda_0{=}1.20$ + discrete-map correction")
    seed_env = np.maximum(0.005, 0.005 * 0.005 / xms[:, 0])
    yerrs = np.sqrt(seed_env**2 + (np.sqrt(2) * 1.8e-5 / xms[:, 0])**2)
    ax2.errorbar(xms[:, 0], xms[:, 1], yerr=yerrs, fmt="o", color=BLUE,
                 markersize=5, capsize=2, elinewidth=0.9,
                 label="2D strong–strong PIC", zorder=4)
    ax2.set_xlabel(r"beam–beam parameter $\xi$")
    ax2.set_ylim(1.10, 1.36)
    ax2.set_xlim(0, 0.021)
    ax2.legend(loc="lower left", handlelength=1.7, borderaxespad=0.4)
    style_axis(ax2)

    for ax, tag in [(ax1, "(a)"), (ax2, "(b)")]:
        ax.text(0.02, 0.965, tag, transform=ax.transAxes, color=INK,
                fontsize=9, fontweight="bold", va="top")
    fig.tight_layout(w_pad=1.8)
    ax2.plot([0.02], [1.196], marker="s", markersize=5.0, color=AQUA,
             linestyle="none", zorder=4, label="$y$ control (off-resonance)")
    ax2.legend(loc="lower left", handlelength=1.2, fontsize=6.8)
    fig.savefig(os.path.join(OUT, "fig_yokoya_scans.pdf"))
    plt.close(fig)


# ============================================================================
# 3. Field error vs grid: PIC vs hybrid, four aspect ratios
# ============================================================================
def fig_error_vs_grid():
    cases = {}
    with open(os.path.join(OCT, "gaussian_pic_field_validation_summary.tsv")) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            case, grid = p[0], int(p[1])
            cases.setdefault(case, {})[grid] = (float(p[5]), float(p[7]))
    floors = {}
    with open(os.path.join(OCT, "pic_analytic_floor.tsv")) as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            floors.setdefault(p[0], {})[int(p[1])] = float(p[2])
    order = ["round", "5:1", "production_e ~11:1", "25:1"]
    titles = ["round", "$5{:}1$", "$11{:}1$ (prod. $e^-$)", "$25{:}1$"]

    fig, axes = plt.subplots(1, 4, figsize=(6.3, 2.1), sharey=True)
    grids = sorted(cases[order[0]].keys())
    for ax, case, title in zip(axes, order, titles):
        pic = [cases[case][g][0] for g in grids]
        hyb = [cases[case][g][1] for g in grids]
        ax.plot(grids, pic, "-o", color=BLUE, linewidth=1.6, markersize=4,
                label="PIC (quantile source)")
        ax.plot(grids, hyb, "-o", color=AQUA, linewidth=1.6, markersize=4,
                label="hybrid (quantile source)")
        fl = floors[case]
        fg = sorted(fl.keys())
        ax.plot(fg, [fl[g] for g in fg], "--", color=MUTED, linewidth=1.3,
                label="PIC floor (analytic deposition)")
        ax.axvline(128, color=MUTED, linewidth=0.8, linestyle=":", zorder=0)
        ax.plot([128], [cases[case][128][0]], "D", color=BLUE, markersize=8.0,
                markerfacecolor="white", markeredgewidth=1.4, zorder=6)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xticks([48, 96, 192])
        ax.set_xticklabels(["$48$", "$96$", "$192$"])
        ax.minorticks_off()
        ax.set_title(title, color=INK, fontsize=8.5)
        ax.set_xlabel("mesh $n$ ($n\\times n$)")
        style_axis(ax)
    axes[0].set_ylabel("median relative\nkick error")
    axes[0].annotate("prod.\nmesh", xy=(0.62, 0.93), xycoords="axes fraction",
                     ha="center", va="top", fontsize=6.0, color=MUTED)
    axes[3].legend(loc="lower left", fontsize=6.2, handlelength=1.3,
                   borderaxespad=0.2)
    fig.tight_layout(w_pad=1.0)
    for _ax in fig.axes:
        _ax.set_ylim(bottom=2.0e-5)
        _ax.set_xticks([48, 64, 96, 128, 192, 256])
        _ax.set_xticklabels(['48', '64', '96', '128', '192', '256'], fontsize=6.5)
    fig.savefig(os.path.join(OUT, "fig_error_vs_grid.pdf"))
    plt.close(fig)


# ============================================================================
# 4. Field error vs aspect ratio: 100 random bi-Gaussian cases
# ============================================================================
def fig_error_vs_aspect():
    ratio, med, p95 = [], [], []
    with open(os.path.join(OCT,
              "pic_gaussian_field_validation_random_summary.tsv")) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            ratio.append(float(p[3]))
            med.append(float(p[9]))
            p95.append(float(p[11]))
    ratio, med, p95 = map(np.array, (ratio, med, p95))

    fig, ax = plt.subplots(figsize=(4.4, 2.7))
    ax.plot(ratio, p95, "o", color=MUTED, markersize=3.6,
            markerfacecolor="none", markeredgewidth=0.9, label="95th percentile")
    ax.plot(ratio, med, "o", color=BLUE, markersize=3.6, label="median")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"aspect ratio $\sigma_x/\sigma_y$")
    ax.set_ylabel("relative kick error")
    ax.set_ylim(top=4.5e-2)
    ax.legend(loc="upper center", ncol=2, handlelength=1.2, borderaxespad=0.2)
    style_axis(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_error_vs_aspect.pdf"))
    plt.close(fig)


# ============================================================================
# 5b. Coherent sigma/pi mode spectra (round-beam Yokoya benchmark)
# ============================================================================
def fig_coherent_fft():
    import re

    def load(plane):
        path = os.path.join(SLIDES, "data", f"coherent_spectrum_pic_{plane}.tsv")
        meta = {}
        with open(path) as f:
            for line in f:
                if not line.startswith("#"):
                    break
                for k in ("q_bare", "q_sigma", "q_pi", "lambda"):
                    m = re.search(rf"{k}=([0-9.eE+-]+)", line)
                    if m:
                        meta[k] = float(m.group(1))
        d = np.loadtxt(path, comments="#", skiprows=4)
        return meta, d

    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.6), sharey=True)
    for ax, plane in zip(axes, ["x", "y"]):
        meta, d = load(plane)
        qs, qp, lam = meta["q_sigma"], meta["q_pi"], meta["lambda"]
        lo, hi = meta["q_bare"] - 0.008, meta["q_bare"] + 0.014
        sel = (d[:, 0] >= lo) & (d[:, 0] <= hi)
        norm = max(d[sel, 1].max(), d[sel, 2].max())
        ax.axvline(qs, color=MUTED, linewidth=0.8, linestyle=(0, (3, 3)))
        ax.axvline(qp, color=MUTED, linewidth=0.8, linestyle=(0, (3, 3)))
        ax.plot(d[sel, 0], d[sel, 1] / norm, color=BLUE, linewidth=1.1,
                label=r"$\sigma$ mode ($x_1{+}x_2$)" if plane == "x"
                      else r"$\sigma$ mode ($y_1{+}y_2$)")
        ax.plot(d[sel, 0], d[sel, 2] / norm, color=ORANGE, linewidth=1.1,
                label=r"$\pi$ mode ($x_1{-}x_2$)" if plane == "x"
                      else r"$\pi$ mode ($y_1{-}y_2$)")
        ax.set_yscale("log")
        ax.set_xlabel("fractional tune")
        ax.set_title(f"${plane}$ plane (seed 1 of 3):  $\\Lambda_{plane} = {lam:.3f}$",
                     color=INK, fontsize=8.5, pad=15)
        ax.text(qs, 2.3, r"$Q_\sigma$", color=INK2, fontsize=7.5, ha="center")
        ax.text(qp, 2.3, r"$Q_\pi$", color=INK2, fontsize=7.5, ha="center")
        # 1e-7, not 2e-7: the measured spectra bottom out at 1.08e-7 and the
        # tighter limit clipped their noise floor out of the frame.
        ax.set_ylim(1e-7, 2.0)
        ax.legend(loc="upper right", handlelength=1.5, borderaxespad=0.2)
        style_axis(ax, ygrid=False)
    axes[0].set_ylabel("dipole amplitude\n(normalized)")
    fig.tight_layout(w_pad=1.4)
    fig.savefig(os.path.join(OUT, "fig_coherent_fft.pdf"))
    plt.close(fig)


# ============================================================================
# 6. EIC asymmetric coherent-mode spectra with theory continua
# ============================================================================
def fig_eic_modes():
    _, d = read_tsv(os.path.join(OCT, "eic_mode_spectra.tsv"))
    freq = d[:, 0]
    sel = (freq >= 0.05) & (freq <= 0.30)
    # theory continua from the coupled linearized-Vlasov analysis
    cont = {"x": {"e": (0.080, 0.168), "p": (0.228, 0.2374)},
            "y": {"e": (0.140, 0.2404), "p": (0.210, 0.2194)}}

    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.6), sharey=True)
    for ax, plane, (ie, ip) in zip(axes, ["x", "y"], [(1, 2), (3, 4)]):
        for beam, lo_hi, color in [("e", cont[plane]["e"], BAND),
                                   ("p", cont[plane]["p"], "#f8d3c2")]:
            ax.axvspan(*lo_hi, color=color, alpha=0.55, zorder=0)
        ax.plot(freq[sel], d[sel, ie], color=BLUE, linewidth=1.0,
                label="electron")
        ax.plot(freq[sel], d[sel, ip], color=ORANGE, linewidth=1.0,
                label="proton")
        ax.set_yscale("log")
        ax.set_xlabel("fractional tune")
        ax.set_title(f"${plane}$ plane", color=INK, fontsize=8.5)
        style_axis(ax, ygrid=False)
    axes[0].set_ylabel("dipole amplitude")
    axes[0].legend(loc="upper left", handlelength=1.5, borderaxespad=0.2)
    axes[0].text(0.125, 2.8e-4, "$e$ continuum", color="#104281", fontsize=7,
                 ha="center")
    axes[0].text(0.232, 1.5e-3, "$p$", color="#a03d12", fontsize=7, ha="center")
    axes[1].text(0.165, 1.5e-3, "$e$ continuum", color="#104281", fontsize=7,
                 ha="center")
    axes[1].annotate("persistent mode\nat $Q_{p,y}$", xy=(0.216, 6e-3),
                     xytext=(0.246, 8e-4), color=INK2, fontsize=7,
                     arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    fig.tight_layout(w_pad=1.4)
    fig.savefig(os.path.join(OUT, "fig_eic_modes.pdf"))
    plt.close(fig)


# ============================================================================
# 8. Multi-slice cross-code benchmark: pi-mode synchro-betatron multiplet

# ============================================================================
# 9. Slice-boundary kick discontinuity: transverse by grid mode, longitudinal
#    by deposition/interpolation pair (archived frozen-field z-scan)
# ============================================================================
def fig_boundary_jump():
    def load(fn):
        rows = [l.split("\t") for l in open(os.path.join(OCT, fn)).read().splitlines()[1:]]
        d = {}
        for r in rows:
            d.setdefault(r[3], []).append([float(x) for x in r[4:]])
        return d
    cic = load("slice_longitudinal_zscan_jumps.tsv")
    tsc = load("slice_longitudinal_zscan_tsc_jumps.tsv")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(6.3, 2.6))

    modes = [("per_slice_grid", "per-slice-pair\n(production)"),
             ("source_slice_grid", "shared\nsource mesh"),
             ("common_grid", "common\nmesh"),
             ("node_grid", "node-indexed")]
    for i, (key, lab) in enumerate(modes):
        a = np.array(cic[key])
        ax1.plot([i - 0.12] * len(a), np.abs(a[:, 0]), "o", color=BLUE,
                 markersize=4.5, markerfacecolor="none", markeredgewidth=1.1,
                 label="horizontal" if i == 0 else None)
        ax1.plot([i + 0.12] * len(a), np.abs(a[:, 1]), "s", color=ORANGE,
                 markersize=4.5, markerfacecolor="none", markeredgewidth=1.1,
                 label="vertical" if i == 0 else None)
    ax1.set_yscale("log")
    ax1.set_xticks(range(len(modes)))
    ax1.set_xticklabels([m[1] for m in modes], fontsize=6.2)
    ax1.set_ylabel("relative transverse\nkick jump at boundary")
    ax1.legend(fontsize=6.5, handlelength=1.0, loc="center right")
    style_axis(ax1)

    pairs = [(cic, 2, "CIC\nlinear"), (cic, 5, "CIC\nquadratic"),
             (tsc, 2, "TSC\nlinear"), (tsc, 5, "TSC\nquadratic")]
    for i, (src, col, lab) in enumerate(pairs):
        v = np.abs(np.array(src["common_grid"])[:, col])
        ax2.plot([i] * len(v), v, "D", color=AQUA, markersize=4.5,
                 markerfacecolor="none", markeredgewidth=1.1)
        ax2.plot([i - 0.22, i + 0.22], [v.max()] * 2, "-", color=INK2, linewidth=1.2)
    ax2.set_yscale("log")
    ax2.set_xticks(range(len(pairs)))
    ax2.set_xticklabels([p[2] for p in pairs], fontsize=6.5)
    ax2.set_ylabel("longitudinal kick jump\n(fraction of peak)")
    ax2.annotate("", xy=(3, 9.5e-4), xytext=(3, 0.55),
                 arrowprops=dict(arrowstyle="<->", color=MUTED, linewidth=0.9))
    ax2.text(2.88, 0.02, r"$\approx$580$\times$", fontsize=6.5, color=MUTED,
             ha="right")
    style_axis(ax2)
    for ax, tag in [(ax1, "(a)"), (ax2, "(b)")]:
        ax.text(0.02, 0.03, tag, transform=ax.transAxes, color=INK,
                fontsize=9, fontweight="bold", va="bottom")
        ax.set_xlim(-0.55, len(modes) - 0.45)
    fig.tight_layout(w_pad=1.6)
    fig.savefig(os.path.join(OUT, "fig_boundary_jump.pdf"))
    plt.close(fig)


# ============================================================================


def fig_multislice_spectra():
    def spectrum(path):
        d = np.loadtxt(path, skiprows=1)
        n = d.shape[0]
        w = np.hanning(n)
        q = np.fft.rfftfreq(n)
        out = {}
        for key, c1, c2 in (("x", 1, 2), ("y", 3, 4)):
            s = d[:, c1] - d[:, c2]
            out[key] = (q, np.abs(np.fft.rfft((s - s.mean()) * w)))
        return out

    oct_kick = spectrum(os.path.join(SLIDES, "data", "multislice_centroids_octopus_kicked.tsv"))
    oct_noise = spectrum(os.path.join(SLIDES, "data", "multislice_centroids_octopus_noise.tsv"))
    bb3d = spectrum(os.path.join(SLIDES, "data", "multislice_centroids_bb3d.tsv"))

    xi = 0.005
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.6), sharey=True)
    qsig = {"x": 0.31046, "y": 0.32045}  # measured sigma modes (kicked run)
    for ax, plane, qbare in zip(axes, ["x", "y"], [0.31, 0.32]):
        qs = qsig[plane]
        ax.axvspan(qs, qs + xi, color=BAND, alpha=0.55, linewidth=0,
                   zorder=0)
        ax.axvline(qs + 1.2 * xi, color=MUTED, linewidth=0.8,
                   linestyle=(0, (3, 3)))
        for data, color, lw, label in (
                (oct_kick, BLUE, 1.2, "Octopus, $0.1\\sigma$ kick"),
                (oct_noise, AQUA, 1.0, "Octopus, noise-excited"),
                (bb3d, ORANGE, 1.0, "BeamBeam3D, noise-excited")):
            q, a = data[plane]
            sel = (q >= qbare - 0.004) & (q <= qbare + 0.010)
            ax.plot(q[sel], a[sel] / a[sel].max(), color=color, linewidth=lw,
                    label=label)
        ax.set_yscale("log")
        ax.set_ylim(3e-3, 2.5)
        ax.set_xlabel("fractional tune")
        ax.set_title(f"${plane}$ plane", color=INK, fontsize=8.5)
        ax.text(qs + 1.2 * xi, 1.35, r"$Q_\sigma + 1.2\,\xi$", color=INK2,
                fontsize=7.0, ha="center")
        style_axis(ax, ygrid=False)
    axes[0].set_ylabel("$\\pi$-mode amplitude\n(normalized)")
    axes[0].legend(loc="lower left", handlelength=1.4, borderaxespad=0.3,
                   fontsize=6.8)
    fig.tight_layout(w_pad=1.4)
    fig.savefig(os.path.join(OUT, "fig_multislice_spectra.pdf"))
    plt.close(fig)


# ============================================================================
# 9. EIC cross-code emittance benchmark (Octopus vs BeamBeam3D, 15 slices)
# ============================================================================
# Design geometric emittances sigma^2/beta, identical in both codes' decks.
# Both curves are referenced to these rather than to each code's own turn-0
# sample: the two codes draw their initial distributions independently and
# record the first sample at different points in the turn.
EIC_DESIGN = {
    "ele_ex": 106.0e-6 ** 2 / 0.55,
    "ele_ey": 9.5e-6 ** 2 / 0.056,
    "pro_ex": 95.0e-6 ** 2 / 0.8,
    "pro_ey": 8.5e-6 ** 2 / 0.072,
}


def fig_eic_emittance():
    o = np.genfromtxt(os.path.join(OCT, "eic_emittance_octopus.tsv"),
                      names=True, delimiter="\t")
    b = np.genfromtxt(os.path.join(OCT, "eic_emittance_bb3d.tsv"),
                      names=True, delimiter="\t")
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.7))
    panels = [
        ("(a) electron, damped ($\\tau=400$ turns)", ["ele_ex", "ele_ey"]),
        ("(b) proton, undamped", ["pro_ex", "pro_ey"]),
    ]
    for k, (ax, (title, cols)) in enumerate(zip(axes, panels)):
        for col, ls in zip(cols, ["-", "--"]):
            lab = "$x$" if col.endswith("ex") else "$y$"
            # Damped electron: refer to the design emittance -- damping erases
            # the initial sample.  Undamped proton: refer to each code's OWN
            # initial value, because the initial-sample difference between the
            # codes persists undiminished and would otherwise be read as a
            # difference in growth.  This matches Table 3.
            do_, db_ = (EIC_DESIGN[col], EIC_DESIGN[col]) if col.startswith("ele") \
                       else (o[col][0], b[col][0])
            ax.plot(o["turn"], 100 * (o[col] / do_ - 1), ls, color=BLUE,
                    linewidth=1.3, label=f"Octopus {lab}")
            ax.plot(b["turn"], 100 * (b[col] / db_ - 1), ls, color=ORANGE,
                    linewidth=1.3, alpha=0.85, label=f"BeamBeam3D {lab}")
        ax.set_title(title, loc="left")
        ax.set_xlabel("turn")
        ax.set_xlim(0, max(o["turn"].max(), b["turn"].max()))
        # Not bottom=0: the two codes' turn-0 points sit at -0.27 and -0.42 pp
        # (their initial sampling difference) and were drawn outside the frame,
        # invisible.  Let the data set the bottom.
        ax.set_ylim(bottom=min(-0.6, ax.get_ylim()[0]))
        if k == 0:
            ax.legend(loc="lower center", handlelength=1.6,
                      borderaxespad=0.3, fontsize=6.2, ncol=2,
                      columnspacing=1.1, framealpha=0.92)
        style_axis(ax)
    axes[0].set_ylabel(r"$\epsilon/\epsilon_{\rm design}-1$  [%]")
    axes[1].set_ylabel(r"$\epsilon/\epsilon(0)-1$  [%]")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_eic_emittance.pdf"))
    plt.close(fig)


if __name__ == "__main__":
    fig_noise_floor()
    fig_boundary_jump()
    fig_yokoya_scans()
    fig_error_vs_grid()
    fig_error_vs_aspect()
    fig_coherent_fft()
    fig_eic_modes()
    fig_multislice_spectra()
    fig_eic_emittance()
    print("figures written to", OUT)
