#!/usr/bin/env python3
"""
nsphere_ic_gen.py

Generates equilibrium N-body initial conditions for the two-component
(dark matter + stars) ultra-faint-galaxy model of Errani, Esser,
Penarrubia & Walker, "Collisional Dynamics of Stars and Dark Matter in
Ultra-Faint Galaxies" (arXiv:2604.06304), via Eddington inversion, and
writes them directly in the binary format expected by nsphere.c's
`read_initial_conditions()` (use nsphere's `--readinit <file>` flag).

This replaces an earlier single-component port of Errani's nbody.py
sampler with a proper THREE-SPECIES model matching the paper's Table 1:

    - Dark matter: exponentially-truncated NFW cusp (paper Eq. 4),
      all particles of equal mass m_DM, species = 0.
    - Low-mass stars: exponential profile (paper Eq. 2), particle
      mass 0.2 Msun, species = 1.
    - High-mass stars: same exponential profile/scale radius as the
      low-mass stars, particle mass 0.8 Msun, species = 2.

Dark matter and both stellar populations are drawn from THEIR OWN
density profile (Eqs. 2 and 4), but all three orbit in the SAME shared
potential sourced by the combined stars+dark-matter system (Eqs. 3+5),
exactly as described in Sec. 2 of the paper. This means two separate
Eddington-inversion distribution functions are built (one for the
dark matter density shape, one for the -- shared -- stellar density
shape), both evaluated against one common potential.

=============================================================================
PHYSICAL PARAMETERS -- taken directly from Table 1 / Eqs. 2-7 of the paper
=============================================================================
Stars (shared by both low- and high-mass populations):
    3D half-light radius            r_h0   = 8.3 pc
    combined stellar mass            M_star = 144 Msun  (72 + 72)
    low-mass star particles          N_low  = 360,  m_low  = 0.2 Msun
    high-mass star particles         N_high = 90,   m_high = 0.8 Msun
    density profile (Eq. 2):  rho_star(r) = rho_0 * exp(-r/r_star)
    3D half-light radius relation:   r_h0 ~= 2.67 * r_star  =>  r_star = r_h0/2.67
    potential (Eq. 3):
        Psi_star(r) = G*M_star*(1 - (1 + 0.5 r/r_star) * exp(-r/r_star)) / r

Dark matter (tidally limited, so the halo's characteristic radius
r_mx0 is truncated to equal the stellar r_h0 -- Sec. 2.2):
    density profile (Eq. 4):  rho_DM(r) = rho_s * r_s * exp(-r/r_s) / r
    circular-velocity peak radius:   r_mx  = 1.79 * r_s      => r_s = r_mx0/1.79
    enclosed mass at r_mx:           M_mx  = 0.54 * M_DM_total
    potential (Eq. 5):
        Psi_DM(r) = G*M_DM_total*(1 - exp(-r/r_s)) / r

    The paper runs three halo masses, parameterized by the initial
    dynamical-to-stellar mass ratio within the half-light radius,
        Upsilon_dyn0 = 1 + M_DM(<r_h0) / M_star(<r_h0)
                     = 1 + M_mx0 / (M_star/2)              (since r_h0 = r_mx0)
    for Upsilon_dyn0 = 3, 10, 30, giving (Table 1):
        M_mx0 = 144, 648, 2088 Msun   =>   M_DM_total = M_mx0 / 0.54
    with dark matter particle mass m_DM = 1e-3 Msun for Upsilon_dyn0 = 3
    and 10, and m_DM = 4e-3 Msun for Upsilon_dyn0 = 30 (paper footnote 4).

=============================================================================
UNITS
=============================================================================
Everything here is computed directly in physical units (kpc, km/s, Msun)
using G_CONST = 4.3e-6 kpc*(km/s)^2/Msun -- this is *exactly* the value
of G_CONST hardcoded in nsphere.c. If nsphere.c's G_CONST is ever changed,
this script's G_CONST must be changed to match.

=============================================================================
nsphere.c BINARY IC FORMAT
=============================================================================
`read_initial_conditions` expects an int32 particle count followed by
that many records of 10 float64 each, in this order:

    r        radius [kpc]
    v        TOTAL speed magnitude [km/s] (nsphere itself multiplies by
             mu and converts km/s -> kpc/Myr immediately after loading --
             this happens even when ICs come from --readinit)
    L        angular momentum r*v*sqrt(1-mu^2) [kpc*km/s]
    ID       0-based particle index (as a double)
    mu       v_radial / v_total, in [-1, 1]
    cos_phi  cosine of a random azimuthal orientation angle (SIDM bookkeeping)
    sin_phi  sine of that same angle
    species  0 = dark matter, 1 = low-mass star (0.2 Msun), 2 = high-mass
             star (0.8 Msun) -- matching nsphere.c's own convention
    mass     per-particle mass [Msun]
    reserved unused, always 0.0

particles[5]/particles[6] (cos_phi, sin_phi) and particles[8] (mass)
must be supplied here because nsphere.c SKIPS its own random-phi
initialization and its own initialize_particle_masses() step whenever
ICs are loaded via --readinit.

Usage:
    python3 nsphere_ic_gen.py --upsilon-dyn0 3 --output ic_errani.bin

    Then in nsphere:
    ./nsphere --readinit ic_errani.bin --nparticles <N printed below> ...
"""

import argparse
import os
import sys
from math import pi

import numpy as np
from scipy.integrate import quad

# =============================================================================
# Physical constant -- MUST match nsphere.c's `#define G_CONST 4.3e-6`
# =============================================================================
G_CONST = 4.3e-6  # kpc * (km/s)^2 / Msun

# =============================================================================
# Paper defaults (arXiv:2604.06304, Table 1 / Eqs. 2-7)
# =============================================================================
R_H0_PC = 8.3            # 3D half-light radius shared by stars, and by the
                          # tidally-truncated DM halo's characteristic radius
M_STAR_TOTAL = 144.0      # Msun, combined stellar mass (both populations)
N_STAR_LOW, M_STAR_LOW = 360, 0.2    # Msun
N_STAR_HIGH, M_STAR_HIGH = 90, 0.8   # Msun

RSTAR_OVER_RH0 = 1.0 / 2.67   # Eq. 2: r_h0 ~= 2.67 r_star
RS_OVER_RMX0 = 1.0 / 1.79     # Eq. 4: r_mx ~= 1.79 r_s
MMX_OVER_MDM = 0.54           # Eq. 4: M(<r_mx) = 0.54 M_DM_total

DEFAULT_DM_MASS = {3: 1.0e-3, 10: 1.0e-3, 30: 4.0e-3}  # Msun, paper footnote 4


# =============================================================================
# Closed-form potential and density-shape functions (Eqs. 2-5)
# =============================================================================
def psi_star(r, M_star_total, r_star):
    """Stellar contribution to Psi(r) = -Phi(r), from paper Eq. 3."""
    x = r / r_star
    return G_CONST * M_star_total * (1.0 - (1.0 + 0.5 * x) * np.exp(-x)) / r


def psi_dm(r, M_dm_total, r_s):
    """Dark matter contribution to Psi(r) = -Phi(r), from paper Eq. 5."""
    x = r / r_s
    return G_CONST * M_dm_total * (1.0 - np.exp(-x)) / r


def nu_star_shape(r, r_star):
    """Unnormalized stellar density shape, paper Eq. 2 (amplitude irrelevant)."""
    return np.exp(-r / r_star)


def nu_dm_shape(r, r_s):
    """Unnormalized DM density shape, paper Eq. 4 (amplitude irrelevant)."""
    return np.exp(-r / r_s) / r


def cdf_star(x):
    """Closed-form enclosed-mass fraction of Eq. 2 at radius r = x*r_star."""
    return 1.0 - (1.0 + x + 0.5 * x * x) * np.exp(-x)


def cdf_dm(x):
    """Closed-form enclosed-mass fraction of Eq. 4 at radius r = x*r_s."""
    return 1.0 - (1.0 + x) * np.exp(-x)


def invert_cdf(cdf_func, u, hi=100.0, iters=60):
    """Vectorized bisection inversion of a monotonic CDF on [0, hi]."""
    lo_arr = np.zeros_like(u)
    hi_arr = np.full_like(u, hi)
    for _ in range(iters):
        mid = 0.5 * (lo_arr + hi_arr)
        below = cdf_func(mid) < u
        lo_arr = np.where(below, mid, lo_arr)
        hi_arr = np.where(below, hi_arr, mid)
    return 0.5 * (lo_arr + hi_arr)


# =============================================================================
# Eddington inversion machinery (shared potential grid, per-species density)
# =============================================================================
def build_distribution_function(R, psi, nu, n_energy_bins, epsrel):
    """
    Builds f(E) for a species with density shape `nu` (array on grid `R`),
    given the shared potential `psi` (array on grid `R`, monotonically
    decreasing with R). Standard isotropic Eddington inversion.
    """
    dndp = np.gradient(nu, psi)
    d2nd2p = np.gradient(dndp, psi)

    f = np.vectorize(
        lambda e: 1.0
        / (np.sqrt(8) * pi * pi)
        * quad(
            lambda p: np.interp(p, psi[::-1], d2nd2p[::-1]) / np.sqrt(e - p),
            0.0,
            e,
            epsrel=epsrel,
        )[0]
    )

    maxE = psi[0]
    minE = maxE / float(n_energy_bins)
    E = np.linspace(minE, maxE, num=n_energy_bins)
    DF = f(E)
    return E, DF


def build_envelope(R, psi, E, DF):
    """Precomputes the v^2*f(E) rejection-sampling envelope on grid R."""

    def dPdr(e, r):
        return np.sqrt(2.0 * (np.interp(r, R, psi) - e)) * r * r

    def PLikelihood(e, r):
        return np.interp(e, E, DF) * dPdr(e, r)

    maxPLikelihood = []
    for RR in R:
        allowed = np.where(E <= np.interp(RR, R, psi))[0]
        if len(allowed) == 0:
            maxPLikelihood.append(0.0)
            continue
        this_max = 1.1 * np.amax(PLikelihood(E[allowed], RR))
        maxPLikelihood.append(this_max)
    return np.array(maxPLikelihood), PLikelihood


def sample_component(
    n_particles, r_of_u, R, psi, E, DF, maxPLikelihood, PLikelihood, rng, draw_batch
):
    """
    Draws n_particles samples of (x,y,z,vx,vy,vz) [physical units: kpc, km/s]
    for one species, given:
      - r_of_u(u): closed-form inverse-CDF mapping uniform u->radius [kpc]
      - R, psi: shared potential grid
      - E, DF, maxPLikelihood, PLikelihood: this species' Eddington inversion products
    Radius is drawn from the species' own closed-form CDF; energy/velocity
    is drawn via rejection sampling exactly as in the original Errani
    nbody.py sampler.
    """
    N = int(n_particles)
    Ndraw = int(draw_batch)

    xx = np.zeros(N)
    yy = np.zeros(N)
    zz = np.zeros(N)
    vx = np.zeros(N)
    vy = np.zeros(N)
    vz = np.zeros(N)

    n = 0
    Efails = 0
    while n < N:
        u = rng.random(Ndraw)
        randR = r_of_u(u)

        psiR = np.interp(randR, R, psi)
        randE = rng.random(Ndraw) * psiR
        rhoE = PLikelihood(randE, randR)
        randY = rng.random(Ndraw) * np.interp(randR, R, maxPLikelihood)
        Missidx = np.where(randY > rhoE)[0]
        Efails += len(Missidx)

        while len(Missidx):
            randE[Missidx] = rng.random(len(Missidx)) * psiR[Missidx]
            rhoE[Missidx] = PLikelihood(randE[Missidx], randR[Missidx])
            randY[Missidx] = rng.random(len(Missidx)) * np.interp(randR[Missidx], R, maxPLikelihood)
            Missidx = np.where(randY > rhoE)[0]
            Efails += len(Missidx)

        okEidx = np.where(randY <= rhoE)[0]
        if len(okEidx) != Ndraw:
            print("      *  Particles went missing. Exit.")
            sys.exit(1)

        missing = N - n
        if len(okEidx) <= missing:
            arrIdx = n + np.arange(0, len(okEidx))
        else:
            arrIdx = n + np.arange(0, missing)
            okEidx = okEidx[:missing]

        Rtheta = np.arccos(2.0 * rng.random(len(okEidx)) - 1.0)
        Rphi = rng.random(len(okEidx)) * 2 * np.pi
        Vtheta = np.arccos(2.0 * rng.random(len(okEidx)) - 1.0)
        Vphi = rng.random(len(okEidx)) * 2 * np.pi
        V = np.sqrt(2.0 * (psiR[okEidx] - randE[okEidx]))

        xx[arrIdx] = randR[okEidx] * np.sin(Rtheta) * np.cos(Rphi)
        yy[arrIdx] = randR[okEidx] * np.sin(Rtheta) * np.sin(Rphi)
        zz[arrIdx] = randR[okEidx] * np.cos(Rtheta)
        vx[arrIdx] = V * np.sin(Vtheta) * np.cos(Vphi)
        vy[arrIdx] = V * np.sin(Vtheta) * np.sin(Vphi)
        vz[arrIdx] = V * np.cos(Vtheta)

        n += len(okEidx)
        print(f"         {100.0 * n / N:.2f} per cent; E rejection ratio {100.0 * Efails / n:.2f}")

    return xx, yy, zz, vx, vy, vz


def vectors_to_nsphere_fields(xx, yy, zz, vx, vy, vz, rng):
    """Reduces 3D (r,v) samples to nsphere's scalar (r, v_total, L, mu) form."""
    r = np.sqrt(xx * xx + yy * yy + zz * zz)
    v = np.sqrt(vx * vx + vy * vy + vz * vz)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = (xx * vx + yy * vy + zz * vz) / (r * v)
    mu = np.nan_to_num(mu, nan=0.0)
    mu = np.clip(mu, -1.0, 1.0)
    L_mag = r * v * np.sqrt(np.clip(1.0 - mu * mu, 0.0, None))
    L_sign = np.where(rng.random(len(r)) < 0.5, -1.0, 1.0)
    ell = L_sign * L_mag
    return r, v, ell, mu


def write_nsphere_ic_file(filename, r, v_total, ell, mu, cos_phi, sin_phi, species, mass):
    """Writes the 10-field binary record format expected by nsphere.c."""
    npts = len(r)
    ids = np.arange(npts, dtype=np.float64)
    reserved = np.zeros(npts, dtype=np.float64)

    header = np.array([npts], dtype=np.int32)
    record = np.column_stack(
        (r, v_total, ell, ids, mu, cos_phi, sin_phi, species, mass, reserved)
    ).astype(np.float64)

    # Create the parent directory (e.g. "../init") if it doesn't exist yet --
    # open() will not create missing directories on its own.
    parent_dir = os.path.dirname(filename)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(filename, "wb") as fp:
        fp.write(header.tobytes())
        fp.write(record.tobytes())

    print(f"Wrote {npts} particles to '{filename}' ({4 + npts * 10 * 8} bytes)")


def main():
    ap = argparse.ArgumentParser(
        description="Generate nsphere.c-compatible ICs for the Errani et al. (2604.06304) ultra-faint-galaxy model.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--upsilon-dyn0", type=int, default=3, choices=[3, 10, 30],
                     help="Initial dynamical-to-stellar mass ratio model from Table 1.")
    ap.add_argument("--dm-only", action="store_true",
                     help="Generate the dark-matter-only reference halo (same halo params as Upsilon_dyn0=3, no stars).")
    ap.add_argument("--dm-mass", type=float, default=None,
                     help="Override dark matter particle mass [Msun] (default: paper value for --upsilon-dyn0).")
    ap.add_argument("--n-dm", type=int, default=None,
                     help="Override total number of DM particles directly (recomputes m_DM = M_DM_total / N).")
    ap.add_argument("--ne", type=int, default=2000, help="Number of energy bins for f(E) (per species).")
    ap.add_argument("--nr", type=int, default=2000, help="Number of radius bins for the shared potential grid.")
    ap.add_argument("--epsrel", type=float, default=1e-6, help="Relative precision for f(E) integration.")
    ap.add_argument("--draw-batch", type=int, default=200000, help="Trial draws per rejection-sampling batch.")
    ap.add_argument("--seed", type=int, default=667408, help="RNG seed.")
    ap.add_argument("--output", type=str, default="ic_errani.bin", help="Output binary filename for nsphere's --readinit.")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)

    # ---- Derive physical parameters from Table 1 ----
    r_h0_kpc = R_H0_PC * 1e-3
    r_star_kpc = r_h0_kpc * RSTAR_OVER_RH0
    r_s_kpc = r_h0_kpc * RS_OVER_RMX0

    upsilon_for_mass = 3 if args.dm_only else args.upsilon_dyn0
    M_mx0 = (upsilon_for_mass - 1) * (M_STAR_TOTAL / 2.0)
    M_dm_total = M_mx0 / MMX_OVER_MDM

    m_dm = args.dm_mass if args.dm_mass is not None else DEFAULT_DM_MASS[upsilon_for_mass]
    if args.n_dm is not None:
        n_dm = args.n_dm
        m_dm = M_dm_total / n_dm
    else:
        n_dm = int(round(M_dm_total / m_dm))

    include_stars = not args.dm_only
    M_star_total_potential = M_STAR_TOTAL if include_stars else 0.0
    n_star_low = N_STAR_LOW if include_stars else 0
    n_star_high = N_STAR_HIGH if include_stars else 0
    n_star_total = n_star_low + n_star_high

    print(f"Upsilon_dyn0 = {upsilon_for_mass}{' (dm-only mode)' if args.dm_only else ''}")
    print(f"r_star = {r_star_kpc*1e3:.4f} pc, r_s = {r_s_kpc*1e3:.4f} pc")
    print(f"M_DM_total = {M_dm_total:.4f} Msun, m_DM = {m_dm:.4e} Msun, N_DM = {n_dm}")
    if include_stars:
        print(f"M_star_total = {M_STAR_TOTAL} Msun, N_low = {n_star_low} (m=0.2), N_high = {n_star_high} (m=0.8)")
    n_total = n_dm + n_star_total
    print(f"Total particles: {n_total}")

    # ---- Shared radius/potential grid ----
    scale_min = min(r_s_kpc, r_star_kpc) if include_stars else r_s_kpc
    scale_max = max(r_s_kpc, r_star_kpc) if include_stars else r_s_kpc
    r_min = 1e-4 * scale_min
    r_max = 60.0 * scale_max
    R = np.logspace(np.log10(r_min), np.log10(r_max), num=args.nr)

    psi = psi_dm(R, M_dm_total, r_s_kpc)
    if include_stars:
        psi = psi + psi_star(R, M_star_total_potential, r_star_kpc)

    # ---- Dark matter component: Eddington inversion + sampling ----
    print("      *  Building DM distribution function f(E)")
    nu_dm = nu_dm_shape(R, r_s_kpc)
    E_dm, DF_dm = build_distribution_function(R, psi, nu_dm, args.ne, args.epsrel)
    if np.any(DF_dm < 0):
        print("      *  DM DF < 0 somewhere -- try increasing --nr/--ne. Exiting.")
        sys.exit(1)
    maxPL_dm, PLikelihood_dm = build_envelope(R, psi, E_dm, DF_dm)

    def r_of_u_dm(u):
        x = invert_cdf(cdf_dm, u)
        return x * r_s_kpc

    print("      *  Sampling DM particles")
    xx_dm, yy_dm, zz_dm, vx_dm, vy_dm, vz_dm = sample_component(
        n_dm, r_of_u_dm, R, psi, E_dm, DF_dm, maxPL_dm, PLikelihood_dm, rng, args.draw_batch
    )
    r_dm, v_dm, ell_dm, mu_dm = vectors_to_nsphere_fields(xx_dm, yy_dm, zz_dm, vx_dm, vy_dm, vz_dm, rng)
    species_dm = np.zeros(n_dm)
    mass_dm = np.full(n_dm, m_dm)

    r_all = [r_dm]; v_all = [v_dm]; ell_all = [ell_dm]; mu_all = [mu_dm]
    species_all = [species_dm]; mass_all = [mass_dm]

    # ---- Stellar component (shared shape for low- and high-mass) ----
    if include_stars:
        print("      *  Building stellar distribution function f(E)")
        nu_star = nu_star_shape(R, r_star_kpc)
        E_star, DF_star = build_distribution_function(R, psi, nu_star, args.ne, args.epsrel)
        if np.any(DF_star < 0):
            print("      *  Stellar DF < 0 somewhere -- try increasing --nr/--ne. Exiting.")
            sys.exit(1)
        maxPL_star, PLikelihood_star = build_envelope(R, psi, E_star, DF_star)

        def r_of_u_star(u):
            x = invert_cdf(cdf_star, u)
            return x * r_star_kpc

        print("      *  Sampling stellar particles")
        xx_s, yy_s, zz_s, vx_s, vy_s, vz_s = sample_component(
            n_star_total, r_of_u_star, R, psi, E_star, DF_star, maxPL_star, PLikelihood_star,
            rng, args.draw_batch
        )
        r_s_arr, v_s_arr, ell_s_arr, mu_s_arr = vectors_to_nsphere_fields(
            xx_s, yy_s, zz_s, vx_s, vy_s, vz_s, rng
        )

        # Randomly designate n_star_low of the n_star_total draws as low-mass
        # (species=1, mass=0.2) and the rest as high-mass (species=2, mass=0.8).
        # All samples come from the identical stellar distribution, so which
        # indices get which label does not bias either population.
        perm = rng.permutation(n_star_total)
        species_s = np.empty(n_star_total)
        mass_s = np.empty(n_star_total)
        low_idx = perm[:n_star_low]
        high_idx = perm[n_star_low:]
        species_s[low_idx] = 1
        mass_s[low_idx] = M_STAR_LOW
        species_s[high_idx] = 2
        mass_s[high_idx] = M_STAR_HIGH

        r_all.append(r_s_arr); v_all.append(v_s_arr); ell_all.append(ell_s_arr); mu_all.append(mu_s_arr)
        species_all.append(species_s); mass_all.append(mass_s)

    r_final = np.concatenate(r_all)
    v_final = np.concatenate(v_all)
    ell_final = np.concatenate(ell_all)
    mu_final = np.concatenate(mu_all)
    species_final = np.concatenate(species_all)
    mass_final = np.concatenate(mass_all)

    phi = 2.0 * np.pi * rng.random(n_total)
    cos_phi = np.cos(phi)
    sin_phi = np.sin(phi)

    out_file = "init/" + args.output
    write_nsphere_ic_file(
        out_file, r_final, v_final, ell_final, mu_final, cos_phi, sin_phi, species_final, mass_final
    )

    print("      *  All done :o)")
    print(f"Run nsphere with: --readinit {out_file} --nparticles {n_total} "
          f"--halo-mass {M_dm_total:g} --scale-radius {r_s_kpc:g}")


if __name__ == "__main__":
    main()
