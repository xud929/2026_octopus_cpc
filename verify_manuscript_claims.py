#!/usr/bin/env python3
"""Whitespace-normalized check that claimed-removed phrases are actually gone.

A plain grep on LaTeX misses any phrase the source line-wraps: "ships\nwith the
driver" does not match "ships with the driver".  That failure let a fix be
reported as applied when the sentence was still in the file.  Normalize all
whitespace to single spaces before searching.
"""
import os
import re
import sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manuscript", "main.tex")
flat = re.sub(r"\s+", " ", open(SRC).read())

MUST_BE_ABSENT = [
    "$1.158$",
    # round 25: single-ensemble numbers, shown non-representative by replication
    "in all six matched pairs",
    "by a factor $4.7$--$7.4$",
    "it rises by $9.7$--$15.6\\%$",
    "more than $16\\%$ in either direction",
    "at least $4.7\\times$",
    "$4.2\\pm0.7$",
    "$18.5\\pm1.6\\%$",
    "all $54$ matched",
    "nine independent ensembles",
    "ships with the driver that produced it",
    "Everything else in the package",
    "plane assignment differs from the wide-plane scan",
    "overestimates the measured 2D value",
    "Quantitative $\\Lambda$ therefore requires the full 2D treatment or direct simulation; the 1D models remain useful for structure",
    "single realizations per entry",
    "the four solver columns share the same sampled source realization",
    "no tested option moves the fluctuation by more than $3\\%$",
    "the fluctuation not at all",
    "rises monotonically by a factor $2.4$",
    "of order $900$ individual",
    "genuinely more transform work",
    "gather/scatter compaction alone",
    "far below both FP64 and bandwidth peaks",
    "Luminosity accounting is a third",
    "three levers the campaign did",
    "$3.2$--$3.4$ in the",
    "$5$--$16\\%$ over the",
    "against $0.306$~s",
    "$\\sim$$70\\times$ smaller",
    "the same realization",
    "3$--$5\\times$ below what independent columns would give.",
    # round 22: abstract/summary drift from the 256^2 extension (R5 A1-A3)
    "and none\nreduces it",
    "and none reduces it",
    "by $4$--$32\\%$ while moving the fluctuation",
    "a factor $5$ or more in the systematic",
    # round 22: wrong validity range and wrong composition order
    "fails for $r\\lesssim0.7$",
    "maps composed\n\\emph{left to right}",
    "agree to $1.2$--$1.6\\%$ wherever the",
    # round 22: enumeration R3 asked three times to drop
    "the FP64 estimate of Section~\\ref{sec:protocol}, the plane-count",
]

MUST_BE_PRESENT = [
    "$355$~GFLOP/s",
    "$17.5\\%$",
    "transform staging and normalization",
    "$3600$ host-synchronizing reductions",
    "Page's",
    "$L=42$",
    "1.213",
    "rigid-bunch limit",
    "$1.162$",
    "smallest difference this design could have detected",
    "$14.4\\times$",
    "$1.17\\times$",
    "$0.072$, $0.098$, $0.135$, $0.162$ and $0.085$~pp",
    "four levers",
    # round 22 fixes, each verified against data before being written
    "right to left",
    "$18.3$--$40.5\\%$",
    "$2.7\\sigma$ ($x$) and $2.1$--$2.6\\sigma$ ($y$)",
    "Every other use of it in this paper is flagged at the",
    "$0.22\\%$ or better at every",
    "reciprocal} aspect ratio $r=11.1$",
    # round 23: R1 showed "pooling" does not yield 2.1 sigma -- adopting the
    # x-plane scatter does (2.05); a literal pooled SD gives 2.26.  Assert the
    # operation is named, so the number and the wording cannot drift apart.
    "\\emph{adopt} the $x$-plane scatter",
    "neither is the\nbetter determined",
    "a factor $8$ low and the outlier",
    # round 25: replicated over nine ensembles, with spread
    "nineteen independent ensembles",
    "$18.5\\pm1.3\\%$",
    "$(4.69\\pm0.14)\\times10^{-4}$",
    "all $114$ matched",
    "one-sided bounds, not",
    "quoted as $2.1$--$2.6\\sigma$",
]



# --- Structural checks (R5): a fixed phrase list cannot catch a figure that
# --- no longer matches its data, nor a series drawn outside its own axes.
def check_figures():
    """Every committed figure must be byte-reproducible from the archived data,
    and every plotted series must lie inside its axis limits."""
    import glob
    import hashlib
    import os
    import subprocess
    import sys as _sys

    here = os.path.dirname(os.path.abspath(__file__))
    def content_hash(path):
        """Hash PDF content ignoring the embedded creation/modification dates,
        which change on every run and are not part of the figure."""
        raw = open(path, "rb").read()
        raw = re.sub(rb"/(CreationDate|ModDate)\s*\([^)]*\)", b"", raw)
        raw = re.sub(rb"/ID\s*\[[^\]]*\]", b"", raw)
        return hashlib.sha256(raw).hexdigest()

    before = {f: content_hash(f)
              for f in sorted(glob.glob(os.path.join(here, "figs", "*.pdf")))}
    r = subprocess.run([_sys.executable, os.path.join(here, "make_figures.py")],
                       capture_output=True, cwd=here)
    if r.returncode != 0:
        print("FIGURES      : make_figures.py failed")
        return 1
    bad = 0
    for f, h in before.items():
        if content_hash(f) != h:
            print(f"FIGURE STALE : {os.path.basename(f)} is not what its data produces")
            bad += 1
    return bad


def check_axis_limits():
    """Flag data drawn outside the limits finally set on its Axes.

    An earlier version shimmed ``Axes.plot`` only.  R5 demonstrated the gap:
    the Yokoya panel draws its measured points with ``ax.errorbar``, so a point
    moved outside ylim went unreported even though the committed PDF matched --
    in the very panel the check was built for.  Walking the artists actually
    attached to each Axes at savefig time sees plot, errorbar, scatter and
    step alike, needs no per-call shim, and checks x against xlim as well.
    """
    import os
    import runpy

    here = os.path.dirname(os.path.abspath(__file__))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.figure as _figure
    import numpy as _np

    problems = []
    orig_savefig = _figure.Figure.savefig

    from matplotlib.collections import PathCollection

    NOMARKER = (None, "None", "none", "", " ")

    def series(ax):
        """(kind, xdata, ydata, strict) for every data-space artist on ax.

        strict=True means EVERY point must be inside: a marker that lands
        outside the axis is invisible data, which is the defect being hunted.
        strict=False means only a series entirely outside is reported: a
        continuous curve running past the axis is clipped on purpose and is
        not a defect (e.g. the theory curve drawn over a wider xi range).
        """
        out = []
        for ln in ax.lines:
            # axhline/axvline/axhspan use blended transforms, where one
            # coordinate is an axes fraction and would false-positive.
            if ln.get_transform() is not ax.transData:
                continue
            marked = ln.get_marker() not in NOMARKER
            # errorbar(fmt="o") puts its data markers here, which is exactly
            # the artist the previous Axes.plot shim could not see.
            out.append(("marker" if marked else "line",
                        _np.asarray(ln.get_xdata(), dtype=float),
                        _np.asarray(ln.get_ydata(), dtype=float), marked))
        for col in ax.collections:
            # Only scatter carries real per-point offsets.  A PolyCollection
            # from axhspan/fill_between reports a default offset of [[0, 0]],
            # which is not data; error-bar LineCollections are redundant with
            # the marker line above and may legitimately extend past the axis.
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
                    # A marker outside the axis is invisible data, so it gets
                    # essentially no tolerance: R5 demonstrated that a 5% pad
                    # is 0.0625 in Lambda on the Yokoya panel, wider than any
                    # difference Sec. 5.1 discusses, so a point at 1.2657 slid
                    # past a 1.25 limit undetected.  The epsilon only absorbs
                    # float noise for a point sitting exactly on the limit.
                    # Continuous curves keep the 5% pad, where it earns its
                    # place by not reporting deliberate clipping.
                    # One tight tolerance for every series: the 5% pad on
                    # marker-less series was itself swallowing hidden points
                    # (Fig. 8(a)'s turn-0 point at -0.269 against a ylim of 0).
                    # The fraction test below does the discriminating instead.
                    pad = 1e-9 * (hi - lo)
                    outside = (v > hi + pad) | (v < lo - pad)
                    frac = outside.sum() / outside.size
                    # Keying strictness off the marker alone left every
                    # marker-less DATA series unchecked (R5 hid 23 of 513 points
                    # in Fig. 8(a) and the harness passed).  Discriminate by how
                    # MUCH is outside instead: a handful of points beyond the
                    # axis is hidden data, whichever way it was drawn, while a
                    # dense curve running past the frame -- a spectrum's noise
                    # floor below a log axis, a theory curve over a wider range
                    # -- is deliberate range selection.
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
        os.chdir(here)
        runpy.run_path(os.path.join(here, "make_figures.py"), run_name="__main__")
    finally:
        os.chdir(cwd)
        _figure.Figure.savefig = orig_savefig

    for p in sorted(set(problems)):
        print(p)
    return len(set(problems))




# --- Derived-claim checks (R4): a phrase list catches STALE text, not WRONG
# --- arithmetic.  Both defects that reached referees in rounds 20-21 were
# --- numbers written fresh from memory of a neighbouring cell, so they were in
# --- no list.  These recompute each claim from data/ and assert it appears.
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _cells():
    import glob
    import statistics as st

    def load(path):
        out, fam = {}, None
        for line in open(path):
            if line.startswith("# family="):
                fam = line.split("family=")[1].split()[0]
                continue
            if line.startswith("#") or line.startswith("family_case"):
                continue
            f = line.split()
            if len(f) >= 5:
                out[(fam, f[0])] = [float(x) for x in f[1:5]]
        return out

    tab = load(os.path.join(DATA, "flat_beam_noise_floor.tsv"))
    seeds = [load(f) for f in sorted(glob.glob(os.path.join(DATA, "nf_seed_*.tsv")))]
    out = []
    for k in sorted(tab):
        if "deterministic" in k[1].lower():
            continue
        for i in range(4):
            v = [sd[k][i] for sd in seeds if k in sd]
            if len(v) >= 3:
                m, s_ = st.mean(v), st.stdev(v)
                # column 0 is the soft-Gaussian closure; 1-3 are the mesh
                # solvers (PIC, hybrid, spectral).  The caption quotes the two
                # groups separately because their scatter differs by 2x.
                out.append((abs(m - tab[k][i]) / s_, 100 * s_ / m,
                            100 * (m / tab[k][i] - 1), i))
    return out


def check_derived():
    """Recompute each derived claim and assert the manuscript states it."""
    import statistics as st
    bad = 0

    def want(value, fmt, label):
        """Assert the manuscript states `value`.

        Match the number as a standalone token rather than with fixed
        surrounding markup: the source writes ranges as "$1.8$--$19.8\\%$",
        so requiring a literal "$19.8$" fails on a number that is present.
        """
        nonlocal bad
        want_str = re.sub(r"\s+", " ", fmt.format(value))
        num = re.search(r"\d+(?:\.\d+)?", want_str)
        found = (re.search(r"(?<![\d.])" + re.escape(num.group()) + r"(?![\d])", flat)
                 if num else None) and want_str.strip("$") in flat.replace("$", "")
        if not found:
            print(f"DERIVED      : {label} -> manuscript lacks {want_str}")
            bad += 1

    cells = _cells()
    want(len(cells), "the {} stochastic cells", "Table 1 stochastic cell count")
    want(sum(1 for c in cells if c[0] > 1), "{}", "Table 1 cells beyond 1 SD")
    want(round(max(c[0] for c in cells), 1), "${:.1f}$", "worst cell in SD")
    # The caption quotes the mesh-solver and soft-Gaussian scatter ranges
    # separately, so assert those four bounds rather than a global min/max.
    mesh = [c[1] for c in cells if c[3] >= 1]
    soft = [c[1] for c in cells if c[3] == 0]
    print(f"  [computed] mesh scatter {min(mesh):.1f}-{max(mesh):.1f}%, "
          f"soft-Gaussian {min(soft):.1f}-{max(soft):.1f}%, "
          f"{sum(1 for c in cells if c[0] > 1)}/{len(cells)} cells beyond 1 SD, "
          f"worst {max(c[0] for c in cells):.2f} SD")
    for v, lbl in ((min(mesh), "mesh scatter min"), (max(mesh), "mesh scatter max"),
                   (min(soft), "soft-G scatter min"), (max(soft), "soft-G scatter max")):
        want(round(v, 1), "${:.1f}$", lbl)

    # Box-convergence of the 1D particle solver (R3 m2).  The manuscript's
    # claim that the two 1D solvers agree once the box is converged must come
    # from the archive, not from memory: assert the L=192 spreads it quotes.
    box, sim = {}, {}
    for line in open(os.path.join(DATA, "yokoya_box_convergence.tsv")):
        if line.startswith(("#", "aspect")):
            continue
        f = line.split()
        box[(float(f[0]), float(f[1]))] = float(f[5])   # spread vs matrix, %
        sim[(float(f[0]), float(f[1]))] = float(f[3])   # Y_1d_sim
    conv = {r: box[(r, 192.0)] for r, L in box if L == 192.0}
    print("  [computed] box-converged spreads at L=192: "
          + ", ".join(f"r={r:g}:{v:.2f}%" for r, v in sorted(conv.items())))
    for r in (0.5, 1.0, 11.111, 50.0):
        want(round(conv[r], 2), "${:.2f}\\%$", f"box-converged spread at r={r:g}")
    # and that the default-box curve's offset quoted in the figure caption is
    # the archived L=24 vs L=192 difference at the two ends of the plotted range
    # How far the plotted L=24 curve sits BELOW its own converged value --
    # a relative offset of the curve itself, not a difference of the two
    # spread-vs-matrix percentages (those differ by ~0.05 pp and would give
    # 1.6% where the curve's true offset is 1.5%).
    for r in (0.5, 1.0):
        off = 100 * (sim[(r, 192.0)] - sim[(r, 24.0)]) / sim[(r, 192.0)]
        want(round(off, 1), "${:.1f}\\%$", f"default-box offset at r={r:g}")

    # Original Table 2 per-seed values live in a comment header.
    for line in open(os.path.join(DATA, "lambda_tuneswap_control.tsv")):
        if line.startswith("# Original run"):
            ly = [float(x) for x in line.split("Lambda_y =")[1].split(",")]
            want(round(st.mean(ly), 3), "${:.3f}", "Table 2 Lambda_y mean")
            break
    return bad


def check_frozen_snapshot():
    """The highest-numbered round snapshot must be byte-identical to main.tex.

    R3's point, and it is the paper's own Sec. 7 rule turned on this script:
    "main.tex and main_roundNN_frozen.tex are the same file" was reported as an
    invariant when it was a habit I had to remember after every edit, and
    md5-comparing against a *stale* snapshot returns a clean pass.  Asserting
    it here makes the freeze an enforced property instead of a maintained one.
    """
    import glob

    # [0-9] in the glob, not *: `main_round_final_frozen.tex` would otherwise
    # match and make the int() below raise.  It would fail loudly rather than
    # silently, but there is no reason to accept even that.
    snaps = sorted(glob.glob(os.path.join(os.path.dirname(SRC),
                                          "main_round[0-9]*_frozen.tex")))
    if not snaps:
        print("SNAPSHOT     : no main_round[0-9]*_frozen.tex found")
        return 1
    latest = max(snaps, key=lambda p: int(re.search(r"round(\d+)", p).group(1)))
    if open(latest, "rb").read() != open(SRC, "rb").read():
        print(f"SNAPSHOT     : {os.path.basename(latest)} is stale "
              f"(differs from main.tex) -- refresh it before reporting a freeze")
        return 1
    return 0


bad = check_frozen_snapshot()
for p in MUST_BE_ABSENT:
    if re.sub(r"\s+", " ", p) in flat:
        print(f"STILL PRESENT: {p[:70]}")
        bad += 1
for p in MUST_BE_PRESENT:
    if re.sub(r"\s+", " ", p) not in flat:
        print(f"MISSING      : {p[:70]}")
        bad += 1
bad += check_derived()
bad += check_figures()
bad += check_axis_limits()
print("ALL CHECKS PASS" if bad == 0 else f"{bad} problem(s)")
sys.exit(1 if bad else 0)
