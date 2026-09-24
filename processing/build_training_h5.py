# -----------------------------------------------------------------------------
# Script to condense simulation output into single HDF5 file with training
# dataset for reionemu.
#
# Robert Pearce
# -----------------------------------------------------------------------------

from pathlib import Path

from reionemu.simio import (
    BuildXYConfig,
    ClConfig,
    CondenseConfig,
    add_cl_to_condensed_h5,
    build_and_write_training,
    condense_sim_root,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Campaign to process
CAMPAIGN = "v7"
# Local data root
DATA_ROOT = REPO_ROOT / "data"
# Raw simulation output and condensed HDF5 for this campaign
RAW_SIM_ROOT = DATA_ROOT / "raw" / f"sims_{CAMPAIGN}"
CONDENSED_H5 = DATA_ROOT / "processed" / f"condensed_{CAMPAIGN}.h5"


def _progress_print(step: str):
    """
    Return a progress_callback that prints step name and percentage.
    """

    def callback(completed: int, total: int):
        pct = 100.0 * completed / total if total else 0
        print(f"\r{step} {completed}/{total} ({pct:.1f}%)", end="", flush=True)

    return callback


def main():
    raw_sim_root = RAW_SIM_ROOT
    condensed_h5 = CONDENSED_H5
    if not raw_sim_root.is_dir():
        raise FileNotFoundError(f"{raw_sim_root} not found")
    # Never overwrite an existing condensed file
    if condensed_h5.exists():
        raise FileExistsError(f"{condensed_h5} already exists")
    condensed_h5.parent.mkdir(parents=True, exist_ok=True)

    print("Condensing Raw Simulation Outputs")
    stats = condense_sim_root(
        sim_root=raw_sim_root,
        out_path=condensed_h5,
        config=CondenseConfig(overwrite=True, require_obs_and_pk=True),
        progress_callback=_progress_print("Condensing"),
    )
    print()
    print(f"\tWritten: {stats.written}, Skipped: {stats.skipped_total}")

    print("Computing C_ell / D_ell and Writing into /cl")
    n_updated = add_cl_to_condensed_h5(
        condensed_h5,
        config=ClConfig(nbins=5, ell_cut=1000.0, overwrite=True, sims_group="sims"),
        progress_callback=_progress_print("CL computation"),
    )
    print()
    print(f"\tUpdated: {n_updated} sims")

    print("Building and Writing Training Data")
    n_train = build_and_write_training(
        condensed_h5,
        config=BuildXYConfig(
            sims_group="sims",
            params_group="params",
            cl_group="cl",
            param_names=("zmean_zre", "alpha_zre", "kb_zre", "b0_zre"),
            y_source="dl_ksz",
            y_transform="ln",
            eps=1e-30,
        ),
    )
    print(f"\tTraining Samples: {n_train}")

    print("Finished building condensed dataset with /cl and /training")
    print(f"Output: {condensed_h5}")


if __name__ == "__main__":
    main()
