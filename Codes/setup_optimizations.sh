#!/bin/bash
# Quick setup script for ISCE2 speed optimizations
# Run with: bash setup_optimizations.sh

echo "=========================================="
echo "ISCE2 Processing Speed Optimization Setup"
echo "=========================================="
echo ""

# Check if running as root for system operations
if [ "$EUID" -ne 0 ]; then 
    echo "Note: Some operations may require sudo password"
fi

# 1. Check and install GNU Parallel
echo "1. Checking GNU Parallel..."
if command -v parallel &> /dev/null; then
    VERSION=$(parallel --version 2>&1 | head -n 1)
    echo "   ✓ GNU Parallel is installed: $VERSION"
else
    echo "   ✗ GNU Parallel not found"
    echo "   Installing GNU Parallel..."
    
    # Try apt-get first (Debian/Ubuntu)
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y parallel
    # Try yum (RedHat/CentOS)
    elif command -v yum &> /dev/null; then
        sudo yum install -y parallel
    # Try conda if available
    elif command -v conda &> /dev/null; then
        conda install -c conda-forge parallel -y
    else
        echo "   ⚠ Could not find package manager. Please install manually:"
        echo "      Ubuntu/Debian: sudo apt-get install parallel"
        echo "      RedHat/CentOS: sudo yum install parallel"
        echo "      Conda: conda install -c conda-forge parallel"
    fi
    
    # Verify installation
    if command -v parallel &> /dev/null; then
        echo "   ✓ GNU Parallel installed successfully!"
    else
        echo "   ✗ Failed to install GNU Parallel"
    fi
fi

echo ""

# 2. Optimize SSD mount
echo "2. Checking SSD mount options..."
MOUNT_POINT="/media/roy/PortableSSD"

if mount | grep "$MOUNT_POINT" > /dev/null; then
    MOUNT_INFO=$(mount | grep "$MOUNT_POINT")
    echo "   Current mount: $MOUNT_INFO"
    
    if echo "$MOUNT_INFO" | grep -q "noatime"; then
        echo "   ✓ SSD already optimized (noatime)"
    else
        echo "   ⚠ SSD not optimized"
        echo "   Optimizing SSD mount options..."
        sudo mount -o remount,noatime,nodiratime "$MOUNT_POINT"
        
        if [ $? -eq 0 ]; then
            echo "   ✓ SSD mount optimized!"
            echo "   Note: This will reset on reboot. Add to /etc/fstab for permanent."
        else
            echo "   ✗ Failed to optimize mount. Run manually:"
            echo "      sudo mount -o remount,noatime,nodiratime $MOUNT_POINT"
        fi
    fi
else
    echo "   ⚠ Mount point $MOUNT_POINT not found"
    echo "   Available mounts:"
    mount | grep "/media"
fi

echo ""

# 3. Check system resources
echo "3. System Resources:"
CORES=$(nproc)
TOTAL_RAM=$(free -h | awk '/^Mem:/ {print $2}')
AVAIL_RAM=$(free -h | awk '/^Mem:/ {print $7}')
DISK_SPACE=$(df -h "$MOUNT_POINT" 2>/dev/null | awk 'NR==2 {print $4}')

echo "   CPU Cores: $CORES"
echo "   Total RAM: $TOTAL_RAM"
echo "   Available RAM: $AVAIL_RAM"
if [ ! -z "$DISK_SPACE" ]; then
    echo "   Free Disk Space: $DISK_SPACE"
fi

echo ""

# 4. Check Python packages
echo "4. Checking Python environment..."
if command -v python &> /dev/null; then
    PYTHON_VER=$(python --version 2>&1)
    echo "   Python: $PYTHON_VER"
    
    # Check for psutil (needed for monitoring)
    if python -c "import psutil" 2>/dev/null; then
        echo "   ✓ psutil installed"
    else
        echo "   ⚠ psutil not installed (needed for resource monitoring)"
        echo "   Install with: pip install psutil"
    fi
else
    echo "   ⚠ Python not found in PATH"
fi

echo ""

# 5. Check ISCE2
echo "5. Checking ISCE2..."
if python -c "import isce" 2>/dev/null; then
    echo "   ✓ ISCE2 is installed"
    ISCE_PATH=$(python -c "import isce; print(isce.__path__[0])" 2>/dev/null)
    echo "   ISCE2 path: $ISCE_PATH"
else
    echo "   ⚠ ISCE2 not found"
    echo "   Make sure conda environment is activated:"
    echo "      conda activate isce2"
fi

echo ""

# 6. Test helper script
echo "6. Checking optimization helpers..."
HELPER_FILE="/media/roy/PortableSSD/InSAR/desc_slc/isce_speedup_helpers.py"
if [ -f "$HELPER_FILE" ]; then
    echo "   ✓ Helper script found: $HELPER_FILE"
    
    # Try to run diagnostics
    if python "$HELPER_FILE" 2>/dev/null; then
        echo "   ✓ Helper script works!"
    else
        echo "   ⚠ Helper script has issues. Install psutil:"
        echo "      pip install psutil"
    fi
else
    echo "   ✗ Helper script not found"
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Use the optimized notebook template:"
echo "   $MOUNT_POINT/InSAR/desc_slc/stackSentinel_OPTIMIZED_TEMPLATE.ipynb"
echo ""
echo "2. Or add threading setup to your existing notebook (FIRST cell):"
echo "   import os"
echo "   NUM_CORES = $CORES"
echo "   os.environ['OMP_NUM_THREADS'] = str(NUM_CORES)"
echo "   os.environ['OPENBLAS_NUM_THREADS'] = str(NUM_CORES)"
echo "   os.environ['MKL_NUM_THREADS'] = str(NUM_CORES)"
echo ""
echo "3. See QUICK_REFERENCE.md for usage examples"
echo ""
echo "Expected speedup: 3-5x faster! 🚀"
echo ""
