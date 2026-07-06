add_library(functions_common STATIC
    framework_scaffold.cpp   # placeholder — Step 3 adds ports.hpp/i_function.hpp/FunctionRunner.cpp/ParamLoader.cpp here
)
target_include_directories(functions_common PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/include
)
target_link_libraries(functions_common PUBLIC AdasInterfaces::AdasInterfaces)
