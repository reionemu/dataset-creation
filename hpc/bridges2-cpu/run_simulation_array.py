# -----------------------------------------------------------------------------
# Run Reionization Simulations Using Latin Hypercube Sampling
# Robert Pearce
# -----------------------------------------------------------------------------

import os
import subprocess as sp
import sys
from pathlib import Path

import numpy as np

# Repository root (this file is hpc/bridges2-cpu/run_simulation_array.py)
REPO_ROOT = Path(__file__).resolve().parents[2]

# Path to simulation executable
EXEC = Path.home() / "software/ksz_2lpt/ksz_2lpt.x"
# Input table ksz_2lpt opens by bare name, so it runs from the executable's folder
TRANSFER_FILE = EXEC.parent / "planck_2018_transfer_z000.dat"
# Output root on Ocean project storage (~/ocean links there), not the home quota
RAW_ROOT = Path.home() / "ocean/raw"

# Campaign folders in this repository, holding params_<campaign>.txt
CAMPAIGNS_DIR = REPO_ROOT / "campaigns"


def main() -> int:
    # Campaign to run (set with sbatch --export=ALL,CAMPAIGN=<name>)
    campaign = os.environ["CAMPAIGN"]
    param_file = CAMPAIGNS_DIR / campaign / f"params_{campaign}.txt"
    # Require the Ocean output root, so output never lands in the home quota
    if not RAW_ROOT.is_dir():
        raise FileNotFoundError(f"{RAW_ROOT} not found")
    # Each campaign writes to sims_<campaign>/ under it
    out = RAW_ROOT / f"sims_{campaign}"
    # A missing table would be created empty by ksz_2lpt and fail every run
    if not TRANSFER_FILE.is_file() or TRANSFER_FILE.stat().st_size == 0:
        raise FileNotFoundError(f"{TRANSFER_FILE} missing or empty")

    # Get array job id (--array=0-999)
    task_id = int(os.environ["SLURM_ARRAY_TASK_ID"])
    # Offset added to the task id, so each array of up to 1000 tasks can run a
    # later block of rows (set with sbatch --export=ALL,ROW_OFFSET=<n>)
    row_offset = int(os.environ["ROW_OFFSET"])
    sim_id = row_offset + task_id

    # Load the samples
    samples = np.loadtxt(param_file, comments="#")
    if sim_id >= len(samples):
        raise IndexError(f"Row {sim_id} not in {param_file} ({len(samples)} rows)")
    # Load the row
    row = samples[sim_id]

    # Create the output directory (and the campaign root if needed)
    outdir = out / f"sim{sim_id}"
    outdir.mkdir(parents=True, exist_ok=True)

    # Output status
    print(
        f"Running {campaign} simulation: {sim_id} (task {task_id}, offset {row_offset})"
    )

    # Build the command ksz_2lpt expects: dir_out zmean_zre alpha_zre kb_zre b0_zre
    out_prefix = str(outdir) + "/"
    args = [str(EXEC), out_prefix] + [str(v) for v in row]
    rc = sp.run(args, cwd=EXEC.parent).returncode

    # Output status
    print(f"Simulation {sim_id} completed. Return code: {rc}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
