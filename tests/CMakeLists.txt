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

add_executable(functions_tests
    unit/common/framework/test_ports.cpp
    unit/common/framework/test_function_params.cpp
    unit/common/framework/test_function_runner.cpp
)

target_link_libraries(functions_tests PRIVATE
    functions_common
    GTest::gtest_main
)

include(GoogleTest)
gtest_discover_tests(functions_tests)
