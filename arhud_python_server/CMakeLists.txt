# AR-HUD SOME/IP 服务端库 —— CMake 构建（Windows / Linux 通用）
# Windows：用标准 vsomeip fork（justinlhudson/vsomeip）编译 libarhud_server.dll
# Linux  ：用 SP 分支库编译 libarhud_server.so（默认），或标准 vsomeip 编译 _std
cmake_minimum_required(VERSION 3.16)
project(arhud_server CXX)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

option(BUILD_SP "使用 SP 分支协议栈（仅 Linux）" OFF)

# 数据层源码（平台无关）
set(DATA_SRC src/arhud_pcap.cpp src/arhud_types.cpp)

if(WIN32)
    if(BUILD_SP)
        # Windows + SP 分支 DLL（libsomeip.dll 等，接口与 Linux 版一致）
        find_package(ZLIB REQUIRED)
        add_library(arhud_server SHARED src/arhud_server_sp.cpp ${DATA_SRC})
        target_include_directories(arhud_server PRIVATE src src/include ${ZLIB_INCLUDE_DIRS})
        target_link_directories(arhud_server PRIVATE ${SP_LIBS_DIR})
        target_link_libraries(arhud_server PRIVATE
            someip someip-cfg someip-sd someip-e2e ZLIB::ZLIB)
        set_target_properties(arhud_server PROPERTIES OUTPUT_NAME arhud_server)
    else()
        # Windows：标准 vsomeip fork
        find_package(vsomeip3 CONFIG REQUIRED)
        find_package(ZLIB REQUIRED)
        add_library(arhud_server SHARED src/arhud_server.cpp ${DATA_SRC})
        target_include_directories(arhud_server PRIVATE src src/include ${ZLIB_INCLUDE_DIRS})
        target_link_libraries(arhud_server PRIVATE vsomeip3::vsomeip3 ZLIB::ZLIB)
        set_target_properties(arhud_server PROPERTIES OUTPUT_NAME arhud_server)
    endif()
else()
    if(BUILD_SP)
        # Linux + SP 分支库
        find_package(ZLIB REQUIRED)
        set(SP_LIBS_DIR ${SP_LIBS_DIR})
        add_library(arhud_server SHARED src/arhud_server_sp.cpp ${DATA_SRC})
        target_include_directories(arhud_server PRIVATE src src/include)
        target_link_libraries(arhud_server PRIVATE
            ${SP_LIBS_DIR}/libsomeip.so ${SP_LIBS_DIR}/libsomeip-cfg.so
            ${SP_LIBS_DIR}/libsomeip-sd.so ${SP_LIBS_DIR}/libsomeip-e2e.so ZLIB::ZLIB)
        target_link_directories(arhud_server PRIVATE ${SP_LIBS_DIR})
    else()
        # Linux + 标准 vsomeip
        find_package(vsomeip3 CONFIG REQUIRED)
        find_package(ZLIB REQUIRED)
        add_library(arhud_server SHARED src/arhud_server.cpp ${DATA_SRC})
        target_include_directories(arhud_server PRIVATE src src/include)
        target_link_libraries(arhud_server PRIVATE vsomeip3::vsomeip3 ZLIB::ZLIB)
        set_target_properties(arhud_server PROPERTIES OUTPUT_NAME arhud_server_std)
    endif()
endif()

install(TARGETS arhud_server LIBRARY DESTINATION lib RUNTIME DESTINATION bin)
