#!/usr/bin/env python3
"""
ISCE2 Processing Speed Optimization Helpers
===========================================

Helper functions to accelerate ISCE2 stackSentinel processing.
Use these in your notebooks for faster execution.

Author: Speed Optimization Guide
Date: 2025-11-10
"""

import os
import subprocess
import psutil
import time
from pathlib import Path
from typing import List, Dict, Optional
import multiprocessing as mp


def setup_threading_environment(num_cores: int = None):
    """
    Configure optimal threading environment variables for ISCE2.
    
    MUST BE CALLED BEFORE IMPORTING NUMPY/SCIPY/ISCE!
    
    Args:
        num_cores: Number of cores to use. If None, uses all available cores.
    
    Returns:
        dict: Environment variables that were set
    """
    if num_cores is None:
        num_cores = mp.cpu_count()
    
    env_vars = {
        "OMP_NUM_THREADS": str(num_cores),
        "OPENBLAS_NUM_THREADS": str(num_cores),
        "MKL_NUM_THREADS": str(num_cores),
        "VECLIB_MAXIMUM_THREADS": str(num_cores),
        "NUMEXPR_NUM_THREADS": str(num_cores),
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    print(f"✓ Threading environment optimized for {num_cores} cores")
    for key, value in env_vars.items():
        print(f"  {key} = {value}")
    
    return env_vars


def parse_run_file(run_file_path: Path) -> List[str]:
    """
    Parse ISCE2 run file and extract commands.
    
    Args:
        run_file_path: Path to run_XX_* file
    
    Returns:
        List of commands to execute
    """
    with open(run_file_path, 'r') as f:
        lines = f.readlines()
    
    commands = []
    for line in lines:
        line = line.strip()
        # Skip empty lines, comments, and wait commands
        if not line or line.startswith('#') or line == 'wait':
            continue
        # Remove trailing & for parallel execution
        if line.endswith('&'):
            line = line[:-1].strip()
        commands.append(line)
    
    return commands


def run_with_gnu_parallel(run_file_path: Path, 
                          max_jobs: int = 10, 
                          verbose: bool = True,
                          progress: bool = True) -> subprocess.CompletedProcess:
    """
    Execute ISCE2 run file using GNU Parallel for optimal core utilization.
    
    GNU Parallel is better than shell & because:
    - Jobs start immediately when cores are free (no waiting for batch)
    - Better load balancing
    - Progress monitoring
    
    Args:
        run_file_path: Path to run_XX_* file
        max_jobs: Maximum parallel jobs (default: 10)
        verbose: Print commands before execution
        progress: Show progress bar
    
    Returns:
        subprocess.CompletedProcess object
    """
    commands = parse_run_file(run_file_path)
    
    if verbose:
        print(f"Parsed {len(commands)} commands from {run_file_path.name}")
    
    # Create temporary command file
    temp_file = Path('/tmp/isce_parallel_commands.txt')
    temp_file.write_text('\n'.join(commands))
    
    # Build GNU parallel command
    parallel_cmd = f'parallel -j {max_jobs}'
    if progress:
        parallel_cmd += ' --progress'
    parallel_cmd += f' < {temp_file}'
    
    if verbose:
        print(f"Executing: {parallel_cmd}")
        print(f"Running {len(commands)} jobs on {max_jobs} cores...")
    
    # Execute
    start_time = time.time()
    result = subprocess.run(
        parallel_cmd,
        shell=True,
        capture_output=True,
        text=True
    )
    elapsed = time.time() - start_time
    
    if verbose:
        print(f"✓ Completed in {elapsed:.1f} seconds")
        if result.returncode != 0:
            print(f"⚠ Warning: Return code {result.returncode}")
            if result.stderr:
                print(f"STDERR: {result.stderr[:500]}")
    
    # Cleanup
    temp_file.unlink(missing_ok=True)
    
    return result


def run_step_optimized(step_number: int,
                       run_dir: Path,
                       max_jobs: int = 10,
                       use_parallel: bool = True) -> subprocess.CompletedProcess:
    """
    Run a specific ISCE2 processing step with optimization.
    
    Args:
        step_number: Step number (e.g., 7 for run_07_*)
        run_dir: Directory containing run files
        max_jobs: Maximum parallel jobs
        use_parallel: If True, use GNU parallel; otherwise use standard execution
    
    Returns:
        subprocess.CompletedProcess object
    """
    # Find run file
    pattern = f'run_{step_number:02d}*'
    run_files = list(run_dir.glob(pattern))
    
    if not run_files:
        raise FileNotFoundError(f"No run file found matching {pattern} in {run_dir}")
    
    run_file = run_files[0]
    print(f"{'='*60}")
    print(f"STEP {step_number}: {run_file.name}")
    print(f"{'='*60}")
    
    if use_parallel:
        # Check if GNU parallel is available
        check = subprocess.run('which parallel', shell=True, capture_output=True)
        if check.returncode == 0:
            result = run_with_gnu_parallel(run_file, max_jobs=max_jobs)
        else:
            print("⚠ GNU Parallel not found, falling back to standard execution")
            print("  Install with: sudo apt-get install parallel")
            result = subprocess.run(
                str(run_file), 
                shell=True, 
                capture_output=True, 
                text=True
            )
    else:
        result = subprocess.run(
            str(run_file), 
            shell=True, 
            capture_output=True, 
            text=True
        )
    
    # Print result
    if result.returncode == 0:
        print("✓ STEP FINISHED - SUCCESS!")
    else:
        print("✗ STEP FINISHED - FAILED!")
        print(f"Return code: {result.returncode}")
    
    return result


class ResourceMonitor:
    """Monitor system resources during processing."""
    
    def __init__(self):
        self.monitoring = False
        self.process = None
    
    def start(self, interval: int = 5, log_file: Optional[Path] = None):
        """Start monitoring in background."""
        self.monitoring = True
        self.log_file = log_file
        
        def monitor_loop():
            if self.log_file:
                f = open(self.log_file, 'w')
                f.write(f"{'Time':<10},{'CPU%':<10},{'RAM%':<10},{'Disk_Read_GB':<15},{'Disk_Write_GB':<15}\n")
            
            start_time = time.time()
            initial_disk = psutil.disk_io_counters()
            
            print(f"{'Time':<10} {'CPU%':<10} {'RAM%':<10} {'Disk Read':<15} {'Disk Write':<15}")
            print("-" * 70)
            
            while self.monitoring:
                elapsed = int(time.time() - start_time)
                cpu = psutil.cpu_percent(interval=1)
                ram = psutil.virtual_memory().percent
                disk_io = psutil.disk_io_counters()
                
                read_gb = (disk_io.read_bytes - initial_disk.read_bytes) / (1024**3)
                write_gb = (disk_io.write_bytes - initial_disk.write_bytes) / (1024**3)
                
                line = f"{elapsed:>8}s {cpu:>8.1f}% {ram:>8.1f}% {read_gb:>13.2f}GB {write_gb:>13.2f}GB"
                print(line)
                
                if self.log_file:
                    f.write(f"{elapsed},{cpu:.1f},{ram:.1f},{read_gb:.2f},{write_gb:.2f}\n")
                    f.flush()
                
                time.sleep(interval - 1)
            
            if self.log_file:
                f.close()
        
        import threading
        self.process = threading.Thread(target=monitor_loop, daemon=True)
        self.process.start()
        print("✓ Resource monitoring started")
    
    def stop(self):
        """Stop monitoring."""
        self.monitoring = False
        if self.process:
            self.process.join(timeout=2)
        print("✓ Resource monitoring stopped")


def check_gnu_parallel():
    """Check if GNU Parallel is installed and install if needed."""
    result = subprocess.run('which parallel', shell=True, capture_output=True)
    
    if result.returncode == 0:
        # Check version
        version_result = subprocess.run('parallel --version', shell=True, capture_output=True, text=True)
        print("✓ GNU Parallel is installed")
        print(version_result.stdout.split('\n')[0])
        return True
    else:
        print("✗ GNU Parallel is NOT installed")
        print("\nTo install:")
        print("  Ubuntu/Debian: sudo apt-get install parallel")
        print("  Conda: conda install -c conda-forge parallel")
        return False


def optimize_ssd_mount(mount_point: str = "/media/roy/PortableSSD"):
    """
    Check and suggest SSD optimization.
    
    Args:
        mount_point: Mount point to check
    """
    # Get current mount options
    result = subprocess.run(f'mount | grep {mount_point}', shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"✗ Mount point {mount_point} not found")
        return
    
    mount_info = result.stdout.strip()
    print(f"Current mount: {mount_info}")
    
    # Check for optimal options
    optimal_options = ['noatime', 'nodiratime']
    has_optimal = any(opt in mount_info for opt in optimal_options)
    
    if has_optimal:
        print("✓ SSD has optimal mount options")
    else:
        print("⚠ SSD mount could be optimized")
        print(f"\nTo optimize, run:")
        print(f"  sudo mount -o remount,noatime,nodiratime {mount_point}")
        print("\nThis reduces write operations and speeds up access.")


def estimate_processing_time(num_dates: int, 
                            num_interferograms: int,
                            cores: int = 10,
                            optimized: bool = False) -> Dict[str, float]:
    """
    Estimate total processing time.
    
    Rough estimates based on typical ISCE2 performance.
    
    Args:
        num_dates: Number of SLC dates
        num_interferograms: Number of interferograms to generate
        cores: Number of CPU cores
        optimized: Whether optimizations are applied
    
    Returns:
        Dictionary with time estimates in hours
    """
    # Base times (in minutes per date/ifg on single core)
    base_slc_time = 15  # minutes per SLC
    base_ifg_time = 10  # minutes per interferogram
    
    # Scaling factors
    parallel_efficiency = 0.8  # Not perfect scaling
    optimization_factor = 0.4 if optimized else 1.0
    
    # Calculate
    slc_time_hours = (num_dates * base_slc_time / (cores * parallel_efficiency) * optimization_factor) / 60
    ifg_time_hours = (num_interferograms * base_ifg_time / (cores * parallel_efficiency) * optimization_factor) / 60
    
    total_hours = slc_time_hours + ifg_time_hours
    
    return {
        'slc_stack_hours': slc_time_hours,
        'interferogram_hours': ifg_time_hours,
        'total_hours': total_hours,
        'total_days': total_hours / 24
    }


if __name__ == "__main__":
    """Run diagnostics when executed as script."""
    print("="*70)
    print("ISCE2 Speed Optimization Diagnostics")
    print("="*70)
    print()
    
    # Check cores
    cores = mp.cpu_count()
    print(f"✓ Available CPU cores: {cores}")
    
    # Check memory
    mem = psutil.virtual_memory()
    print(f"✓ Total RAM: {mem.total / (1024**3):.1f} GB")
    print(f"  Available RAM: {mem.available / (1024**3):.1f} GB ({100 - mem.percent:.1f}%)")
    
    # Check GNU Parallel
    print()
    check_gnu_parallel()
    
    # Check disk
    print()
    disk = psutil.disk_usage('/media/roy/PortableSSD')
    print(f"✓ Disk space:")
    print(f"  Total: {disk.total / (1024**3):.1f} GB")
    print(f"  Used: {disk.used / (1024**3):.1f} GB ({disk.percent:.1f}%)")
    print(f"  Free: {disk.free / (1024**3):.1f} GB")
    
    # Check SSD mount
    print()
    optimize_ssd_mount()
    
    print()
    print("="*70)
    print("To use these helpers in your notebook:")
    print("  from isce_speedup_helpers import *")
    print("  setup_threading_environment(10)")
    print("  result = run_step_optimized(7, run_dir, max_jobs=10)")
    print("="*70)
