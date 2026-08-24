# AR-HUD SOME/IP 服务端库
# 默认用 SP 分支库（与板端示例 C++ 服务端同一协议栈）；SP_LIBS 指向 SP 库目录
#   make libarhud_server.so         # SP 版（默认，链接 libsomeip.so）
#   make libarhud_server_std.so     # 标准 vsomeip 3.4.10 版（备用）
# 架构：aarch64 用 ../to_longjie_demo_20250625/libs/lib_bst_t517
#       x86_64 用 ../to_longjie_demo_20250625/libs/lib_x86（-DARCH=x86_64）
CXX      ?= g++
CXXFLAGS ?= -std=c++14 -O2 -Wall -fPIC -I. -I/usr/local/include
ARCH     ?= aarch64

ifeq ($(ARCH),x86_64)
SP_LIBS  ?= ../to_longjie_demo_20250625/libs/lib_x86
else
SP_LIBS  ?= ../to_longjie_demo_20250625/libs/lib_bst_t517
endif

# SP 版：链接 SP 分支库（libsomeip.so 等）
SP_OBJS = arhud_server_sp.o arhud_pcap.o arhud_types.o
SP_LIBS_LINK = -L$(SP_LIBS) -lsomeip -lsomeip-cfg -lsomeip-sd -lsomeip-e2e \
               -lboost_system -lboost_thread -lboost_log -lboost_filesystem -lboost_program_options -lz

libarhud_server.so: $(SP_OBJS)
	$(CXX) $(CXXFLAGS) -shared -o $@ $(SP_OBJS) $(SP_LIBS_LINK) -Wl,-rpath,$(SP_LIBS)

# 标准版：链接标准 vsomeip 3.4.10
STD_OBJS = arhud_server.o arhud_pcap.o arhud_types.o
libarhud_server_std.so: $(STD_OBJS)
	$(CXX) $(CXXFLAGS) -shared -o $@ $(STD_OBJS) -L/usr/local/lib -lvsomeip3 -lz

%.o: %.cpp arhud_server.h arhud_pcap.h arhud_types.h
	$(CXX) $(CXXFLAGS) -c $< -o $@

arhud_server_sp.o: arhud_server_sp.cpp include/vsomeip/someip_com.h
	$(CXX) $(CXXFLAGS) -Iinclude -c $< -o $@

all: libarhud_server.so

clean:
	rm -f *.o libarhud_server.so libarhud_server_std.so

.PHONY: all clean
