find_package(AdasSharedConfig REQUIRED)

add_library(df_sil SHARED
    df_interface_c.cpp
    param_loader.cpp
)
target_compile_definitions(df_sil PRIVATE
    DF_SIL_EXPORTS
    ADAS_EGO_PARAMS_PATH="${adas-shared-config_PACKAGE_FOLDER_RELEASE}/projects/${ADAS_PROJECT}/vehicle/ego_params.yaml"
)
target_include_directories(df_sil PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(df_sil PRIVATE df_common)
if("aeb" IN_LIST ENABLED_FUNCTIONS)
    target_link_libraries(df_sil PRIVATE fn_aeb)
endif()
