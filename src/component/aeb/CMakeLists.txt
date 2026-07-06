add_library(fn_aeb STATIC
    aeb_function.cpp
)
target_link_libraries(fn_aeb PUBLIC functions_common)
