find_package(yaml-cpp REQUIRED)

add_library(df_common STATIC
    framework/df_runner.cpp
)
target_include_directories(df_common PUBLIC
    # PROJECT_SOURCE_DIR (df's own project(), not CMAKE_SOURCE_DIR - plan.md
    # item 13) resolves to modules/df whether df is the top-level build or
    # add_subdirectory()'d into the superproject aggregator, where
    # CMAKE_SOURCE_DIR would instead point at the aggregate's own root.
    ${PROJECT_SOURCE_DIR}/src
    ${PROJECT_SOURCE_DIR}/include
)
target_link_libraries(df_common PUBLIC
    AdasInterfaces::AdasInterfaces
    yaml-cpp::yaml-cpp   # transitively needed by df_params.hpp, even though
                          # df_common's own .cpp files don't call into it directly —
                          # consumers (fn_aeb, df_tests) get it for free via PUBLIC
)
target_compile_definitions(df_common PUBLIC
    ADAS_MAX_GEN_OBJECTS=${ADAS_MAX_GEN_OBJECTS}   # object_limits.hpp's #ifndef guard
                                                     # picks this up; PUBLIC so every
                                                     # consumer (fn_aeb, df_tests) sees
                                                     # the same value the root CMakeLists.txt
                                                     # cache variable was built with
)
