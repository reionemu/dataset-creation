#!/bin/bash
#SBATCH -J ksz_2lpt
#SBATCH -p RM
#SBATCH -t 00:15:00
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --array=0-999%16
#SBATCH -o slurm-%A_%a.out
#SBATCH -e slurm-%A_%a.err
#SBATCH -A ast180004p
#SBATCH --mail-type ALL
#SBATCH --mail-user robertbdpearce@gmail.com

set -euo pipefail

# Runs rows ROW_OFFSET + task id of campaigns/<CAMPAIGN>/params_<CAMPAIGN>.txt.
# Submit from hpc/bridges2-cpu:
#   sbatch --export=ALL,CAMPAIGN=v7,ROW_OFFSET=1000 slurm/run_sims_array.sh
: "${CAMPAIGN:?Set CAMPAIGN, e.g. sbatch --export=ALL,CAMPAIGN=v7,ROW_OFFSET=1000}"
: "${ROW_OFFSET:?Set ROW_OFFSET, e.g. sbatch --export=ALL,CAMPAIGN=v7,ROW_OFFSET=1000}"

# Intel
module unload intel
module load intel-icc
module load intel-mkl
which ifort

# Set environment variables
export KMP_LIBRARY=turnaround
export KMP_SCHEDULE=static
export KMP_STACKSIZE=256m
# Number of OpenMP threads (match with Slurm CPU request)
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK

echo "SLURM_ARRAY_JOB_ID=${SLURM_ARRAY_JOB_ID:-}"
echo "SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID:-}"
echo "SLURM_JOB_ID=${SLURM_JOB_ID:-}"
echo "CAMPAIGN=${CAMPAIGN}"
echo "ROW_OFFSET=${ROW_OFFSET}"
echo "Host=$(hostname)"
echo "PWD=$(pwd)"

# Define the simulation code directory
SIM_DIR="$HOME/software/ksz_2lpt/"
SCRIPT_DIR="$SLURM_SUBMIT_DIR"
MAMBA="$HOME/miniforge3/bin/mamba"

# Go to script directory for execution
echo "Changing directory to $SCRIPT_DIR for execution"
cd $SCRIPT_DIR

# Run Python inside the conda env
"$MAMBA" run -n simenv python "$SCRIPT_DIR/run_simulation_array.py"

