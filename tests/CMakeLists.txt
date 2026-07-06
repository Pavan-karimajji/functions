cmake_minimum_required(VERSION 3.22)

# Try to find GTest in system or package manager first
find_package(GTest QUIET)

if(NOT GTest_FOUND)
    message(STATUS "GTest not found locally. Fetching GoogleTest from GitHub...")
    include(FetchContent)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
    )
    # Prevent overriding the compiler/linker settings on Windows
    set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
    FetchContent_MakeAvailable(googletest)
endif()

set(FUNCTIONS_TEST_SOURCES
    unit/common/framework/test_ports.cpp
    unit/common/framework/test_function_params.cpp
    unit/common/framework/test_function_runner.cpp
)

# Test sources/links follow the same ENABLED_FUNCTIONS gating as production
# code — otherwise a BCT-01-style override that disables aeb would break the
# test build instead of just excluding fn_aeb's tests.
if("aeb" IN_LIST ENABLED_FUNCTIONS)
    list(APPEND FUNCTIONS_TEST_SOURCES unit/aeb/test_aeb_function.cpp)
endif()

add_executable(functions_tests ${FUNCTIONS_TEST_SOURCES})

target_link_libraries(functions_tests PRIVATE
    functions_common
    GTest::gtest_main
)

if("aeb" IN_LIST ENABLED_FUNCTIONS)
    target_link_libraries(functions_tests PRIVATE fn_aeb)
endif()

include(GoogleTest)
gtest_discover_tests(functions_tests)
