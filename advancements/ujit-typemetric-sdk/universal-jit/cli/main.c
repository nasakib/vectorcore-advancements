#include "ujit.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static void print_usage(const char *prog) {
    printf("Universal JIT Compiler (ujit) v%d.%d.%d\n",
           UJIT_VERSION_MAJOR, UJIT_VERSION_MINOR, UJIT_VERSION_PATCH);
    printf("Compiles algorithmic pseudocode directly to bare-metal native machine code.\n\n");
    printf("Usage:\n");
    printf("  %s run <file.pseudo> [func_name] [args...]\n", prog);
    printf("  %s dump <file.pseudo> [func_name]\n", prog);
    printf("  %s bench <file.pseudo> [func_name] [iterations] [args...]\n", prog);
    printf("  %s eval \"<code>\" [func_name] [args...]\n", prog);
    printf("  %s -h | --help\n", prog);
    printf("  %s -v | --version\n", prog);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        print_usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "-h") == 0 || strcmp(argv[1], "--help") == 0) {
        print_usage(argv[0]);
        return 0;
    }

    if (strcmp(argv[1], "-v") == 0 || strcmp(argv[1], "--version") == 0) {
        printf("ujit version %d.%d.%d (target: x86-64 native)\n",
               UJIT_VERSION_MAJOR, UJIT_VERSION_MINOR, UJIT_VERSION_PATCH);
        return 0;
    }

    ujit_ctx_t *ctx = ujit_create();
    if (!ctx) {
        fprintf(stderr, "Error: Failed to initialize Universal JIT context\n");
        return 1;
    }

    const char *cmd = argv[1];

    if (strcmp(cmd, "run") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Error: missing source file for 'run'\n");
            ujit_destroy(ctx);
            return 1;
        }
        const char *filepath = argv[2];
        ujit_status_t status = ujit_compile_file(ctx, filepath);
        if (status != UJIT_OK) {
            fprintf(stderr, "Compilation error: %d\n", status);
            ujit_destroy(ctx);
            return 1;
        }

        const char *fn_name = (argc >= 4) ? argv[3] : "main";
        int64_t args[8] = {0};
        size_t num_args = 0;
        for (int i = 4; i < argc && num_args < 8; i++) {
            args[num_args++] = atoll(argv[i]);
        }

        int64_t result = ujit_call(ctx, fn_name, args, num_args);
        printf("%lld\n", (long long)result);

    } else if (strcmp(cmd, "eval") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Error: missing code string for 'eval'\n");
            ujit_destroy(ctx);
            return 1;
        }
        const char *code = argv[2];
        ujit_status_t status = ujit_compile_string(ctx, code);
        if (status != UJIT_OK) {
            fprintf(stderr, "Compilation error: %d\n", status);
            ujit_destroy(ctx);
            return 1;
        }

        const char *fn_name = (argc >= 4) ? argv[3] : "main";
        int64_t args[8] = {0};
        size_t num_args = 0;
        for (int i = 4; i < argc && num_args < 8; i++) {
            args[num_args++] = atoll(argv[i]);
        }

        int64_t result = ujit_call(ctx, fn_name, args, num_args);
        printf("%lld\n", (long long)result);

    } else if (strcmp(cmd, "dump") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Error: missing source file for 'dump'\n");
            ujit_destroy(ctx);
            return 1;
        }
        const char *filepath = argv[2];
        ujit_status_t status = ujit_compile_file(ctx, filepath);
        if (status != UJIT_OK) {
            fprintf(stderr, "Compilation error: %d\n", status);
            ujit_destroy(ctx);
            return 1;
        }

        const char *fn_name = (argc >= 4) ? argv[3] : NULL;
        printf("=== Universal JIT Intermediate Representation ===\n");
        ujit_dump_ir(ctx, fn_name);
        printf("\n=== Universal JIT Native Machine Code ===\n");
        ujit_dump_bytes(ctx, fn_name);

    } else if (strcmp(cmd, "bench") == 0) {
        if (argc < 3) {
            fprintf(stderr, "Error: missing source file for 'bench'\n");
            ujit_destroy(ctx);
            return 1;
        }
        const char *filepath = argv[2];
        ujit_status_t status = ujit_compile_file(ctx, filepath);
        if (status != UJIT_OK) {
            fprintf(stderr, "Compilation error: %d\n", status);
            ujit_destroy(ctx);
            return 1;
        }

        const char *fn_name = (argc >= 4) ? argv[3] : "main";
        long long iterations = (argc >= 5) ? atoll(argv[4]) : 10000000LL;
        int64_t args[8] = {0};
        size_t num_args = 0;
        for (int i = 5; i < argc && num_args < 8; i++) {
            args[num_args++] = atoll(argv[i]);
        }

        void *fn_ptr = ujit_get_fn(ctx, fn_name);
        if (!fn_ptr) {
            fprintf(stderr, "Error: function '%s' not found\n", fn_name);
            ujit_destroy(ctx);
            return 1;
        }

        clock_t t0 = clock();
        int64_t sum = 0;
        for (long long i = 0; i < iterations; i++) {
            sum += ujit_call(ctx, fn_name, args, num_args);
        }
        clock_t t1 = clock();

        double elapsed_sec = (double)(t1 - t0) / CLOCKS_PER_SEC;
        double ns_per_call = (elapsed_sec / (double)iterations) * 1e9;
        printf("Benchmarked '%s': %lld iterations in %.3f sec (%.2f ns/call), result checksum: %lld\n",
               fn_name, iterations, elapsed_sec, ns_per_call, (long long)sum);

    } else {
        fprintf(stderr, "Unknown command '%s'. Run '%s --help' for usage.\n", cmd, argv[0]);
        ujit_destroy(ctx);
        return 1;
    }

    ujit_destroy(ctx);
    return 0;
}
