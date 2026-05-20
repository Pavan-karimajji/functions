add_library(adas_functions
    aeb/AEBController.cpp
)
target_include_directories(adas_functions PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/include
)
target_link_libraries(adas_functions PUBLIC AdasInterfaces::AdasInterfaces)
