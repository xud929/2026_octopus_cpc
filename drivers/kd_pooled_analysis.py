#!/usr/bin/env python3
"""Pooled (Panel B) analysis of the kick-error decomposition, from the
per-realization dumps written by Octopus validation/kick_decomposition.jl
with OCTOPUS_KD_DUMP set (19 seeds x {round, flat11} x CIC {64, 256}).

Recomputes, deterministically from the dumps:
  - pooled R=1900 B and S per Eq. (error_split) for both grids,
  - the 19 delete-one-block estimates of B256 and S256 and their normal
    intervals,
and, with a RECORDED null seed:
  - the one-sign-per-realization centered Rademacher null of the pooled B256
    and its 95th percentile.

The submitted manuscript's pooled values were computed from arrays that were
never retained; this script plus the dumps closes that archival gap.

Usage: python3 drivers/kd_pooled_analysis.py [dumpdir] [--write]
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DUMP = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") \
    else os.path.join(ROOT, "work", "kd_dump")

SEEDS = [20260728, 1, 11117, 12345, 13579, 22229, 24680, 27182, 31415,
         33331, 44443, 55557, 66661, 777001, 777002, 777003, 77773, 88887,
         98765]
NULL_SEED = 20260812
NULL_DRAWS = 2000


def load(family, grid):
    """Return ex, ey with shape (R_total, npoints), and gnorm."""
    exs, eys, gnorm = [], [], None
    for s in SEEDS:
        base = os.path.join(DUMP, f"kd_seed{s}_{family}_{grid}_CIC")
        npoints, R, g = open(base + "_meta.tsv").read().splitlines()[1].split()
        npoints, R, g = int(npoints), int(R), float(g)
        if gnorm is None:
            gnorm = g
        elif abs(g - gnorm) > 1e-12 * gnorm:
            raise SystemExit(f"gnorm differs across seeds for {family}/{grid}")
        for tag, acc in (("_ex.bin", exs), ("_ey.bin", eys)):
            a = np.fromfile(base + tag, dtype="<f8")
            acc.append(a.reshape(R, npoints))  # column-major (npoints,R) dump
    return np.concatenate(exs), np.concatenate(eys), gnorm


def BS(ex, ey, gnorm):
    """Pooled B and S per Eq. (error_split), normalized by gnorm."""
    B = np.median(np.hypot(ex.mean(0), ey.mean(0))) / gnorm
    S = np.median(np.hypot(ex.std(0, ddof=1), ey.std(0, ddof=1))) / gnorm
    return B, S


def main():
    out_lines = ["# Pooled (Panel B) kick-decomposition statistics from the",
                 "# per-realization dumps (drivers/kd_pooled_analysis.py).",
                 f"# seeds: {','.join(map(str, SEEDS))}",
                 f"# null: one Rademacher sign per realization vector, centered,",
                 f"# {NULL_DRAWS} draws, numpy default_rng seed {NULL_SEED}",
                 "family\tgrid\tpooled_B\tpooled_S\tB_loo_lo\tB_loo_hi"
                 "\tS_loo_lo\tS_loo_hi\tnull95_B"]
    for family in ("round", "flat11"):
        for grid in (64, 256):
            ex, ey, gnorm = load(family, grid)
            R = ex.shape[0]
            B, S = BS(ex, ey, gnorm)
            print(f"{family} {grid}^2 pooled R={R}: "
                  f"B={B:.6e}  S={S:.6e}")
            loo_note = null_note = ("", "", "", "", "")
            if grid == 256:
                # delete-one-block: drop each seed's 100 realizations
                n = len(SEEDS)
                loosB, loosS = [], []
                for i in range(n):
                    keep = np.ones(R, bool)
                    keep[i * 100:(i + 1) * 100] = False
                    b, s = BS(ex[keep], ey[keep], gnorm)
                    loosB.append(b)
                    loosS.append(s)
                loosB, loosS = np.array(loosB), np.array(loosS)
                # jackknife normal interval around the full-sample estimate
                seB = np.sqrt((n - 1) / n * ((loosB - loosB.mean()) ** 2).sum())
                seS = np.sqrt((n - 1) / n * ((loosS - loosS.mean()) ** 2).sum())
                iv = (B - 1.96 * seB, B + 1.96 * seB,
                      S - 1.96 * seS, S + 1.96 * seS)
                print(f"  delete-one-block 95% (jackknife normal): "
                      f"B256 [{iv[0]:.3e}, {iv[1]:.3e}]  "
                      f"S256 [{iv[2]:.3e}, {iv[3]:.3e}]")
                # centered sign-flip null, one sign per realization
                rng = np.random.default_rng(NULL_SEED)
                cx, cy = ex - ex.mean(0), ey - ey.mean(0)
                nulls = np.empty(NULL_DRAWS)
                for t in range(NULL_DRAWS):
                    sgn = rng.integers(0, 2, R) * 2.0 - 1.0
                    nulls[t] = np.median(np.hypot(
                        (cx * sgn[:, None]).mean(0),
                        (cy * sgn[:, None]).mean(0))) / gnorm
                p95 = np.quantile(nulls, 0.95)
                print(f"  null 95th percentile: {p95:.3e}  "
                      f"(B256 {'BELOW' if B < p95 else 'ABOVE'})")
                loo_note = tuple(f"{v:.6e}" for v in iv)
                null_note = loo_note + (f"{p95:.6e}",)
                out_lines.append(
                    f"{family}\t{grid}\t{B:.6e}\t{S:.6e}\t" +
                    "\t".join(f"{v:.6e}" for v in iv) + f"\t{p95:.6e}")
            else:
                out_lines.append(
                    f"{family}\t{grid}\t{B:.6e}\t{S:.6e}\t\t\t\t\t")
    if "--write" in sys.argv:
        out = os.path.join(ROOT, "data", "kd_pooled_panelB.tsv")
        open(out, "w").write("\n".join(out_lines) + "\n")
        print("wrote", out)


if __name__ == "__main__":
    main()
