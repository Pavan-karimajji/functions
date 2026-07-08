find_package(yaml-cpp REQUIRED)

add_library(df_common STATIC
    framework/function_runner.cpp
)
target_include_directories(df_common PUBLIC
    ${CMAKE_SOURCE_DIR}/src   # so "component/common/framework/x.hpp" resolves from anywhere
    ${CMAKE_SOURCE_DIR}/include
)
target_link_libraries(df_common PUBLIC
    AdasInterfaces::AdasInterfaces
    yaml-cpp::yaml-cpp   # transitively needed by function_params.hpp, even though
                          # df_common's own .cpp files don't call into it directly —
                          # consumers (fn_aeb, df_tests) get it for free via PUBLIC
)
