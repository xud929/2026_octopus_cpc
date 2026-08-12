BeamBeam3D control run: identical to ../beam{1,2}_multislice.in except that
beam 1's initial centroid offset cn.x = cn.y = 1.06d-5 (0.1 sigma) is set to
zero, so both beams start centred and the coherent modes are excited only by
macroparticle sampling noise -- the same excitation as the Octopus
noise-excited arm.  4096 turns, 5 slices, as archived.

Purpose: test whether the measured mode positions depend on the excitation.
They do not.  Analysed with validation/coherent_beam_beam_modes_beambeam3d.jl:

                  offset (archived)   no offset (this run)   difference
  Q_sigma x         0.310747            0.310749             2e-6
  Q_pi    x         0.313430            0.313452             2.2e-5
  Q_sigma y         0.320680            0.320684             4e-6
  Q_pi    y         0.325192            0.325214             2.2e-5

The largest shift is 0.09 of an FFT bin (1/4096 = 2.44e-4).

Run with the system OpenMPI, not a conda one:
  /usr/lib64/openmpi/bin/mpirun -np 2 ./xmain      (~634 s)
