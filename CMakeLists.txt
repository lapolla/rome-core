cmake_minimum_required(VERSION 3.20)
project(ROME_Core VERSION 1.0.0)

# 1. Compilation Settings
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

# 2. Options and Flags
if(MSVC)
    add_compile_options(/W4 /WX /EHsc /permissive- /Zc:preprocessor)
else()
    add_compile_options(-Wall -Wextra -Werror)
endif()

# 3. Dependencies
# Assume CommonLibSSE-NG and nlohmann_json are available in include paths
# or provided via find_package in a full SKSE environment.
# find_package(CommonLibSSE-NG REQUIRED)
# find_package(nlohmann_json REQUIRED)

# 4. Target Definition
add_library(${PROJECT_NAME} SHARED
    src/CommandDispatcher.cpp
    src/CommandHooks.cpp
    src/JsonProcessor.cpp
)

target_include_directories(${PROJECT_NAME} PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Link dependencies (Placeholder)
# target_link_libraries(${PROJECT_NAME} PRIVATE CommonLibSSE-NG::CommonLibSSE-NG nlohmann_json::nlohmann_json)

# 5. Post-Build
# Copy to SKSE Plugins directory (Placeholder)
# add_custom_command(TARGET ${PROJECT_NAME} POST_BUILD
#     COMMAND ${CMAKE_COMMAND} -E copy_if_different
#     $<TARGET_FILE:${PROJECT_NAME}>
#     "${SKSE_PLUGINS_PATH}/${PROJECT_NAME}.dll"
# )

message(STATUS "ROME Core configured for build.")
