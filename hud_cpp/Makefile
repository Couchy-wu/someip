# AR-HUD 23 服务 C++ 客户端（vsomeip + 自研大端编解码 "sp" 层）构建
# 依赖：COVESA vsomeip 3.4.x（含 vsomeip3 库与头文件）、g++ (C++14)
# 用法：make            # 生成 hud_client
#       make clean

CXX      ?= g++
CXXFLAGS ?= -std=c++14 -O2 -Wall -Wextra
INCLUDES  = -I/usr/local/include
LIBS      = -L/usr/local/lib -lvsomeip3

all: hud_client

hud_client: hud_client.cpp hud_data_types.cpp hud_data_types.hpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) hud_client.cpp hud_data_types.cpp $(LIBS) -o hud_client

test: hud_client
	./hud_client

clean:
	rm -f hud_client

.PHONY: all test clean
