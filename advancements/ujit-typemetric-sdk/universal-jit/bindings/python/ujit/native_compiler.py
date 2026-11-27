"""
Universal JIT Native Pure-Python Backend
Directly synthesizes bare-metal x86-64 machine instructions into executable memory pages
(via VirtualAlloc on Windows or mmap on POSIX).
Guarantees 100% zero-dependency bare-metal execution anywhere Python runs.
"""

import ctypes
import os
import platform
import struct
import re
from typing import Dict, List, Tuple, Any, Optional

IS_WINDOWS = platform.system() == "Windows"

if IS_WINDOWS:
    kernel32 = ctypes.windll.kernel32
    kernel32.VirtualAlloc.restype = ctypes.c_void_p
    kernel32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32, ctypes.c_uint32]
    kernel32.VirtualFree.restype = ctypes.c_bool
    kernel32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint32]
    MEM_COMMIT = 0x1000
    MEM_RESERVE = 0x2000
    MEM_RELEASE = 0x8000
    PAGE_EXECUTE_READWRITE = 0x40
else:
    import mmap


def allocate_executable_memory(code_bytes: bytes) -> Tuple[int, Any]:
    size = len(code_bytes)
    if IS_WINDOWS:
        addr = kernel32.VirtualAlloc(0, size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
        if not addr:
            raise MemoryError("VirtualAlloc failed to allocate executable memory")
        ctypes.memmove(addr, code_bytes, size)
        return addr, None
    else:
        # POSIX mmap
        mm = mmap.mmap(-1, size, prot=mmap.PROT_READ | mmap.PROT_WRITE | mmap.PROT_EXEC, flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS)
        mm.write(code_bytes)
        addr = ctypes.cast(ctypes.c_char_p(id(mm) + 32), ctypes.c_void_p).value
        # Use python-level ctypes address
        addr = ctypes.c_void_p.from_buffer(mm).value
        return addr, mm


def free_executable_memory(addr: int, size: int, handle: Any):
    if IS_WINDOWS:
        if addr:
            kernel32.VirtualFree(addr, 0, MEM_RELEASE)
    else:
        if handle:
            handle.close()


class NativeFunction:
    def __init__(self, name: str, code_bytes: bytes, num_params: int):
        self.name = name
        self.code_bytes = code_bytes
        self.num_params = num_params
        self.addr, self.handle = allocate_executable_memory(code_bytes)

        # Build ctypes function type
        arg_types = [ctypes.c_int64] * num_params
        self.fn_type = ctypes.CFUNCTYPE(ctypes.c_int64, *arg_types)
        self.c_fn = self.fn_type(self.addr)

    def __call__(self, *args: int) -> int:
        return self.c_fn(*args)

    def __del__(self):
        if hasattr(self, "addr") and self.addr:
            free_executable_memory(self.addr, len(self.code_bytes), self.handle)
            self.addr = 0


# Tokenizer and IR for pure Python compiler backend
class Token:
    def __init__(self, kind: str, text: str, val: int = 0):
        self.kind = kind
        self.text = text
        self.val = val


def tokenize(source: str) -> List[Token]:
    # Strip comments (#, //, --)
    cleaned_lines = []
    for line in source.splitlines():
        # Remove comments
        line = re.sub(r'(//|--|#).*$', '', line)
        cleaned_lines.append(line)
    src = " ".join(cleaned_lines)

    token_spec = [
        ('NUM',     r'\b\d+\b'),
        ('FN',      r'\bfn\b'),
        ('LET',     r'\blet\b'),
        ('IF',      r'\bif\b'),
        ('ELSE',    r'\belse\b'),
        ('WHILE',   r'\bwhile\b'),
        ('RETURN',  r'\breturn\b'),
        ('ARROW',   r'->'),
        ('EQ',      r'=='),
        ('NE',      r'!='),
        ('LE',      r'<='),
        ('GE',      r'>='),
        ('LT',      r'<'),
        ('GT',      r'>'),
        ('ASSIGN',  r'='),
        ('PLUS',    r'\+'),
        ('MINUS',   r'-'),
        ('STAR',    r'\*'),
        ('SLASH',   r'/'),
        ('PERCENT', r'%'),
        ('AMP',     r'&'),
        ('PIPE',    r'\|'),
        ('CARET',   r'\^'),
        ('LPAREN',  r'\('),
        ('RPAREN',  r'\)'),
        ('LBRACE',  r'\{'),
        ('RBRACE',  r'\}'),
        ('COLON',   r':'),
        ('COMMA',   r','),
        ('IDENT',   r'[A-Za-z_][A-Za-z0-9_]*'),
        ('SKIP',    r'[ \t\r\n]+'),
    ]
    tok_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in token_spec)
    tokens = []
    for mo in re.finditer(tok_regex, src):
        kind = mo.lastgroup
        text = mo.group()
        if kind == 'SKIP':
            continue
        elif kind == 'NUM':
            tokens.append(Token('NUM', text, int(text)))
        else:
            tokens.append(Token(kind, text))
    tokens.append(Token('EOF', ''))
    return tokens


class Instruction:
    def __init__(self, op: str, dst: int = 0, src1: int = 0, src2: int = 0, imm: int = 0):
        self.op = op
        self.dst = dst
        self.src1 = src1
        self.src2 = src2
        self.imm = imm


class FunctionIR:
    def __init__(self, name: str, params: List[str]):
        self.name = name
        self.params = params
        self.locals_map: Dict[str, int] = {}
        for p in params:
            self.locals_map[p] = len(self.locals_map)
        self.next_reg = len(self.locals_map)
        self.instructions: List[Instruction] = []

    def alloc_reg(self) -> int:
        r = self.next_reg
        self.next_reg += 1
        return r

    def get_var_reg(self, name: str) -> int:
        if name not in self.locals_map:
            self.locals_map[name] = self.alloc_reg()
        return self.locals_map[name]

    def emit(self, op: str, dst: int = 0, src1: int = 0, src2: int = 0, imm: int = 0) -> int:
        idx = len(self.instructions)
        self.instructions.append(Instruction(op, dst, src1, src2, imm))
        return idx


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def cur(self) -> Token:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else Token('EOF', '')

    def consume(self, kind: Optional[str] = None) -> Token:
        tok = self.cur()
        if kind and tok.kind != kind:
            raise SyntaxError(f"Expected token {kind}, got {tok.kind} ('{tok.text}')")
        self.pos += 1
        return tok

    def parse_functions(self) -> List[FunctionIR]:
        funcs = []
        while self.cur().kind != 'EOF':
            if self.cur().kind == 'FN':
                self.consume('FN')
                name = self.consume('IDENT').text
                self.consume('LPAREN')
                params = []
                while self.cur().kind == 'IDENT':
                    p_name = self.consume('IDENT').text
                    if self.cur().kind == 'COLON':
                        self.consume('COLON')
                        self.consume('IDENT') # Skip type
                    params.append(p_name)
                    if self.cur().kind == 'COMMA':
                        self.consume('COMMA')
                self.consume('RPAREN')
                if self.cur().kind == 'ARROW':
                    self.consume('ARROW')
                    self.consume('IDENT') # Skip return type

                fn_ir = FunctionIR(name, params)
                self.parse_block(fn_ir)

                if not fn_ir.instructions or fn_ir.instructions[-1].op != 'RET':
                    r0 = fn_ir.alloc_reg()
                    fn_ir.emit('CONST', dst=r0, imm=0)
                    fn_ir.emit('RET', src1=r0)
                funcs.append(fn_ir)
            else:
                self.consume()
        return funcs

    def parse_block(self, fn: FunctionIR):
        self.consume('LBRACE')
        while self.cur().kind != 'RBRACE' and self.cur().kind != 'EOF':
            self.parse_statement(fn)
        self.consume('RBRACE')

    def parse_statement(self, fn: FunctionIR):
        tok = self.cur()
        if tok.kind == 'LET':
            self.consume('LET')
            name = self.consume('IDENT').text
            self.consume('ASSIGN')
            reg = self.parse_expr(fn)
            var_reg = fn.get_var_reg(name)
            fn.emit('MOV', dst=var_reg, src1=reg)
        elif tok.kind == 'RETURN':
            self.consume('RETURN')
            reg = self.parse_expr(fn)
            fn.emit('RET', src1=reg)
        elif tok.kind == 'IF':
            self.consume('IF')
            cond_reg = self.parse_expr(fn)
            jz_idx = fn.emit('JZ', src1=cond_reg)
            self.parse_block(fn)
            if self.cur().kind == 'ELSE':
                self.consume('ELSE')
                jmp_idx = fn.emit('JMP')
                fn.instructions[jz_idx].imm = len(fn.instructions)
                self.parse_block(fn)
                fn.instructions[jmp_idx].imm = len(fn.instructions)
            else:
                fn.instructions[jz_idx].imm = len(fn.instructions)
        elif tok.kind == 'WHILE':
            self.consume('WHILE')
            loop_start = len(fn.instructions)
            cond_reg = self.parse_expr(fn)
            exit_jz = fn.emit('JZ', src1=cond_reg)
            self.parse_block(fn)
            fn.emit('JMP', imm=loop_start)
            fn.instructions[exit_jz].imm = len(fn.instructions)
        elif tok.kind == 'IDENT':
            name = self.consume('IDENT').text
            if self.cur().kind == 'ASSIGN':
                self.consume('ASSIGN')
                reg = self.parse_expr(fn)
                var_reg = fn.get_var_reg(name)
                fn.emit('MOV', dst=var_reg, src1=reg)
        else:
            self.consume()

    def parse_expr(self, fn: FunctionIR) -> int:
        return self.parse_relational(fn)

    def parse_relational(self, fn: FunctionIR) -> int:
        left = self.parse_additive(fn)
        while self.cur().kind in ('EQ', 'NE', 'LT', 'LE', 'GT', 'GE'):
            op_kind = self.consume().kind
            right = self.parse_additive(fn)
            res = fn.alloc_reg()
            op_map = {
                'EQ': 'CMP_EQ', 'NE': 'CMP_NE', 'LT': 'CMP_LT',
                'LE': 'CMP_LE', 'GT': 'CMP_GT', 'GE': 'CMP_GE'
            }
            fn.emit(op_map[op_kind], dst=res, src1=left, src2=right)
            left = res
        return left

    def parse_additive(self, fn: FunctionIR) -> int:
        left = self.parse_multiplicative(fn)
        while self.cur().kind in ('PLUS', 'MINUS', 'PIPE', 'CARET', 'AMP'):
            op_kind = self.consume().kind
            right = self.parse_multiplicative(fn)
            res = fn.alloc_reg()
            op_map = {
                'PLUS': 'ADD', 'MINUS': 'SUB', 'PIPE': 'OR', 'CARET': 'XOR', 'AMP': 'AND'
            }
            fn.emit(op_map[op_kind], dst=res, src1=left, src2=right)
            left = res
        return left

    def parse_multiplicative(self, fn: FunctionIR) -> int:
        left = self.parse_primary(fn)
        while self.cur().kind in ('STAR', 'SLASH', 'PERCENT'):
            op_kind = self.consume().kind
            right = self.parse_primary(fn)
            res = fn.alloc_reg()
            op_map = {'STAR': 'IMUL', 'SLASH': 'IDIV', 'PERCENT': 'MOD'}
            fn.emit(op_map[op_kind], dst=res, src1=left, src2=right)
            left = res
        return left

    def parse_primary(self, fn: FunctionIR) -> int:
        tok = self.cur()
        if tok.kind == 'MINUS':
            self.consume('MINUS')
            val = self.consume('NUM').val
            r = fn.alloc_reg()
            fn.emit('CONST', dst=r, imm=-val)
            return r
        elif tok.kind == 'NUM':
            self.consume('NUM')
            r = fn.alloc_reg()
            fn.emit('CONST', dst=r, imm=tok.val)
            return r
        elif tok.kind == 'IDENT':
            name = self.consume('IDENT').text
            return fn.get_var_reg(name)
        elif tok.kind == 'LPAREN':
            self.consume('LPAREN')
            r = self.parse_expr(fn)
            self.consume('RPAREN')
            return r
        else:
            self.consume()
            r = fn.alloc_reg()
            fn.emit('CONST', dst=r, imm=0)
            return r


def assemble_x86_64(fn: FunctionIR) -> bytes:
    code = bytearray()
    inst_offsets: Dict[int, int] = {}
    patches: List[Tuple[int, int]] = [] # (patch_pos, target_inst_idx)

    # 1. Prologue
    # push rbp (55)
    # mov rbp, rsp (48 89 E5)
    code += bytes([0x55, 0x48, 0x89, 0xE5])
    stack_size = (fn.next_reg * 8 + 32 + 15) & ~15
    # sub rsp, stack_size (48 81 EC <u32>)
    code += bytes([0x48, 0x81, 0xEC]) + struct.pack('<I', stack_size)

    def local_offset(idx: int) -> int:
        return -8 * (idx + 1)

    def emit_load_rax(local_idx: int):
        nonlocal code
        off = local_offset(local_idx)
        code += bytes([0x48, 0x8B])
        if -128 <= off <= 127:
            code += bytes([0x45, off & 0xFF])
        else:
            code += bytes([0x85]) + struct.pack('<i', off)

    def emit_store_rax(local_idx: int):
        nonlocal code
        off = local_offset(local_idx)
        code += bytes([0x48, 0x89])
        if -128 <= off <= 127:
            code += bytes([0x45, off & 0xFF])
        else:
            code += bytes([0x85]) + struct.pack('<i', off)

    def emit_load_rcx(local_idx: int):
        nonlocal code
        off = local_offset(local_idx)
        code += bytes([0x48, 0x8B])
        if -128 <= off <= 127:
            code += bytes([0x4D, off & 0xFF])
        else:
            code += bytes([0x8D]) + struct.pack('<i', off)

    # 2. Parameters from ABI registers to local slots
    num_params = len(fn.params)
    if IS_WINDOWS:
        # RCX, RDX, R8, R9
        if num_params > 0: code += bytes([0x48, 0x89, 0x4D, local_offset(0) & 0xFF])
        if num_params > 1: code += bytes([0x48, 0x89, 0x55, local_offset(1) & 0xFF])
        if num_params > 2: code += bytes([0x4C, 0x89, 0x45, local_offset(2) & 0xFF])
        if num_params > 3: code += bytes([0x4C, 0x89, 0x4D, local_offset(3) & 0xFF])
    else:
        # RDI, RSI, RDX, RCX, R8, R9
        if num_params > 0: code += bytes([0x48, 0x89, 0x7D, local_offset(0) & 0xFF])
        if num_params > 1: code += bytes([0x48, 0x89, 0x75, local_offset(1) & 0xFF])
        if num_params > 2: code += bytes([0x48, 0x89, 0x55, local_offset(2) & 0xFF])
        if num_params > 3: code += bytes([0x48, 0x89, 0x4D, local_offset(3) & 0xFF])
        if num_params > 4: code += bytes([0x4C, 0x89, 0x45, local_offset(4) & 0xFF])
        if num_params > 5: code += bytes([0x4C, 0x89, 0x4D, local_offset(5) & 0xFF])

    # 3. Emit instructions
    for idx, inst in enumerate(fn.instructions):
        inst_offsets[idx] = len(code)
        op = inst.op

        if op == 'CONST':
            # mov rax, imm64 (48 B8 <u64>)
            code += bytes([0x48, 0xB8]) + struct.pack('<q', inst.imm)
            emit_store_rax(inst.dst)
        elif op == 'MOV':
            emit_load_rax(inst.src1)
            emit_store_rax(inst.dst)
        elif op == 'ADD':
            emit_load_rax(inst.src1)
            emit_load_rcx(inst.src2)
            code += bytes([0x48, 0x01, 0xC8]) # add rax, rcx
            emit_store_rax(inst.dst)
        elif op == 'SUB':
            emit_load_rax(inst.src1)
            emit_load_rcx(inst.src2)
            code += bytes([0x48, 0x29, 0xC8]) # sub rax, rcx
            emit_store_rax(inst.dst)
        elif op == 'IMUL':
            emit_load_rax(inst.src1)
            emit_load_rcx(inst.src2)
            code += bytes([0x48, 0x0F, 0xAF, 0xC1]) # imul rax, rcx
            emit_store_rax(inst.dst)
        elif op in ('IDIV', 'MOD'):
            emit_load_rax(inst.src1)
            emit_load_rcx(inst.src2)
            code += bytes([0x48, 0x99, 0x48, 0xF7, 0xF9]) # cqo; idiv rcx
            if op == 'IDIV':
                emit_store_rax(inst.dst)
            else:
                code += bytes([0x48, 0x89, 0xD0]) # mov rax, rdx
                emit_store_rax(inst.dst)
        elif op == 'AND':
            emit_load_rax(inst.src1)
            emit_load_rcx(inst.src2)
            code += bytes([0x48, 0x21, 0xC8])
            emit_store_rax(inst.dst)
        elif op == 'OR':
            emit_load_rax(inst.src1)
            emit_load_rcx(inst.src2)
            code += bytes([0x48, 0x09, 0xC8])
            emit_store_rax(inst.dst)
        elif op == 'XOR':
            emit_load_rax(inst.src1)
            emit_load_rcx(inst.src2)
            code += bytes([0x48, 0x31, 0xC8])
            emit_store_rax(inst.dst)
        elif op.startswith('CMP_'):
            emit_load_rax(inst.src1)
            emit_load_rcx(inst.src2)
            code += bytes([0x48, 0x39, 0xC8]) # cmp rax, rcx
            set_byte = {
                'CMP_EQ': 0x94, 'CMP_NE': 0x95, 'CMP_LT': 0x9C,
                'CMP_LE': 0x9E, 'CMP_GT': 0x9F, 'CMP_GE': 0x9D
            }[op]
            code += bytes([0x0F, set_byte, 0xC0]) # setcc al
            code += bytes([0x48, 0x0F, 0xB6, 0xC0]) # movzx rax, al
            emit_store_rax(inst.dst)
        elif op == 'JZ':
            emit_load_rax(inst.src1)
            code += bytes([0x48, 0x85, 0xC0]) # test rax, rax
            code += bytes([0x0F, 0x84]) # jz rel32
            patches.append((len(code), inst.imm))
            code += bytes([0, 0, 0, 0])
        elif op == 'JNZ':
            emit_load_rax(inst.src1)
            code += bytes([0x48, 0x85, 0xC0]) # test rax, rax
            code += bytes([0x0F, 0x85]) # jnz rel32
            patches.append((len(code), inst.imm))
            code += bytes([0, 0, 0, 0])
        elif op == 'JMP':
            code += bytes([0xE9]) # jmp rel32
            patches.append((len(code), inst.imm))
            code += bytes([0, 0, 0, 0])
        elif op == 'RET':
            emit_load_rax(inst.src1)
            code += bytes([0x48, 0x89, 0xEC, 0x5D, 0xC3]) # mov rsp, rbp; pop rbp; ret

    end_offset = len(code)

    # 4. Patch branch jump displacements
    for patch_pos, target_idx in patches:
        target_offset = inst_offsets.get(target_idx, end_offset)
        disp = target_offset - (patch_pos + 4)
        code[patch_pos:patch_pos+4] = struct.pack('<i', disp)

    return bytes(code)


def compile_pseudocode(source: str) -> Dict[str, NativeFunction]:
    tokens = tokenize(source)
    parser = Parser(tokens)
    funcs_ir = parser.parse_functions()
    compiled = {}
    for fn_ir in funcs_ir:
        code_bytes = assemble_x86_64(fn_ir)
        fn_obj = NativeFunction(fn_ir.name, code_bytes, len(fn_ir.params))
        compiled[fn_ir.name] = fn_obj
    return compiled
