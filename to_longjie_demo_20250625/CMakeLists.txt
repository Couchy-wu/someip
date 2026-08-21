#set(CMAKE_C_COMPILER    gcc)
#set(CMAKE_CXX_COMPILER  g++)

project (demo)

cmake_minimum_required(VERSION 3.10)

# 读取文件内容到变量
set(PREFIX_PAHT "/home/lipeng/lipeng/git/BYDOS/BYDOS/SOMEIP/to_longjie_demo_20250625/")
#file(STRINGS "${PREFIX_PAHT}someip/CMakeLists.txt" FILE_CONTENTS)


#set(FILE_CONTENTS "lib_bst_t517")

# 设置要查找的字符串
set(SEARCH_STRING_ARM "lib_arm")
set(SEARCH_STRING_BST_T517 "lib_bst_t517")
set(SEARCH_STRING_TDA4 "lib_tda4")

# 使用正则表达式查找字符串
string(REGEX MATCH "${SEARCH_STRING_ARM}" STRING_MATCHED_ARM "${FILE_CONTENTS}")
string(REGEX MATCH "${SEARCH_STRING_BST_T517}" STRING_MATCHED_BST_T517 "${FILE_CONTENTS}")
string(REGEX MATCH "${SEARCH_STRING_TDA4}" STRING_MATCHED_TDA4 "${FILE_CONTENTS}")

# 判断是否找到匹配的字符串
if(STRING_MATCHED_ARM)
  set(CMAKE_C_COMPILER /home/lipeng/linux/tools/arm/gcc-arm-9.2-2019.12-x86_64-arm-none-linux-gnueabihf/bin/arm-none-linux-gnueabihf-gcc)
  set(CMAKE_CXX_COMPILER /home/lipeng/linux/tools/arm/gcc-arm-9.2-2019.12-x86_64-arm-none-linux-gnueabihf/bin/arm-none-linux-gnueabihf-g++)
  set(SP_LIB_TYPES "${PREFIX_PAHT}libs/lib_arm/*.so")
elseif(STRING_MATCHED_BST_T517)
  set(CMAKE_C_COMPILER    /home/lipeng/linux/tools/bst_t517/gcc-linaro-7.4.1-2019.02-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-gcc)
  set(CMAKE_CXX_COMPILER  /home/lipeng/linux/tools/bst_t517/gcc-linaro-7.4.1-2019.02-x86_64_aarch64-linux-gnu/bin/aarch64-linux-gnu-g++)
  set(SP_LIB_TYPES "${PREFIX_PAHT}libs/lib_bst_t517/*.so")
  set(PCAP_LIB "${PREFIX_PAHT}libpcap_aarch64.a")
elseif(STRING_MATCHED_TDA4)
  set(CMAKE_C_COMPILER    /home/lipeng/linux/tools/tda4/gcc-arm-9.2-2019.12-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-gcc)
  set(CMAKE_CXX_COMPILER  /home/lipeng/linux/tools/tda4/gcc-arm-9.2-2019.12-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-g++)
  set(SP_LIB_TYPES "${PREFIX_PAHT}libs/lib_tda4/*.so")
else()
  set(CMAKE_C_COMPILER    gcc)
  set(CMAKE_CXX_COMPILER  g++)
  set(SP_LIB_TYPES "${PREFIX_PAHT}libs/lib_x86/*.so")
  set(PCAP_LIB "${PREFIX_PAHT}libpcap_x86.a")
endif()

file(GLOB_RECURSE SOMEIP_LIB_FILES ${SP_LIB_TYPES} )


###################################################################################################
# Set a default build type if none was specified
set(default_build_type "Debug")
if(NOT CMAKE_BUILD_TYPE)
  message(STATUS "Setting build type to '${default_build_type}' as none was specified.")
  set(CMAKE_BUILD_TYPE "${default_build_type}" CACHE STRING "Choose the type of build." FORCE)
  # Set the possible values of build type for cmake-gui
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "MinSizeRel" "RelWithDebInfo")
endif()

set(CMAKE_CXX_FLAGS "-std=c++11 -O0 -g3 -fPIC")
SET(CMAKE_BUILD_TYPE "Debug")

################################################################################
# Directories
################################################################################

add_executable(hud_huifang_client ${PROJECT_SOURCE_DIR}/hud_huifang_client.cpp ${PROJECT_SOURCE_DIR}/CppCommon.cpp ${PROJECT_SOURCE_DIR}/ArHudSomeipDataConversion.cpp)
add_executable(hud_pcap_huifang_server ${PROJECT_SOURCE_DIR}/hud_pcap_huifang_server.cpp)


################################################################################
#  Dependencies
################################################################################
set(SOMEIP_COM_INCLUDE_DIR ${PREFIX_PAHT}include)
include_directories(${SOMEIP_COM_INCLUDE_DIR})

target_link_libraries(hud_huifang_client  -lstdc++ ${SOMEIP_LIB_FILES} -lpthread -lm -lc)
target_link_libraries(hud_pcap_huifang_server  -lstdc++ ${SOMEIP_LIB_FILES} -lpthread -lm -lc ${PCAP_LIB})

file(COPY ./out.pcap  DESTINATION ./)
file(COPY config/someip_arhud01.json  DESTINATION ./)
file(COPY config/someip_arhud01_pcap_server.json  DESTINATION ./)


message(STATUS "---------------------build OK!\r\n")
