add_library(fn_aeb STATIC
    aeb_scaffold.cpp   # placeholder — Step 4 adds aeb_ports.hpp/aeb_function.{hpp,cpp} here
)
target_include_directories(fn_aeb PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(fn_aeb PUBLIC functions_common)
