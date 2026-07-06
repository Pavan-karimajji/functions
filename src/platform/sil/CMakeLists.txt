add_library(functions_sil SHARED
    functions_interface_c.cpp
    param_loader.cpp
)
target_compile_definitions(functions_sil PRIVATE
    FUNCTIONS_SIL_EXPORTS
    # Placeholder read-only demo in fnInit() (plan.md item 2 will do real
    # wiring once a function needs specific fields) — baked in at build time
    # since SIL is a dev/desktop-only artifact, never shipped to production
    # targets, so a build-tree absolute path is fine here.
    ADAS_EGO_PARAMS_PATH="${CMAKE_CURRENT_SOURCE_DIR}/../../../../../config/ego_params.yaml"
)
target_include_directories(functions_sil PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(functions_sil PRIVATE functions_common)
if("aeb" IN_LIST ENABLED_FUNCTIONS)
    target_link_libraries(functions_sil PRIVATE fn_aeb)
endif()
