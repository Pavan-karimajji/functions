add_library(functions_sil SHARED
    functions_interface_c.cpp
    param_loader.cpp
)
target_compile_definitions(functions_sil PRIVATE FUNCTIONS_SIL_EXPORTS)
target_include_directories(functions_sil PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(functions_sil PRIVATE functions_common)
if("aeb" IN_LIST ENABLED_FUNCTIONS)
    target_link_libraries(functions_sil PRIVATE fn_aeb)
endif()
