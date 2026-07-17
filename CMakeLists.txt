cmake_minimum_required(VERSION 3.22)
project(adas-df VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)

if(NOT DEFINED TARGET_TYPE)
    set(TARGET_TYPE sil CACHE STRING "Build target: sil, autosar")
endif()

# Compile-time function selection (plan.md item 2). Functions graduate onto
# this list once their real port skeleton lands (aeb since Step 4).
# Override for testing: cmake --preset sil-vs2026 -DENABLED_FUNCTIONS="aeb;acc"
if(NOT DEFINED ENABLED_FUNCTIONS)
    set(ENABLED_FUNCTIONS "aeb" CACHE STRING "Semicolon-separated list of enabled functions, e.g. \"aeb;acc\"")
endif()

# Which projects/<name> calibration folder this build is associated with.
# Set by build.bat's third argument (build.bat <part> <platform> <project>);
# override manually with -DADAS_PROJECT=<name>.
if(NOT DEFINED ADAS_PROJECT)
    set(ADAS_PROJECT base CACHE STRING "Which projects/<name> calibration folder to build against, e.g. base, proj_alpha")
endif()

# Compile-time bound on how many GenObjects any function's exec() processes
# per cycle - mirrors the reference codebase's EM_N_OBJECTS pattern (a single
# shared fixed-array budget, not one macro per array type), just driven by a
# CMake cache variable instead of an ARXML-generated header. Single global
# value for now, not per-project (see src/component/common/framework/object_limits.hpp).
# Override for testing: cmake --preset sil-vs2026 -DADAS_MAX_GEN_OBJECTS=200
if(NOT DEFINED ADAS_MAX_GEN_OBJECTS)
    set(ADAS_MAX_GEN_OBJECTS 50 CACHE STRING "Maximum number of GenObjects processed per exec() cycle")
endif()

find_package(AdasInterfaces REQUIRED)

add_subdirectory(src/component)

if(TARGET_TYPE STREQUAL "sil")
    add_subdirectory(src/platform/df_sil)
elseif(TARGET_TYPE STREQUAL "autosar")
    add_subdirectory(src/platform/autosar)
elseif(TARGET_TYPE STREQUAL "standalone")
    add_subdirectory(src/platform/standalone)
endif()

if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(tests)
endif()
