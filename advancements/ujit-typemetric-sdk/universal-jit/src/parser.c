#include "internal.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

typedef enum {
    TOK_EOF = 0,
    TOK_IDENT,
    TOK_NUM,
    TOK_FN,
    TOK_LET,
    TOK_IF,
    TOK_ELSE,
    TOK_WHILE,
    TOK_FOR,
    TOK_IN,
    TOK_RETURN,
    TOK_LPAREN,
    TOK_RPAREN,
    TOK_LBRACE,
    TOK_RBRACE,
    TOK_COLON,
    TOK_ARROW,
    TOK_COMMA,
    TOK_ASSIGN,
    TOK_DOTDOT,
    TOK_PLUS,
    TOK_MINUS,
    TOK_STAR,
    TOK_SLASH,
    TOK_PERCENT,
    TOK_EQ,
    TOK_NE,
    TOK_LT,
    TOK_LE,
    TOK_GT,
    TOK_GE,
    TOK_AND,
    TOK_OR,
    TOK_CARET,
    TOK_AMP,
    TOK_PIPE,
} token_kind_t;

typedef struct {
    token_kind_t kind;
    char text[64];
    int64_t int_val;
} token_t;

typedef struct {
    const char *src;
    size_t pos;
    token_t cur;
} lexer_t;

static void next_token(lexer_t *lex);

static void lexer_init(lexer_t *lex, const char *src) {
    lex->src = src;
    lex->pos = 0;
    next_token(lex);
}

static void skip_whitespace_and_comments(lexer_t *lex) {
    while (lex->src[lex->pos] != '\0') {
        char c = lex->src[lex->pos];
        if (isspace(c)) {
            lex->pos++;
        } else if (c == '/' && lex->src[lex->pos + 1] == '/') {
            lex->pos += 2;
            while (lex->src[lex->pos] != '\0' && lex->src[lex->pos] != '\n') {
                lex->pos++;
            }
        } else if (c == '#' || (c == '-' && lex->src[lex->pos + 1] == '-')) {
            /* Support Python '#' and Lua '--' comments in pseudocode */
            lex->pos += (c == '#') ? 1 : 2;
            while (lex->src[lex->pos] != '\0' && lex->src[lex->pos] != '\n') {
                lex->pos++;
            }
        } else {
            break;
        }
    }
}

static void next_token(lexer_t *lex) {
    skip_whitespace_and_comments(lex);
    if (lex->src[lex->pos] == '\0') {
        lex->cur.kind = TOK_EOF;
        lex->cur.text[0] = '\0';
        return;
    }

    char c = lex->src[lex->pos];
    if (isdigit(c)) {
        size_t start = lex->pos;
        while (isdigit(lex->src[lex->pos])) {
            lex->pos++;
        }
        size_t len = lex->pos - start;
        if (len >= sizeof(lex->cur.text)) len = sizeof(lex->cur.text) - 1;
        strncpy(lex->cur.text, lex->src + start, len);
        lex->cur.text[len] = '\0';
        lex->cur.int_val = atoll(lex->cur.text);
        lex->cur.kind = TOK_NUM;
        return;
    }

    if (isalpha(c) || c == '_') {
        size_t start = lex->pos;
        while (isalnum(lex->src[lex->pos]) || lex->src[lex->pos] == '_') {
            lex->pos++;
        }
        size_t len = lex->pos - start;
        if (len >= sizeof(lex->cur.text)) len = sizeof(lex->cur.text) - 1;
        strncpy(lex->cur.text, lex->src + start, len);
        lex->cur.text[len] = '\0';

        if (strcmp(lex->cur.text, "fn") == 0 || strcmp(lex->cur.text, "function") == 0 || strcmp(lex->cur.text, "def") == 0) {
            lex->cur.kind = TOK_FN;
        } else if (strcmp(lex->cur.text, "let") == 0 || strcmp(lex->cur.text, "var") == 0) {
            lex->cur.kind = TOK_LET;
        } else if (strcmp(lex->cur.text, "if") == 0) {
            lex->cur.kind = TOK_IF;
        } else if (strcmp(lex->cur.text, "else") == 0) {
            lex->cur.kind = TOK_ELSE;
        } else if (strcmp(lex->cur.text, "while") == 0) {
            lex->cur.kind = TOK_WHILE;
        } else if (strcmp(lex->cur.text, "for") == 0) {
            lex->cur.kind = TOK_FOR;
        } else if (strcmp(lex->cur.text, "in") == 0) {
            lex->cur.kind = TOK_IN;
        } else if (strcmp(lex->cur.text, "return") == 0) {
            lex->cur.kind = TOK_RETURN;
        } else if (strcmp(lex->cur.text, "and") == 0) {
            lex->cur.kind = TOK_AND;
        } else if (strcmp(lex->cur.text, "or") == 0) {
            lex->cur.kind = TOK_OR;
        } else {
            lex->cur.kind = TOK_IDENT;
        }
        return;
    }

    lex->pos++;
    lex->cur.text[0] = c;
    lex->cur.text[1] = '\0';

    switch (c) {
        case '(': lex->cur.kind = TOK_LPAREN; break;
        case ')': lex->cur.kind = TOK_RPAREN; break;
        case '{': lex->cur.kind = TOK_LBRACE; break;
        case '}': lex->cur.kind = TOK_RBRACE; break;
        case ':': lex->cur.kind = TOK_COLON; break;
        case ',': lex->cur.kind = TOK_COMMA; break;
        case '+': lex->cur.kind = TOK_PLUS; break;
        case '*': lex->cur.kind = TOK_STAR; break;
        case '/': lex->cur.kind = TOK_SLASH; break;
        case '%': lex->cur.kind = TOK_PERCENT; break;
        case '^': lex->cur.kind = TOK_CARET; break;
        case '&': lex->cur.kind = TOK_AMP; break;
        case '|': lex->cur.kind = TOK_PIPE; break;
        case '-':
            if (lex->src[lex->pos] == '>') {
                lex->pos++;
                lex->cur.kind = TOK_ARROW;
            } else {
                lex->cur.kind = TOK_MINUS;
            }
            break;
        case '=':
            if (lex->src[lex->pos] == '=') {
                lex->pos++;
                lex->cur.kind = TOK_EQ;
            } else {
                lex->cur.kind = TOK_ASSIGN;
            }
            break;
        case '!':
            if (lex->src[lex->pos] == '=') {
                lex->pos++;
                lex->cur.kind = TOK_NE;
            }
            break;
        case '<':
            if (lex->src[lex->pos] == '=') {
                lex->pos++;
                lex->cur.kind = TOK_LE;
            } else {
                lex->cur.kind = TOK_LT;
            }
            break;
        case '>':
            if (lex->src[lex->pos] == '=') {
                lex->pos++;
                lex->cur.kind = TOK_GE;
            } else {
                lex->cur.kind = TOK_GT;
            }
            break;
        case '.':
            if (lex->src[lex->pos] == '.') {
                lex->pos++;
                lex->cur.kind = TOK_DOTDOT;
            }
            break;
        default:
            break;
    }
}

typedef struct {
    char name[32];
    int reg;
} symbol_t;

typedef struct {
    lexer_t *lex;
    ujit_func_t *fn;
    symbol_t locals[UJIT_MAX_LOCALS];
    size_t local_count;
    int next_reg;
} parser_t;

static int alloc_reg(parser_t *p) {
    return p->next_reg++;
}

static int resolve_or_alloc_local(parser_t *p, const char *name) {
    for (size_t i = 0; i < p->local_count; i++) {
        if (strcmp(p->locals[i].name, name) == 0) {
            return p->locals[i].reg;
        }
    }
    if (p->local_count >= UJIT_MAX_LOCALS) return -1;
    int r = alloc_reg(p);
    strncpy(p->locals[p->local_count].name, name, 31);
    p->locals[p->local_count].name[31] = '\0';
    p->locals[p->local_count].reg = r;
    p->local_count++;
    return r;
}

static int lookup_local(parser_t *p, const char *name) {
    for (size_t i = 0; i < p->local_count; i++) {
        if (strcmp(p->locals[i].name, name) == 0) {
            return p->locals[i].reg;
        }
    }
    return -1;
}

static void emit_ir(parser_t *p, ir_op_t op, int dst, int src1, int src2, int64_t imm) {
    if (p->fn->inst_count >= UJIT_MAX_INSTRUCTIONS) return;
    ir_inst_t *inst = &p->fn->insts[p->fn->inst_count++];
    inst->op = op;
    inst->dst = dst;
    inst->src1 = src1;
    inst->src2 = src2;
    inst->imm = imm;
}

/* Recursive Descent Expression Parsing */
static int parse_expr(parser_t *p);

static int parse_primary(parser_t *p) {
    if (p->lex->cur.kind == TOK_MINUS) {
        next_token(p->lex);
        if (p->lex->cur.kind == TOK_NUM) {
            int r = alloc_reg(p);
            emit_ir(p, IR_CONST, r, 0, 0, -p->lex->cur.int_val);
            next_token(p->lex);
            return r;
        }
    }
    if (p->lex->cur.kind == TOK_NUM) {
        int r = alloc_reg(p);
        emit_ir(p, IR_CONST, r, 0, 0, p->lex->cur.int_val);
        next_token(p->lex);
        return r;
    }
    if (p->lex->cur.kind == TOK_IDENT) {
        int r = lookup_local(p, p->lex->cur.text);
        if (r < 0) {
            r = resolve_or_alloc_local(p, p->lex->cur.text);
        }
        next_token(p->lex);
        return r;
    }
    if (p->lex->cur.kind == TOK_LPAREN) {
        next_token(p->lex);
        int r = parse_expr(p);
        if (p->lex->cur.kind == TOK_RPAREN) next_token(p->lex);
        return r;
    }
    return 0;
}

static int parse_multiplicative(parser_t *p) {
    int left = parse_primary(p);
    while (p->lex->cur.kind == TOK_STAR || p->lex->cur.kind == TOK_SLASH || p->lex->cur.kind == TOK_PERCENT) {
        token_kind_t op = p->lex->cur.kind;
        next_token(p->lex);
        int right = parse_primary(p);
        int res = alloc_reg(p);
        if (op == TOK_STAR) emit_ir(p, IR_IMUL, res, left, right, 0);
        else if (op == TOK_SLASH) emit_ir(p, IR_IDIV, res, left, right, 0);
        else emit_ir(p, IR_MOD, res, left, right, 0);
        left = res;
    }
    return left;
}

static int parse_additive(parser_t *p) {
    int left = parse_multiplicative(p);
    while (p->lex->cur.kind == TOK_PLUS || p->lex->cur.kind == TOK_MINUS) {
        token_kind_t op = p->lex->cur.kind;
        next_token(p->lex);
        int right = parse_multiplicative(p);
        int res = alloc_reg(p);
        if (op == TOK_PLUS) emit_ir(p, IR_ADD, res, left, right, 0);
        else emit_ir(p, IR_SUB, res, left, right, 0);
        left = res;
    }
    return left;
}

static int parse_relational(parser_t *p) {
    int left = parse_additive(p);
    while (p->lex->cur.kind == TOK_LT || p->lex->cur.kind == TOK_LE ||
           p->lex->cur.kind == TOK_GT || p->lex->cur.kind == TOK_GE ||
           p->lex->cur.kind == TOK_EQ || p->lex->cur.kind == TOK_NE) {
        token_kind_t op = p->lex->cur.kind;
        next_token(p->lex);
        int right = parse_additive(p);
        int res = alloc_reg(p);
        ir_op_t ir_op = IR_CMP_EQ;
        if (op == TOK_LT) ir_op = IR_CMP_LT;
        else if (op == TOK_LE) ir_op = IR_CMP_LE;
        else if (op == TOK_GT) ir_op = IR_CMP_GT;
        else if (op == TOK_GE) ir_op = IR_CMP_GE;
        else if (op == TOK_NE) ir_op = IR_CMP_NE;
        emit_ir(p, ir_op, res, left, right, 0);
        left = res;
    }
    return left;
}

static int parse_expr(parser_t *p) {
    return parse_relational(p);
}

static void parse_block(parser_t *p);

static void parse_statement(parser_t *p) {
    if (p->lex->cur.kind == TOK_LET) {
        next_token(p->lex);
        char var_name[32];
        strncpy(var_name, p->lex->cur.text, 31);
        next_token(p->lex);
        if (p->lex->cur.kind == TOK_ASSIGN) {
            next_token(p->lex);
            int expr_reg = parse_expr(p);
            int var_reg = resolve_or_alloc_local(p, var_name);
            emit_ir(p, IR_MOV, var_reg, expr_reg, 0, 0);
        }
        return;
    }

    if (p->lex->cur.kind == TOK_RETURN) {
        next_token(p->lex);
        int r = parse_expr(p);
        emit_ir(p, IR_RET, 0, r, 0, 0);
        return;
    }

    if (p->lex->cur.kind == TOK_IF) {
        next_token(p->lex);
        int cond_reg = parse_expr(p);
        size_t jz_idx = p->fn->inst_count;
        emit_ir(p, IR_JZ, 0, cond_reg, 0, 0); /* Target patched later */

        parse_block(p);

        if (p->lex->cur.kind == TOK_ELSE) {
            next_token(p->lex);
            size_t jmp_idx = p->fn->inst_count;
            emit_ir(p, IR_JMP, 0, 0, 0, 0);
            p->fn->insts[jz_idx].imm = (int64_t)p->fn->inst_count;
            parse_block(p);
            p->fn->insts[jmp_idx].imm = (int64_t)p->fn->inst_count;
        } else {
            p->fn->insts[jz_idx].imm = (int64_t)p->fn->inst_count;
        }
        return;
    }

    if (p->lex->cur.kind == TOK_WHILE) {
        next_token(p->lex);
        size_t loop_start = p->fn->inst_count;
        int cond_reg = parse_expr(p);
        size_t exit_jz = p->fn->inst_count;
        emit_ir(p, IR_JZ, 0, cond_reg, 0, 0);

        parse_block(p);

        emit_ir(p, IR_JMP, 0, 0, 0, (int64_t)loop_start);
        p->fn->insts[exit_jz].imm = (int64_t)p->fn->inst_count;
        return;
    }

    if (p->lex->cur.kind == TOK_IDENT) {
        char var_name[32];
        strncpy(var_name, p->lex->cur.text, 31);
        next_token(p->lex);
        if (p->lex->cur.kind == TOK_ASSIGN) {
            next_token(p->lex);
            int expr_reg = parse_expr(p);
            int var_reg = resolve_or_alloc_local(p, var_name);
            emit_ir(p, IR_MOV, var_reg, expr_reg, 0, 0);
        }
        return;
    }

    /* Skip unknown token */
    next_token(p->lex);
}

static void parse_block(parser_t *p) {
    if (p->lex->cur.kind == TOK_LBRACE) {
        next_token(p->lex);
        while (p->lex->cur.kind != TOK_RBRACE && p->lex->cur.kind != TOK_EOF) {
            parse_statement(p);
        }
        if (p->lex->cur.kind == TOK_RBRACE) next_token(p->lex);
    } else {
        parse_statement(p);
    }
}

ujit_status_t ujit_parse_and_build_ir(ujit_ctx_t *ctx, const char *source) {
    if (ctx == NULL || source == NULL) return UJIT_ERR_SYNTAX;

    lexer_t lex;
    lexer_init(&lex, source);

    while (lex.cur.kind != TOK_EOF) {
        if (lex.cur.kind == TOK_FN) {
            next_token(&lex);
            if (lex.cur.kind != TOK_IDENT) return UJIT_ERR_SYNTAX;

            if (ctx->func_count >= UJIT_MAX_FUNCS) return UJIT_ERR_MEMORY;
            ujit_func_t *fn = &ctx->funcs[ctx->func_count++];
            memset(fn, 0, sizeof(ujit_func_t));
            strncpy(fn->name, lex.cur.text, 31);
            next_token(&lex);

            parser_t p;
            p.lex = &lex;
            p.fn = fn;
            p.local_count = 0;
            p.next_reg = 0;

            if (lex.cur.kind == TOK_LPAREN) {
                next_token(&lex);
                while (lex.cur.kind == TOK_IDENT) {
                    char param_name[32];
                    strncpy(param_name, lex.cur.text, 31);
                    next_token(&lex);
                    if (lex.cur.kind == TOK_COLON) {
                        next_token(&lex);
                        if (lex.cur.kind == TOK_IDENT) next_token(&lex); /* Skip type (int, num) */
                    }
                    resolve_or_alloc_local(&p, param_name);
                    fn->num_params++;
                    if (lex.cur.kind == TOK_COMMA) next_token(&lex);
                }
                if (lex.cur.kind == TOK_RPAREN) next_token(&lex);
            }

            if (lex.cur.kind == TOK_ARROW) {
                next_token(&lex);
                if (lex.cur.kind == TOK_IDENT) next_token(&lex); /* Skip return type */
            }

            parse_block(&p);

            /* If no explicit return, emit IR_RET 0 */
            if (fn->inst_count == 0 || fn->insts[fn->inst_count - 1].op != IR_RET) {
                int r0 = alloc_reg(&p);
                emit_ir(&p, IR_CONST, r0, 0, 0, 0);
                emit_ir(&p, IR_RET, 0, r0, 0, 0);
            }
            fn->num_locals = (uint8_t)p.next_reg;
        } else {
            next_token(&lex);
        }
    }

    return UJIT_OK;
}
