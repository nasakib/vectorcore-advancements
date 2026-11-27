CC ?= gcc
CFLAGS ?= -Wall -Wextra -O2 -Iinclude -fPIC
AR ?= ar

SRC = src/parser.c src/opt.c src/emitter_x86.c src/runtime.c
OBJS = $(SRC:.c=.o)

LIB_STATIC = lib/libujit.a
LIB_SHARED = lib/libujit.so
CLI_BIN = bin/ujit
TEST_BIN = bin/test_ujit
BENCH_BIN = bin/bench_ujit

.PHONY: all clean test bench dirs

all: dirs $(LIB_STATIC) $(LIB_SHARED) $(CLI_BIN) $(TEST_BIN) $(BENCH_BIN)

dirs:
	mkdir -p lib bin

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

$(LIB_STATIC): $(OBJS)
	$(AR) rcs $@ $^

$(LIB_SHARED): $(OBJS)
	$(CC) -shared -o $@ $^

LDFLAGS ?= -Llib -lujit -Wl,-rpath,'$$ORIGIN/../lib'

$(CLI_BIN): cli/main.c $(LIB_STATIC)
	$(CC) $(CFLAGS) $< $(LIB_STATIC) -o $@

$(TEST_BIN): tests/test_ujit.c $(LIB_STATIC) $(LIB_SHARED)
	$(CC) $(CFLAGS) $< $(LDFLAGS) -o $@

$(BENCH_BIN): bench/bench_ujit.c $(LIB_STATIC) $(LIB_SHARED)
	$(CC) $(CFLAGS) $< $(LDFLAGS) -o $@

test: $(TEST_BIN)
	LD_LIBRARY_PATH=lib:$$LD_LIBRARY_PATH ./$(TEST_BIN)

bench: $(BENCH_BIN)
	LD_LIBRARY_PATH=lib:$$LD_LIBRARY_PATH ./$(BENCH_BIN)

clean:
	rm -f src/*.o lib/* bin/*
