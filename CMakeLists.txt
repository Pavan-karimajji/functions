cmake_minimum_required(VERSION 3.22)
project(adas-functions VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)

if(NOT DEFINED TARGET_TYPE)
    set(TARGET_TYPE sil CACHE STRING "Build target: sil, autosar")
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
    # add_subdirectory(tests/unit)
endif()
