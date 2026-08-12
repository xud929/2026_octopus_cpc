#!/usr/bin/env python3
"""Reduce a BB3D eicdamp run to the archived emittance-TSV layout and compare.

Per the validation-script header: emittance is column 7 of fort.24/25
(beam 1 = electron x/y) and fort.34/35 (beam 2 = proton x/y).  The archived
eic_emittance_bb3d.tsv samples every 16 turns from 0 to 8192 (513 rows).

Usage: python3 drivers/eicdamp_reduce.py <rundir> [--write <out.tsv>]
Compares against data/eic_emittance_bb3d.tsv and prints the verdict.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def col(rundir, fname, index):
    out = {}
    for line in open(os.path.join(rundir, fname)):
        f = line.split()
        if len(f) > index:
            out[int(float(f[0]))] = f[index]
    return out


def main():
    rundir = sys.argv[1]
    series = {
        "ele_ex": col(rundir, "fort.24", 6),
        "ele_ey": col(rundir, "fort.25", 6),
        "pro_ex": col(rundir, "fort.34", 6),
        "pro_ey": col(rundir, "fort.35", 6),
    }
    arch_rows = [l.split() for l in
                 open(os.path.join(ROOT, "data", "eic_emittance_bb3d.tsv"))
                 if not l.startswith(("#", "turn"))]
    worst = 0.0
    n = mism = missing = 0
    for row in arch_rows:
        t = int(row[0])
        for i, key in enumerate(("ele_ex", "ele_ey", "pro_ex", "pro_ey")):
            n += 1
            fresh = series[key].get(t)
            if fresh is None:
                missing += 1
                continue
            a, b = float(row[1 + i]), float(fresh)
            rel = abs(a - b) / max(abs(a), 1e-300)
            worst = max(worst, rel)
            if a != b:
                mism += 1
                if mism <= 3:
                    print(f"differs: turn {t} {key} archived={row[1+i]} fresh={fresh}")
    print(f"rows={len(arch_rows)} cells={n} missing={missing} "
          f"non-bit-identical={mism} worst_rel={worst:.3e}")
    if "--write" in sys.argv:
        out = sys.argv[sys.argv.index("--write") + 1]
        with open(out, "w") as io:
            io.write("turn\tele_ex\tele_ey\tpro_ex\tpro_ey\n")
            for t in sorted(series["ele_ex"]):
                if t % 16 == 0:
                    io.write("\t".join([str(t)] + [series[k][t] for k in
                             ("ele_ex", "ele_ey", "pro_ex", "pro_ey")]) + "\n")
        print("wrote", out)


if __name__ == "__main__":
    main()
