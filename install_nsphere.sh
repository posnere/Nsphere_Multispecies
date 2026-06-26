#!/bin/bash
#
# install_nsphere.sh - Attempt to install C library dependencies for NSphere
#
# Supports: Debian/Ubuntu (apt), Fedora (dnf), Arch (pacman), macOS (brew)
#           and provides guidance for Windows (MSYS2 CLANG64).
#

echo "--- NSphere C Library Dependency Installer ---"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- OS Detection ---
OS_NAME=$(uname -s)
echo "Detected OS: $OS_NAME"

INSTALL_CMD=""
UPDATE_CMD=""
GSL_PKG=""
FFTW_PKG=""
OMP_PKG="" # OpenMP runtime package (may vary)
PKG_MANAGER=""
PYTHON_PKG=""
PIP_PKG=""
VENV_PKG=""
MAKE_PKG=""
CLANG_PKG=""
# Potentially add variables for build-essential/base-devel groups later

if [ "$OS_NAME" == "Linux" ]; then
    if command_exists apt-get; then
        PKG_MANAGER="apt"
        UPDATE_CMD="sudo apt update"
        # Core Tools
        PYTHON_PKG="python3"
        PIP_PKG="python3-pip"
        VENV_PKG="python3-venv"
        MAKE_PKG="make"
        CLANG_PKG="clang"
        # C Libs
        GSL_PKG="libgsl-dev"
        FFTW_PKG="libfftw3-dev"
        OMP_PKG="libomp-dev"
        # Combine all packages
        PKG_LIST="$PYTHON_PKG $PIP_PKG $VENV_PKG $MAKE_PKG $CLANG_PKG $GSL_PKG $FFTW_PKG $OMP_PKG"
        INSTALL_CMD="sudo $PKG_MANAGER install -y $PKG_LIST"
    elif command_exists dnf; then
        PKG_MANAGER="dnf"
        UPDATE_CMD="sudo dnf check-update" # Use check-update instead of update for non-interactive
        # Core Tools
        PYTHON_PKG="python3"
        PIP_PKG="python3-pip"
        # VENV_PKG="python3-venv" # REMOVE THIS LINE (or comment out)
        MAKE_PKG="make"
        CLANG_PKG="clang"
        # C Libs
        GSL_PKG="gsl-devel"
        FFTW_PKG="fftw-devel"
        OMP_PKG="libomp-devel"
        # Combine all packages (removed VENV_PKG)
        PKG_LIST="$PYTHON_PKG $PIP_PKG $MAKE_PKG $CLANG_PKG $GSL_PKG $FFTW_PKG $OMP_PKG"
        INSTALL_CMD="sudo $PKG_MANAGER install -y $PKG_LIST"
        # Optional: Could suggest groupinstall "Development Tools" which covers make/gcc
    elif command_exists pacman; then
        PKG_MANAGER="pacman"
        UPDATE_CMD="sudo pacman -Syu --noconfirm"
        # Core Tools (python-venv included with python)
        PYTHON_PKG="python"
        PIP_PKG="python-pip"
        # venv module is included in python package
        MAKE_PKG="make"
        CLANG_PKG="clang"
        # C Libs
        GSL_PKG="gsl"
        FFTW_PKG="fftw"
        OMP_PKG="openmp"
        # Combine all packages
        PKG_LIST="$PYTHON_PKG $PIP_PKG $MAKE_PKG $CLANG_PKG $GSL_PKG $FFTW_PKG $OMP_PKG"
        INSTALL_CMD="sudo $PKG_MANAGER -S --noconfirm --needed $PKG_LIST"
        # Optional: Could suggest installing 'base-devel' group which covers make/gcc
    else
        echo "ERROR: Unsupported Linux distribution (apt, dnf, or pacman not found)." >&2
        exit 1
    fi

elif [ "$OS_NAME" == "Darwin" ]; then # macOS
    if ! command_exists brew; then
        echo "ERROR: Homebrew not found. Please install Homebrew first: https://brew.sh/" >&2
        exit 1
    fi
    PKG_MANAGER="brew"

    # --- Homebrew Installations First ---
    UPDATE_CMD="brew update"
    PYTHON_PKG="python" # Installs python3
    GSL_PKG="gsl"
    FFTW_PKG="fftw"
    OMP_PKG="libomp" # OpenMP runtime for macOS
    # Make/Clang come from Command Line Tools, not installed via brew here
    PKG_LIST="$PYTHON_PKG $GSL_PKG $FFTW_PKG $OMP_PKG"
    INSTALL_CMD="brew install $PKG_LIST"

    echo "Attempting to update Homebrew..."
    eval "$UPDATE_CMD"
    if [ $? -ne 0 ]; then
        echo "WARNING: Failed to update Homebrew package list. Continuing installation attempt..." >&2
    fi

    echo "Attempting to install required Homebrew packages ($PKG_LIST)..."
    eval "$INSTALL_CMD"
    if [ $? -ne 0 ]; then
        echo "ERROR: Failed to install one or more required Homebrew packages." >&2
        echo "Please review the output above and install the packages manually." >&2
        # Decide whether to exit or continue to xcode check. Continuing for now.
    else
         echo "Homebrew packages ($PKG_LIST) installed successfully."
    fi

    # --- Check/Install Command Line Tools Last ---
    echo "---------------------------------------------------------------------"
    echo "Checking for Command Line Tools (make, clang)..."
    if ! command_exists make || ! command_exists clang; then
        echo "WARNING: Core build tools (make, clang) appear missing."
        echo "These are typically installed via Apple's Command Line Tools package."
        echo ""
        echo "The script needs to run 'xcode-select --install' to initiate this."
        echo "**IMPORTANT:** This command will likely open a separate window or"
        echo "dialog box on your Mac. You MUST follow the instructions in that"
        echo "window (e.g., accept license, click 'Install') for the process"
        echo "to complete successfully. This script cannot wait for that process."
        echo "The 'make all' command later will FAIL if these tools are not installed."
        echo "---------------------------------------------------------------------"
        read -p "Press Enter to run 'xcode-select --install' now..."

        # Run the command, suppressing exit on non-zero (e.g., if already installed)
        xcode-select --install || true

        echo "Command Line Tools installation initiated. Please monitor your screen"
        echo "for any dialog boxes and complete the installation steps there."
        echo "**Crucial:** Ensure this finishes successfully before running 'make all'."
        echo "---------------------------------------------------------------------"
    else
        echo "Command Line Tools found."
    fi
    # --- End Command Line Tools Check ---

    # Skip the generic INSTALL_CMD execution for macOS as brew was run directly
    # and xcode-select handles make/clang
    INSTALL_CMD="" # Clear install command to prevent execution later

elif [[ "$OS_NAME" == CYGWIN* || "$OS_NAME" == MINGW* || "$OS_NAME" == MSYS* || "$OS_NAME" == CLANG* ]]; then
    # Report OS detection details for debugging
    echo "Detected Windows-like environment: OS_NAME=$OS_NAME, MSYSTEM=$MSYSTEM"
    
    # Try to detect CLANG64 environment within MSYS2
    if [[ "$MSYSTEM" == "CLANG64" || "$MSYSTEM" == *"CLANG"* || "$OS_NAME" == *"CLANG"* ]]; then
        # Log the detected environment
        echo "Confirmed CLANG-based environment (MSYSTEM=$MSYSTEM)"
         PKG_MANAGER="pacman"
         UPDATE_CMD="pacman -Syuu --noconfirm" # May need user interaction despite --noconfirm
         # Core Tools
         PYTHON_PKG="mingw-w64-clang-x86_64-python"
         PIP_PKG="mingw-w64-clang-x86_64-python-pip"
         # venv module is included with python package
         MAKE_PKG="mingw-w64-clang-x86_64-make"
         CLANG_PKG="mingw-w64-clang-x86_64-clang"
         # C Libs
         GSL_PKG="mingw-w64-clang-x86_64-gsl"
         FFTW_PKG="mingw-w64-clang-x86_64-fftw"
         # OpenMP is included with the compiler
         OMP_PKG="mingw-w64-clang-x86_64-openmp"
         
         # Python scientific packages for NSphere
         MATPLOTLIB_PKG="mingw-w64-clang-x86_64-python-matplotlib"
         SCIPY_PKG="mingw-w64-clang-x86_64-python-scipy"
         JUPYTERLAB_PKG="mingw-w64-clang-x86_64-python-jupyterlab"
         PSUTIL_PKG="mingw-w64-clang-x86_64-python-psutil"
         
         # Combine all packages
         PKG_LIST="$PYTHON_PKG $PIP_PKG $MAKE_PKG $CLANG_PKG $OMP_PKG $GSL_PKG $FFTW_PKG"
         PY_SCI_PKG_LIST="$MATPLOTLIB_PKG $SCIPY_PKG $JUPYTERLAB_PKG $PSUTIL_PKG"
         INSTALL_CMD="pacman -S --noconfirm --needed $PKG_LIST $PY_SCI_PKG_LIST"
         
         echo "Detected MSYS2 CLANG64 environment."

        # Provide a plain 'make' alias so docs work unchanged
        /usr/bin/install -Dm755 /clang64/bin/make.exe /clang64/bin/make.exe 2>/dev/null || true
    else
         echo "ERROR: This script requires the MSYS2 CLANG64 environment on Windows." >&2
         echo "Current environment: MSYSTEM=$MSYSTEM, OS_NAME=$OS_NAME" >&2
         echo "Please launch the 'CLANG64' shell from your MSYS2 installation." >&2
         echo "See: https://www.msys2.org/" >&2
         echo "If you believe this is an error and you are already in CLANG64, you can edit" >&2
         echo "the install_nsphere.sh script to bypass this check." >&2
         exit 1
    fi

else
    echo "ERROR: Unsupported operating system '$OS_NAME'." >&2
    echo "Please install GSL (dev), FFTW3 (dev), and ensure OpenMP support manually." >&2
    exit 1
fi

echo "Using package manager: $PKG_MANAGER"

# --- Run Update and Install ---
echo "Attempting to update package list..."
eval "$UPDATE_CMD"
if [ $? -ne 0 ]; then
    echo "WARNING: Failed to update package list. Continuing installation attempt..." >&2
fi

echo "Attempting to install required system packages (Python, Build Tools, C Libs)..."
eval "$INSTALL_CMD"
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install one or more required system dependencies." >&2
    echo "Please review the output above and install the packages manually." >&2
    echo "Required: Python 3 (including venv module), pip, Make, Clang, GSL (dev), FFTW3 (dev), OpenMP runtime (usually from compiler)" >&2
    # Consider adding specific package list $PKG_LIST if helpful here
    exit 1
fi

echo "--- System dependency installation attempt finished. ---"
echo "Please check for any errors above."
echo "You can now proceed to compile the code with 'make all'."

exit 0