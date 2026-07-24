# df_utils: header-only df-domain math shared across driving functions
# (docs/df_utils_plan.md, R-MATH-2). INTERFACE lib - no seed file needs its
# own translation unit yet (§10 "decide at Phase 0").
add_library(df_utils INTERFACE)

target_include_directories(df_utils INTERFACE
    ${PROJECT_SOURCE_DIR}/src
)

target_link_libraries(df_utils INTERFACE
    AdasMathlib::AdasMathlib
)
