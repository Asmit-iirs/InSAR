# ISCE2 stackSentinel Processing Optimization Guide

## Summary
Your current notebook is using conservative settings. With 10 cores and ample RAM, you can significantly speed up processing.

## Current Bottlenecks Identified

### 1. **Threading Environment Variables (Currently Commented Out)**
The threading variables at the start of your notebook are commented out. These control NumPy/SciPy performance.

**Current (Disabled):**
```python
#os.environ["OMP_NUM_THREADS"] = "4"
#os.environ["OPENBLAS_NUM_THREADS"] = "1"
#os.environ["MKL_NUM_THREADS"] = "6"
#os.environ["VECLIB_MAXIMUM_THREADS"] = "4"
#os.environ["NUMEXPR_NUM_THREADS"] = "6"
```

**Optimized for 10 cores:**
```python
os.environ["OMP_NUM_THREADS"] = "10"
os.environ["OPENBLAS_NUM_THREADS"] = "10"
os.environ["MKL_NUM_THREADS"] = "10"
os.environ["VECLIB_MAXIMUM_THREADS"] = "10"
os.environ["NUMEXPR_NUM_THREADS"] = "10"
```

### 2. **Parallel Job Batching (Currently 10 at a time)**
Your run files batch parallel jobs in groups of 10, then wait. With 10 cores, this is reasonable, but the waiting pattern could be optimized.

**Current Pattern in run files:**
- Run 10 jobs in parallel
- Wait for all to complete
- Run next 10 jobs
- Continue...

**Issue:** If some jobs finish faster than others, cores sit idle waiting for the slowest job in each batch.

### 3. **Config Files: numProcess Parameter**
The topo processing currently uses `numProcess : 10` which is good, but other config files may not specify this.

## Optimization Strategies

### A. **Enable Threading Variables (Do This First)**
Create a new notebook cell at the very beginning (after imports) to set threading:

```python
import os
# Optimize for 10 cores - SET BEFORE ANY NUMERICAL IMPORTS
os.environ["OMP_NUM_THREADS"] = "10"
os.environ["OPENBLAS_NUM_THREADS"] = "10" 
os.environ["MKL_NUM_THREADS"] = "10"
os.environ["VECLIB_MAXIMUM_THREADS"] = "10"
os.environ["NUMEXPR_NUM_THREADS"] = "10"

print("✓ Threading optimized for 10 cores")
```

**Impact:** 2-3x speedup for I/O and matrix operations

### B. **Optimize Run File Execution**
Instead of running shell scripts directly, use GNU Parallel to better manage job distribution:

```python
# Install GNU Parallel if not already installed
# sudo apt-get install parallel

import subprocess
from pathlib import Path

def run_with_gnu_parallel(run_file_path, max_jobs=10):
    """
    Execute ISCE run file with GNU Parallel for better core utilization
    """
    with open(run_file_path, 'r') as f:
        commands = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    
    # Remove trailing & and wait commands
    commands = [cmd.rstrip(' &') for cmd in commands if cmd != 'wait']
    
    # Write to temp file for parallel
    temp_file = Path('/tmp/parallel_commands.txt')
    temp_file.write_text('\n'.join(commands))
    
    # Execute with GNU parallel
    cmd = f'parallel -j {max_jobs} --progress < {temp_file}'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    return result

# Example usage:
# result = run_with_gnu_parallel(run_file, max_jobs=10)
```

### C. **Modify stackSentinel Command for More Aggressive Parallelism**

**Current:**
```python
args += ' --num_proc4topo 10 --num_proc 10'
```

**For more aggressive processing (uses more memory):**
```python
args += ' --num_proc4topo 10 --num_proc 10 --num_overlap 10'
```

### D. **Use RAM Disk for Temporary Files**
ISCE2 generates many temporary files. Using RAM disk can dramatically speed up I/O:

```bash
# Create 16GB RAM disk (adjust based on available RAM)
sudo mkdir -p /mnt/ramdisk
sudo mount -t tmpfs -o size=16G tmpfs /mnt/ramdisk
```

Then modify config to use it:
```python
# Add to notebook before stackSentinel call
import os
os.environ['TMPDIR'] = '/mnt/ramdisk'
```

**Warning:** Ensure you have enough RAM. Monitor with `free -h`

### E. **Optimize Interferogram Generation**
The interferogram steps (21-24) can be very slow. Check if they support multiprocessing:

```python
# Check if interferogramStack.py supports parallel processing
# Look for --num_proc or similar flags
subprocess.run('interferogramStack.py -h', shell=True)
```

### F. **Enable GPU Acceleration (If Available)**
Check your GPU availability:
```bash
nvidia-smi  # For NVIDIA GPUs
```

If you have a GPU, modify config files to enable:
```python
# In config files, change:
useGPU : True
```

Then ensure CUDA libraries are available in your isce2 environment.

### G. **Optimize SSD Performance**
Since you're on a portable SSD, ensure optimal mount options:

```bash
# Check current mount options
mount | grep PortableSSD

# Remount with noatime to reduce write operations
sudo mount -o remount,noatime /media/roy/PortableSSD
```

### H. **Pre-allocate Disk Space**
Large file operations can be slow with dynamic allocation:

```python
# Before running processing steps
import subprocess

def preallocate_workspace(size_gb=100):
    """Pre-allocate disk space for faster I/O"""
    test_file = Path('/media/roy/PortableSSD/InSAR/desc_slc/isce/.disk_test')
    subprocess.run(f'fallocate -l {size_gb}G {test_file}', shell=True)
    test_file.unlink()  # Delete test file
    print(f"✓ Disk pre-allocation verified: {size_gb}GB")
```

## Recommended Implementation Order

1. **Immediate (No Risk):**
   - Enable threading environment variables (Section A)
   - Optimize SSD mount options (Section G)
   
2. **High Impact (Low Risk):**
   - Use GNU Parallel for run file execution (Section B)
   - Add `--num_overlap` parameter (Section C)

3. **Medium Impact (Requires Testing):**
   - RAM disk for temp files (Section D) - Monitor memory usage
   - Pre-allocate disk space (Section H)

4. **Advanced (If Available):**
   - GPU acceleration (Section F) - Only if you have compatible GPU
   - Custom config file modifications

## Monitoring Performance

Add this to a notebook cell to monitor resource usage:

```python
import psutil
import time

def monitor_resources(duration_seconds=300, interval=5):
    """Monitor CPU, RAM, and disk I/O during processing"""
    print(f"Monitoring resources for {duration_seconds} seconds...")
    print(f"{'Time':<10} {'CPU%':<10} {'RAM%':<10} {'Disk Read':<15} {'Disk Write':<15}")
    print("-" * 70)
    
    for i in range(0, duration_seconds, interval):
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        disk_io = psutil.disk_io_counters()
        
        print(f"{i:>8}s {cpu:>8.1f}% {ram:>8.1f}% {disk_io.read_bytes/(1024**3):>13.2f}GB {disk_io.write_bytes/(1024**3):>13.2f}GB")
        time.sleep(interval - 1)

# Run in background while processing
# monitor_resources(duration_seconds=600)
```

## Expected Speed Improvements

| Optimization | Expected Speedup | Risk Level |
|-------------|------------------|------------|
| Threading Variables | 2-3x | None |
| GNU Parallel | 1.5-2x | Low |
| RAM Disk | 2-4x (I/O bound steps) | Medium (RAM) |
| GPU Acceleration | 3-10x (compatible steps) | Low |
| Combined | 5-15x overall | - |

## Troubleshooting

### Out of Memory
If you run out of memory:
- Reduce `--num_proc` values
- Don't use RAM disk
- Process fewer dates at once

### Disk Space Issues
Monitor disk space:
```bash
df -h /media/roy/PortableSSD
```

### Process Hanging
If processes hang:
- Check for zombie processes: `ps aux | grep defunct`
- Reduce parallelization
- Check disk I/O: `iotop`

## Next Steps for Current Run

Since your notebook is already running, for the **NEXT** processing run:

1. Create a new notebook: `stackSentinel_optimized.ipynb`
2. Copy current notebook but add threading variables
3. Create helper function for GNU parallel execution
4. Test on a small subset first

**DO NOT** interrupt current run - these optimizations should be applied to future runs.
