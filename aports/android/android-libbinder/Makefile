CXX        := g++
CXXFLAGS   := -std=c++14 -Wall -g -I../include -I/usr/include/android -I./
LIBS       :=

SOURCES	:= ${wildcard *.cpp}
OBJECTS	:= $(SOURCES:%.cpp=%.o)

all: libbinder.so

%.o: %.cpp
	@echo CC $<
	@$(CXX) -c -o $@ $< $(CXXFLAGS)

libbinder.so: $(OBJECTS)
	@echo LD $@
	@$(CXX) -o $@ $^ $(CXXFLAGS) $(LIBS) $(LDFLAGS)

.PHONY: clean

clean:
	-rm -fv *.o libbinder.so
