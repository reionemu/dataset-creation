# -----------------------------------------------------------------------------
# Extend an existing Latin Hypercube sample with new parameter sets. New points
# fill only the strata left empty by the existing points, so the combined set
# is a Latin Hypercube when the total is a multiple of the base size. The base
# rows are written unchanged, followed by the new rows.
# Robert Pearce
# -----------------------------------------------------------------------------

from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist, pdist
from scipy.stats import qmc

REPO_ROOT = Path(__file__).resolve().parents[1]

# Existing parameter file to build on
BASE_FILE = REPO_ROOT / "campaigns/v6/params_v6.txt"
# Output directory and file name for the combined parameter file
OUT = REPO_ROOT / "campaigns/v7"
FILE_NAME = "params_v7.txt"

# Number of new samples to add (a multiple of the base size keeps an exact LHS)
NUM_NEW = 3000
# Seed for reproducible results (use a different seed from the base run)
SEED = 456
# Number of swap iterations used to spread out the new points
NUM_ITER = 20_000

# Params and their bounds (must match the base run)
PARAMS = [
    ("zmean", 7.0, 9.0),
    ("alpha", 0.10, 0.90),
    ("kb", 0.10, 2.0),
    ("b0", 0.10, 0.80),
]


def strata_filled(unit: np.ndarray) -> np.ndarray:
    """
    Return the fraction of the n strata occupied in each dimension
    """
    n = len(unit)
    cells = np.floor(unit * n).astype(int)
    return np.array([len(np.unique(c)) / n for c in cells.T])


def fill_empty_strata(base: np.ndarray, m: int, rng: np.random.Generator) -> np.ndarray:
    """
    Place m new points in the strata left empty by the base points
    base: (n x d) existing points in the unit hypercube
    m: Number of new points
    rng: Random generator
    Returns: (m x d) new points in the unit hypercube
    """
    # Total number of strata per dimension after augmentation
    n_total = len(base) + m
    cols = []
    for j in range(base.shape[1]):
        # Strata already occupied by the base points in this dimension
        occupied = np.floor(base[:, j] * n_total).astype(int)
        empty = np.setdiff1d(np.arange(n_total), occupied)
        # If base points collide (total not a multiple of base size), more
        # than m strata are empty; keep m of them spread across the range
        if len(empty) > m:
            keep = np.round(np.linspace(0, len(empty) - 1, m)).astype(int)
            empty = empty[keep]
        # Assign the empty strata to new points in random order
        cols.append(rng.permutation(empty))
    # Draw a uniform position within each assigned stratum
    cells = np.array(cols).T
    return (cells + rng.random(cells.shape)) / n_total


def spread_new_points(
    base: np.ndarray, new: np.ndarray, n_iter: int, rng: np.random.Generator
) -> np.ndarray:
    """
    Increase the smallest distance between each new point and all other points
    by swapping stratum assignments between new points within one dimension.
    Swaps keep every stratum filled, so the Latin property is preserved.
    """
    n, m = len(base), len(new)
    new = new.copy()
    # Distances from each new point to every base and new point
    dist = cdist(new, np.vstack([base, new]))
    dist[np.arange(m), n + np.arange(m)] = np.inf

    def update_rows(idx: np.ndarray):
        # Recompute distances for the swapped points (rows and columns)
        rows = cdist(new[idx], np.vstack([base, new]))
        rows[np.arange(len(idx)), n + idx] = np.inf
        dist[idx] = rows
        dist[:, n + idx] = rows[:, n:].T

    best = dist.min()
    for _ in range(n_iter):
        # Swap the worst-placed new point with a random one in one dimension
        worst = np.unravel_index(np.argmin(dist), dist.shape)[0]
        other = rng.integers(m)
        if other == worst:
            continue
        j = rng.integers(new.shape[1])
        idx = np.array([worst, other])
        new[idx, j] = new[idx[::-1], j]
        update_rows(idx)
        score = dist.min()
        if score > best:
            best = score
        else:
            # Revert the swap
            new[idx, j] = new[idx[::-1], j]
            update_rows(idx)
    return new


def main():
    # Take names and bounds
    names = [name for (name, _lo, _hi) in PARAMS]
    lows = np.array([lo for (_name, lo, _hi) in PARAMS])
    highs = np.array([hi for (_name, _lo, hi) in PARAMS])

    # Load the base samples and map them to the unit hypercube
    base_phys = np.loadtxt(BASE_FILE, comments="#")
    if base_phys.shape[1] != len(PARAMS):
        raise ValueError(f"{BASE_FILE} has {base_phys.shape[1]} columns")
    if np.any(base_phys < lows) or np.any(base_phys > highs):
        raise ValueError(f"{BASE_FILE} has samples outside PARAMS bounds")
    base = qmc.scale(base_phys, lows, highs, reverse=True)
    n = len(base)
    print(f"Base: {n} samples from {BASE_FILE.name}")
    print(f"\tStrata filled at n={n}: {strata_filled(base)}")

    # Place new points in the empty strata, then spread them out
    rng = np.random.default_rng(SEED)
    new = fill_empty_strata(base, NUM_NEW, rng)
    new = spread_new_points(base, new, NUM_ITER, rng)
    combined = np.vstack([base, new])

    # Report the quality of the combined design
    n_total = len(combined)
    print(f"Combined: {n_total} samples")
    print(f"\tStrata filled at n={n_total}: {strata_filled(combined)}")
    new_min = min(cdist(new, base).min(), pdist(new).min())
    print(f"\tMin distance, base to base:\t{pdist(base).min():.4f}")
    print(f"\tMin distance, new to all:\t{new_min:.4f}")
    print(f"\tCentered discrepancy:\t\t{qmc.discrepancy(combined):.3e}")

    # Base rows are written from the loaded values so they stay unchanged
    samples = np.vstack([base_phys, qmc.scale(new, lows, highs)])

    # Check if output directory exists / create it, and never overwrite
    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / FILE_NAME
    if out_path.exists():
        raise FileExistsError(f"{out_path} already exists")

    # Build header
    header_lines = [
        "Augmented Latin Hypercube Sampling Parameter Sets",
        f"Number of Samples: {n_total}",
        f"Base File: {BASE_FILE.name} (rows 0-{n - 1}, unchanged)",
        f"New Samples: {NUM_NEW} (rows {n}-{n_total - 1})",
        f"Seed: {SEED}",
        f"Swap Iterations: {NUM_ITER}",
        "Columns =" + " ".join(names),
        "Bounds =" + " ".join([f"{p}[{lo},{hi}]" for (p, lo, hi) in PARAMS]),
        " ".join(names),
    ]
    header = "\n".join(header_lines)
    # Save as whitespace delimited text
    np.savetxt(
        out_path,
        samples,
        fmt="%.17g",
        delimiter=" ",
        header=header,
        comments="# ",
    )
    print(f"Wrote {n_total} samples to: {out_path}")


if __name__ == "__main__":
    main()
