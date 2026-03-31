cmake_minimum_required(VERSION 3.22)
project(adas-functions VERSION 0.1.0 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(AdasInterfaces REQUIRED)

add_library(adas_functions
    src/aeb/AEBController.cpp
    # src/acc/ACCController.cpp
    # src/lka/LKAController.cpp
    # src/lca/LCAController.cpp
    # src/tja/TJACoordinator.cpp
)
target_include_directories(adas_functions PUBLIC src/ include/)
target_link_libraries(adas_functions PUBLIC AdasInterfaces::AdasInterfaces)

if(TARGET_TYPE STREQUAL "sil")
    # add_subdirectory(adapters/ros2)
elseif(TARGET_TYPE STREQUAL "autosar")
    # add_subdirectory(adapters/autosar)
endif()

if(BUILD_TESTING)
    # add_subdirectory(tests/unit)
endif()
