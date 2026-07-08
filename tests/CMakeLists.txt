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

set(DF_TEST_SOURCES
    unit/common/framework/test_ports.cpp
    unit/common/framework/test_function_params.cpp
    unit/common/framework/test_function_runner.cpp
    unit/sil/test_param_loader.cpp   # ungated: ParamLoader doesn't depend on ENABLED_FUNCTIONS
)

# Test sources/links follow the same ENABLED_FUNCTIONS gating as production
# code — otherwise a BCT-01-style override that disables aeb would break the
# test build instead of just excluding fn_aeb's tests.
if("aeb" IN_LIST ENABLED_FUNCTIONS)
    list(APPEND DF_TEST_SOURCES
        unit/aeb/test_aeb_function.cpp
        unit/sil/test_interface_c_api.cpp
    )
endif()

add_executable(df_tests ${DF_TEST_SOURCES})

target_compile_definitions(df_tests PRIVATE
    ADAS_DF_TEST_FIXTURE_DIR="${CMAKE_CURRENT_SOURCE_DIR}/fixtures"
    ADAS_DF_PROJECTS_DIR="${CMAKE_CURRENT_SOURCE_DIR}/../projects"
)

target_link_libraries(df_tests PRIVATE
    df_common
    df_sil
    GTest::gtest_main
)

if("aeb" IN_LIST ENABLED_FUNCTIONS)
    target_link_libraries(df_tests PRIVATE fn_aeb)
endif()

# Windows only searches the exe's own directory (+ PATH) for DLLs at load
# time — implicit linking against df_sil's import lib resolves the
# symbols at compile time, but df_sil.dll itself still needs to be
# copied next to df_tests.exe or the process fails to start
# (STATUS_DLL_NOT_FOUND) before any test body ever runs.
add_custom_command(TARGET df_tests POST_BUILD
    COMMAND ${CMAKE_COMMAND} -E copy_if_different
        $<TARGET_FILE:df_sil>
        $<TARGET_FILE_DIR:df_tests>
)

include(GoogleTest)
gtest_discover_tests(df_tests)
