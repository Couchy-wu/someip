# AR-HUD SOME/IP 服务端库 —— 编译 libarhud_server.so
# 依赖：vsomeip 3.4.10（libvsomeip3.so）+ zlib
# 用法：make          # 生成 libarhud_server.so
#       make clean
CXX      ?= g++
CXXFLAGS ?= -std=c++14 -O2 -Wall -fPIC -I/usr/local/include
LDFLAGS  ?= -shared -L/usr/local/lib -lvsomeip3 -lz

SRCS = arhud_server.cpp arhud_pcap.cpp arhud_types.cpp
OBJS = $(SRCS:.cpp=.o)
LIB  = libarhud_server.so

all: $(LIB)

$(LIB): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJS) $(LDFLAGS)

%.o: %.cpp arhud_server.h arhud_pcap.h arhud_types.h
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(LIB)

.PHONY: all clean
