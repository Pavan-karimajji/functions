find_package(yaml-cpp REQUIRED)

add_library(functions_common STATIC
    framework/function_runner.cpp
)
target_include_directories(functions_common PUBLIC
    ${CMAKE_SOURCE_DIR}/src   # so "component/common/framework/x.hpp" resolves from anywhere
    ${CMAKE_SOURCE_DIR}/include
)
target_link_libraries(functions_common PUBLIC
    AdasInterfaces::AdasInterfaces
    yaml-cpp::yaml-cpp   # transitively needed by function_params.hpp, even though
                          # functions_common's own .cpp files don't call into it directly —
                          # consumers (fn_aeb, functions_tests) get it for free via PUBLIC
)
