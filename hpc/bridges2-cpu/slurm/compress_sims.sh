#!/bin/bash
#SBATCH -J compress_sims
#SBATCH -p RM-shared
#SBATCH -t 04:00:00
#SBATCH -N 1
#SBATCH --ntasks-per-node=2
#SBATCH -o slurm-%x-%j.out
#SBATCH -e slurm-%x-%j.err
#SBATCH -A ast180004p
#SBATCH --mail-type END,FAIL
#SBATCH --mail-user robertbdpearce@gmail.com

# Compress a campaign's simulation folders into one .tar.gz next to it, with a
# .sha256 file for checking the copy after transfer.
#
# Usage, from hpc/bridges2-cpu:
#   sbatch slurm/compress_sims.sh <sims dir> [first last]
#
#   sbatch slurm/compress_sims.sh ~/ocean/raw/sims_v7
#       -> ~/ocean/raw/sims_v7.tar.gz               (every sim* folder)
#   sbatch slurm/compress_sims.sh ~/ocean/raw/sims_v7 1000 1999
#       -> ~/ocean/raw/sims_v7_1000-1999.tar.gz     (sim1000 to sim1999)
#
# Paths inside the archive start with the folder name (sims_v7/sim1000/...), so
# extracting it recreates sims_v7/. The sim files are uncompressed float64
# grids; gzip -1 brings them to about 75% of their size.

set -euo pipefail

if [[ $# -ne 1 && $# -ne 3 ]]; then
    echo "Usage: sbatch slurm/compress_sims.sh <sims dir> [first last]" >&2
    exit 2
fi

SIMS_DIR=$(realpath "$1")
PARENT=$(dirname "$SIMS_DIR")
NAME=$(basename "$SIMS_DIR")

# Folders to archive: a numbered range, or every sim* folder
members=()
if [[ $# -eq 3 ]]; then
    FIRST=$2
    LAST=$3
    ARCHIVE="$PARENT/${NAME}_${FIRST}-${LAST}.tar.gz"
    for i in $(seq "$FIRST" "$LAST"); do
        members+=("$NAME/sim$i")
    done
else
    ARCHIVE="$PARENT/$NAME.tar.gz"
    for d in "$SIMS_DIR"/sim*/; do
        [[ -d "$d" ]] && members+=("$NAME/$(basename "$d")")
    done
fi

echo "Source:  $SIMS_DIR"
echo "Archive: $ARCHIVE"
echo "Sims:    ${#members[@]}"

if [[ ${#members[@]} -eq 0 ]]; then
    echo "No sim folders found" >&2
    exit 1
fi
if [[ -e "$ARCHIVE" ]]; then
    echo "$ARCHIVE already exists" >&2
    exit 1
fi

# Every sim must be present and complete, so the archive never silently omits one
missing=0
for m in "${members[@]}"; do
    for f in obs_grids.hdf5 pk_arrays.hdf5; do
        if [[ ! -s "$PARENT/$m/$f" ]]; then
            echo "Missing or empty: $PARENT/$m/$f" >&2
            missing=$((missing + 1))
        fi
    done
done
if [[ $missing -ne 0 ]]; then
    echo "$missing file(s) missing; nothing archived" >&2
    exit 1
fi

# Write to a temporary name and rename only once the archive is complete
echo "Compressing ($(date))"
tar -C "$PARENT" -cf - "${members[@]}" | gzip -1 > "$ARCHIVE.part"
mv "$ARCHIVE.part" "$ARCHIVE"
echo "Finished ($(date))"

# Check the archive reads back and holds two files per sim
n_files=$(tar -tzf "$ARCHIVE" | grep -c '\.hdf5$')
if [[ $n_files -ne $((2 * ${#members[@]})) ]]; then
    echo "Archive holds $n_files .hdf5 files, expected $((2 * ${#members[@]}))" >&2
    exit 1
fi

# Checksum for verifying the transfer: shasum -a 256 -c <file>.sha256
(cd "$PARENT" && sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256")

du -sh "$ARCHIVE"
echo "Checked: $n_files .hdf5 files. Checksum in $ARCHIVE.sha256"
