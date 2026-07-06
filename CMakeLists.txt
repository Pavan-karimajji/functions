cmake_minimum_required(VERSION 3.22)
project(adas-functions VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)

if(NOT DEFINED TARGET_TYPE)
    set(TARGET_TYPE sil CACHE STRING "Build target: sil, autosar")
endif()

# Compile-time function selection (plan.md item 2). Empty by default — functions
# graduate onto this list once their real port skeleton lands (Step 4 for aeb).
# Override for testing: cmake --preset sil-release -DENABLED_FUNCTIONS=aeb
if(NOT DEFINED ENABLED_FUNCTIONS)
    set(ENABLED_FUNCTIONS "" CACHE STRING "Semicolon-separated list of enabled functions, e.g. \"aeb;acc\"")
endif()

find_package(AdasInterfaces REQUIRED)

add_subdirectory(src/component)

if(TARGET_TYPE STREQUAL "sil")
    add_subdirectory(src/platform/sil)
elseif(TARGET_TYPE STREQUAL "autosar")
    add_subdirectory(src/platform/autosar)
elseif(TARGET_TYPE STREQUAL "standalone")
    add_subdirectory(src/platform/standalone)
endif()

if(BUILD_TESTING)
    enable_testing()
    add_subdirectory(tests)
endif()
