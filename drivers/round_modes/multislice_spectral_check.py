#!/usr/bin/env python3
"""Spectral comparison of regenerated multislice arms vs archived reductions.

Manuscript estimator (Sec. "Multi-slice cross-code benchmark"): symmetric Hann
window on the difference-mode centroid series, search band
[Q0-0.004, Q0+0.010] with Q0=0.31 (x) / 0.32 (y), local maxima above 1% of the
in-band maximum, three-bin parabolic refinement.  The paper compares the
noise-excited Octopus x trace against the coherently kicked BeamBeam3D x
trace: six peaks each, frequency-rank pairing, median/max
|dQ| = (1.20, 3.84)e-4.
"""
import numpy as np
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


def load(path, col_a, col_b):
    rows = []
    for line in open(path):
        if line.startswith(("#", "turn")):
            continue
        f = line.split()
        rows.append((float(f[col_a]), float(f[col_b])))
    a = np.array(rows)
    return a[:, 0] - a[:, 1]  # difference mode


def peaks(series, q0, band=(-0.004, 0.010), thresh=0.01):
    n = len(series)
    w = np.hanning(n)
    amp = np.abs(np.fft.rfft(series * w))
    q = np.fft.rfftfreq(n)
    sel = (q >= q0 + band[0]) & (q <= q0 + band[1])
    idx = np.where(sel)[0]
    cutoff = thresh * amp[idx].max()
    out = []
    for i in idx:
        if amp[i] < cutoff or i == 0 or i + 1 >= len(amp):
            continue
        if amp[i] >= amp[i - 1] and amp[i] >= amp[i + 1]:
            a, b, c = amp[i - 1], amp[i], amp[i + 1]
            denom = a - 2 * b + c
            delta = 0.5 * (a - c) / denom if denom != 0 else 0.0
            out.append(q[i] + delta * (q[1] - q[0]))
    return np.array(out)


def report(label, fresh_series, arch_series, q0):
    pf, pa = peaks(fresh_series, q0), peaks(arch_series, q0)
    print(f"{label}: fresh {len(pf)} peaks, archived {len(pa)} peaks")
    print(f"  fresh   : {np.array2string(pf, precision=6)}")
    print(f"  archived: {np.array2string(pa, precision=6)}")
    if len(pf) == len(pa):
        d = np.abs(pf - pa)
        print(f"  paired |dQ| median={np.median(d):.2e} max={d.max():.2e}")
    return pf, pa


def main():
    d = os.path.join(ROOT, "data")
    raw = os.environ.get("OCTOPUS_RAW_DIR",
                         os.path.join(ROOT, "work", "round_modes_out", "raw"))

    arch_noise_x = load(os.path.join(d, "multislice_centroids_octopus_noise.tsv"), 1, 2)
    arch_kick_x = load(os.path.join(d, "multislice_centroids_octopus_kicked.tsv"), 1, 2)
    arch_bb3d_x = load(os.path.join(d, "multislice_centroids_bb3d.tsv"), 1, 2)
    fresh_noise = np.loadtxt(os.path.join(raw, "multislice_noise.tsv"), skiprows=4)
    fresh_kick = np.loadtxt(os.path.join(raw, "multislice_kicked.tsv"), skiprows=4)
    # raw runner rows: turn x1 x2 y1 y2, including turn 0; archive starts at 1
    fn_x = fresh_noise[1:, 1] - fresh_noise[1:, 2]
    fk_x = fresh_kick[1:, 1] - fresh_kick[1:, 2]

    print("== Octopus noise arm, x (the figure's Octopus trace) ==")
    pf, pa = report("noise x", fn_x, arch_noise_x, 0.31)

    print("\n== Octopus kicked arm, x ==")
    report("kicked x", fk_x, arch_kick_x, 0.31)

    print("\n== paper claim: Octopus-noise vs BB3D-kicked, x ==")
    pb = peaks(arch_bb3d_x, 0.31)
    for tag, po in (("fresh", pf), ("archived", pa)):
        if len(po) == len(pb):
            dq = np.abs(np.sort(po) - np.sort(pb))
            print(f"  {tag} octopus-noise vs bb3d: {len(pb)} peaks, "
                  f"median={np.median(dq):.3e} max={dq.max():.3e} "
                  f"(paper: 1.20e-4, 3.84e-4; max bins={dq.max()*4096:.2f})")
        else:
            print(f"  {tag}: peak count differs from bb3d ({len(po)} vs {len(pb)})")


if __name__ == "__main__":
    main()
