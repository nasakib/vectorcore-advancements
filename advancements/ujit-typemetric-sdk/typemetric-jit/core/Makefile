CC ?= cc
AR ?= ar
CFLAGS ?= -std=c99 -Wall -Wextra -Werror -pedantic -O3 -fPIC -Iinclude
LDFLAGS ?=

SRCS := src/metric_space.c src/gonzalez.c src/short_key.c src/trace_stitch.c \
        src/walsh_hadamard.c src/graph_laplacian.c src/chebyshev.c src/phase_fourier.c \
        src/harmonic.c
OBJS := $(SRCS:.c=.o)

LIB_STATIC := libtypemetric.a
LIB_SHARED := libtypemetric.so

.PHONY: all clean

all: $(LIB_STATIC) $(LIB_SHARED)

$(LIB_STATIC): $(OBJS)
	$(AR) rcs $@ $^

$(LIB_SHARED): $(OBJS)
	$(CC) -shared -o $@ $^ $(LDFLAGS) -lm

%.o: %.c include/typemetric/typemetric.h include/typemetric/spectral.h include/typemetric/harmonic.h
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(LIB_STATIC) $(LIB_SHARED)
