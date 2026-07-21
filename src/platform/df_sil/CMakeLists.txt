if(NOT TARGET AdasSharedConfig::AdasSharedConfig)
    find_package(AdasSharedConfig REQUIRED)
endif()

add_library(df_sil SHARED
    df_interface_c.cpp
    param_loader.cpp
)

# plan.md item 13 (docs/build_superbuild_aggregator_plan.md §3) - lets a
# consumer link "AdasDf::AdasDf" whether df is in-tree (this alias, via the
# superproject aggregator's add_subdirectory) or a real Conan package
# (find_package's own same-named imported target) - zero branching in any
# consumer's CMakeLists.txt either way.
add_library(AdasDf::AdasDf ALIAS df_sil)
target_compile_definitions(df_sil PRIVATE
    DF_SIL_EXPORTS
    ADAS_EGO_PARAMS_PATH="${adas-shared-config_PACKAGE_FOLDER_RELEASE}/projects/${ADAS_PROJECT}/vehicle/ego_params.yaml"
)
target_include_directories(df_sil PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(df_sil PRIVATE df_common)
if("aeb" IN_LIST ENABLED_FUNCTIONS)
    target_link_libraries(df_sil PRIVATE fn_aeb)
endif()

# Needed for a real `conan create` package (plan.md item 14) - the SIL DLL
# deliverable, same pattern as adas-interfaces' own install() (plan.md item 13).
install(TARGETS df_sil
    RUNTIME DESTINATION bin
    LIBRARY DESTINATION lib
    ARCHIVE DESTINATION lib
)
install(FILES df_interface_c.h DESTINATION include)
