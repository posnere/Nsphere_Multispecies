# Universal Dispatcher Makefile for NSphere
# Detects OS, sets platform variables, and invokes sub-makefile or runs commands directly.
# 'make <os>' only prints confirmation message.

# --- Stage 1: Parse MAKECMDGOALS to Identify OS and Actual Targets ---
OS_SPECIFIERS := linux macos windows
# Extract any OS specifiers from the command line goals
REQUESTED_OS_SPECIFIER := $(firstword $(filter $(OS_SPECIFIERS), $(MAKECMDGOALS)))
OS_GOAL_COUNT := $(words $(filter $(OS_SPECIFIERS), $(MAKECMDGOALS)))
# Extract the actual targets (goals that are not OS specifiers)
ACTUAL_REQUESTED_GOALS := $(filter-out $(OS_SPECIFIERS), $(MAKECMDGOALS))

# --- Determine Effective OS ---
# Error out if multiple OS overrides are specified.
# This check is skipped if 'detect-platform' is requested.
ifeq ($(filter detect-platform, $(ACTUAL_REQUESTED_GOALS)),)
	ifeq ($(shell test $(OS_GOAL_COUNT) -gt 1; echo $$?), 0)
		$(error Multiple OS targets specified: $(filter $(OS_SPECIFIERS), $(MAKECMDGOALS)). Please choose only one.)
	endif
endif

# Determine the OS name based on the requested specifier, if any.
FORCED_OS_NAME :=
ifeq ($(REQUESTED_OS_SPECIFIER),linux)
    FORCED_OS_NAME := Linux
else ifeq ($(REQUESTED_OS_SPECIFIER),macos)
    FORCED_OS_NAME := MacOS
else ifeq ($(REQUESTED_OS_SPECIFIER),windows)
    FORCED_OS_NAME := Windows
endif

# Perform OS detection if no override was specified.
OS := Unknown
ifeq ($(FORCED_OS_NAME),)
	UNAME_S := $(shell uname -s)
	ifeq ($(UNAME_S),Linux)
		OS := Linux
	else ifeq ($(UNAME_S),Darwin)
		OS := MacOS
	else ifneq (,$(findstring MINGW,$(UNAME_S)))
		OS := Windows
		DEFAULT_CLANG := 1
	else ifneq (,$(findstring CYGWIN,$(UNAME_S)))
		OS := Windows
		DEFAULT_CLANG := 1
	else ifneq (,$(findstring MSYS,$(UNAME_S)))
		OS := Windows
		DEFAULT_CLANG := 1
	else ifneq (,$(filter Windows%,$(OS))) # Check OS environment variable if available
		OS := Windows
		DEFAULT_CLANG := 0 # Assume MSVC if running in a Windows environment outside MSYS2/CLANG64
	else
		$(warning Unknown operating system detected. Assuming Linux...)
		OS := Linux
	endif
else
	OS := $(FORCED_OS_NAME)
endif

# Ensure DEFAULT_CLANG is set based on OS
ifeq ($(OS),Windows)
	DEFAULT_CLANG ?= 1
else
	DEFAULT_CLANG := 0
endif

# Use the OS override specified on the command line.
ifeq ($(FORCED_OS_NAME),)
	PLATFORM_INFO := $(OS)
else
	PLATFORM_INFO := $(OS) (Override)
endif

# Set default Windows compiler type based on forced OS, unless USE_CLANG is set.
ifeq ($(OS),Windows)
	USE_CLANG ?= $(DEFAULT_CLANG)
	ifeq ($(USE_CLANG),1)
		PLATFORM_INFO := $(PLATFORM_INFO) (CLANG64)
	else
		PLATFORM_INFO := $(PLATFORM_INFO) (MSVC)
	endif
endif

# --- Configure Platform-Specific Settings ---

# Configuration for platform-specific makefiles and variables
PLATFORM_MAKEFILE_LINUX := Makefile.Linux
PLATFORM_MAKEFILE_MACOS := Makefile.MacOS
PLATFORM_MAKEFILE_WINDOWS := Makefile.Windows

# Set platform-specific makefile path based on detected OS
ifeq ($(OS),Linux)
	PLATFORM_MAKEFILE := $(PLATFORM_MAKEFILE_LINUX)
	RM = rm -f
	CP = cp -f
endif
ifeq ($(OS),MacOS)
	PLATFORM_MAKEFILE := $(PLATFORM_MAKEFILE_MACOS)
	RM = rm -f
	CP = cp -f
endif
ifeq ($(OS),Windows)
	PLATFORM_MAKEFILE := $(PLATFORM_MAKEFILE_WINDOWS)
	# Set defaults based on CLANG vs MSVC selection (determined by USE_CLANG ?= $(DEFAULT_CLANG) earlier)
	ifeq ($(USE_CLANG),1)
		RM ?= rm -f
		CP ?= cp -f
	else
		RM ?= del /Q /F
		CP ?= copy
	endif
endif

# --- Clean Command Configuration ---
# For greater reliability, append "|| true" to clean commands to ignore non-zero exit codes.
# Avoids "Error 1" when files don't exist to be removed.
CLEAN_CMD_BASE := $(RM)
CLEAN_CMD = $(CLEAN_CMD_BASE) || true

# --- Build Rules ---
# ================================================================

# Export variables needed by sub-makefiles
export CC RM CP USE_CLANG DEBUG GSL_DIR FFTW_DIR QUAD_CACHE_BYTES

# --- Define Recipes for Explicitly Handled Targets ---

# Default target: Build using the platform-specific sub-makefile.
all:
	@echo "Building for $(PLATFORM_INFO)..."
ifeq ($(OS),Windows)
ifeq ($(USE_CLANG),1)
	@echo "Using CLANG64 build mode..."
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) all USE_CLANG=1 CC=clang
else
	@echo "Using MSVC build mode..."
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) all USE_MSVC=1
endif
else
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) all
endif

# Clean target: Use the platform-specific Makefile's clean target with explicit OS detection
clean:
	@echo "Cleaning up..."
ifeq ($(OS),Windows)
	@echo "Using Windows clean target..."
ifeq ($(USE_CLANG),1)
	@echo "CLANG64 clean mode..."
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) clean USE_CLANG=1
else
	@echo "MSVC clean mode..."
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) clean USE_MSVC=1
endif
else
	@echo "Using $(OS) clean target..."
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) clean
endif

# Debug target: Build with DEBUG=yes using the platform-specific sub-makefile.
debug:
	@echo "Building DEBUG mode for $(PLATFORM_INFO)..."
ifeq ($(OS),Windows)
ifeq ($(USE_CLANG),1)
	@echo "Using CLANG64 debug build mode..."
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) DEBUG=yes all USE_CLANG=1 CC=clang
else
	@echo "Using MSVC debug build mode..."
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) DEBUG=yes all USE_MSVC=1
endif
else
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) DEBUG=yes all
endif

# No-OpenMP target: Build without OpenMP using the platform-specific sub-makefile.
no-openmp:
	@echo "Building without OpenMP for $(PLATFORM_INFO)..."
ifeq ($(OS),Windows)
ifeq ($(USE_CLANG),1)
	@echo "Using CLANG64 no-openmp build mode..."
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) no-openmp USE_CLANG=1 CC=clang
else
	@echo "Using MSVC no-openmp build mode..."
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) no-openmp USE_MSVC=1
endif
else
	@$(MAKE) --no-print-directory -f $(PLATFORM_MAKEFILE) no-openmp
endif

# Print detected platform information
detect-platform:
	@echo "Detected Platform: $(PLATFORM_INFO)"
	@echo "Platform Makefile: $(PLATFORM_MAKEFILE)"
	@echo "RM Command: $(RM)"
	@echo "CP Command: $(CP)"
ifeq ($(OS),Windows)
	@echo "USE_CLANG: $(USE_CLANG)"
endif

# Help target: Show available make targets.
help:
	@echo "NSphere Makefile Help"
	@echo "===================="
	@echo ""
	@echo "Current platform: $(PLATFORM_INFO)"
	@echo ""
	@echo "Available targets:"
	@echo "  make             # Build everything with default settings"
	@echo "  make clean       # Clean up compiled files"
	@echo "  make debug       # Build with debug information"
	@echo "  make no-openmp   # Build without OpenMP support"
	@echo "  make help        # Show this help message"
	@echo ""
	@echo "Platform overrides:"
	@echo "  make linux ...   # Force Linux build mode"
	@echo "  make macos ...   # Force macOS build mode"
	@echo "  make windows ... # Force Windows build mode"
	@echo ""
	@echo "Platform detection:"
	@echo "  make detect-platform # Show detected platform information"
	@echo ""
	@echo "Build options for Windows:"
	@echo "  make USE_CLANG=1 ...    # Build with CLANG64 (default for MSYS2)"
	@echo "  make USE_CLANG=0 ...    # Build with MSVC (requires Visual Studio)"
	@echo "  make USE_MSVC=1 ...     # Build with MSVC (alternative syntax)"
	@echo ""
	@echo "Example: make DEBUG=yes        # Build with debug flags via $(PLATFORM_MAKEFILE)"
	@echo "Example: make windows USE_CLANG=0   # Force Windows MSVC mode"
	@echo ""

# --- Target Entry Point ---
# This is how we handle OS-specific phony targets like 'linux', 'macos', 'windows'.
# When such a target is specified, don't actually build that target,
# but remove it from the goals and build the actual targets requested.
.PHONY : $(OS_SPECIFIERS)
$(OS_SPECIFIERS):
	@# These targets just set FORCED_OS_NAME; they don't directly do anything.
	@echo "Using $(REQUESTED_OS_SPECIFIER) build mode..."

# Handle the case of no targets specified
EFFECTIVE_GOALS := $(ACTUAL_REQUESTED_GOALS)
ifeq ($(EFFECTIVE_GOALS),)
	EFFECTIVE_GOALS := all # Default to 'all' if no target is explicitly specified
endif

# Handle the platform-selection target and its dependencies
.PHONY : default_entry
default_entry: $(EFFECTIVE_GOALS)
	@# This target has no recipe; it just triggers dependencies.

# --- Phony Targets ---
# Declare targets defined in this file (and OS specifiers) as phony.
.PHONY: all clean debug help no-openmp detect-platform default_entry linux macos windows