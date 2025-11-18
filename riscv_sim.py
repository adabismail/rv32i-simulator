import sys
import re

# ---------- Utilities ----------
def reg_to_index(r):
    if r.startswith('x'):
        return int(r[1:])
    raise ValueError(f"Bad register {r}")

def imm_val(s):
    s = s.strip()
    if s == '':
        raise ValueError("Empty immediate")
    # handle optional sign and hex/dec
    m = re.match(r'^([+-]?)(0x[0-9a-fA-F]+|\d+)$', s)
    if not m:
        raise ValueError(f"Bad immediate: {s}")
    sign, body = m.groups()
    if body.startswith('0x') or body.startswith('0X'):
        val = int(body, 16)
    else:
        val = int(body, 10)
    if sign == '-':
        val = -val
    return val

# ---------- Parser / Assembler (two-pass) ----------
def load_and_assemble(filename):
    with open(filename) as f:
        raw_lines = [ln.split('#',1)[0].rstrip() for ln in f.readlines()]
    # remove empty lines
    lines = [ln.strip() for ln in raw_lines if ln.strip()!='']

    # pass 1: record labels
    labels = {}
    instrs = []
    pc = 0
    for ln in lines:
        if ln.endswith(':'):
            lbl = ln[:-1].strip()
            labels[lbl] = pc
        else:
            instrs.append((pc, ln))
            pc += 4

    # pass 2: keep instructions; we'll resolve labels during execution for branches/jumps
    return instrs, labels

# ---------- Simulator State ----------
class Simulator:
    def __init__(self, instrs, labels, mem_size=1024):
        self.instrs = {pc: text for pc, text in instrs}
        self.labels = labels
        self.regs = [0]*32
        self.pc = 0
        self.mem = bytearray(mem_size)  # byte-addressable
        self.max_pc = max(self.instrs.keys()) if self.instrs else -4

    def read_word(self, addr):
        # bounds & alignment checks
        if addr < 0 or addr+4 > len(self.mem):
            raise IndexError(f"Bad memory read at {addr}")
        if addr % 4 != 0:
            raise ValueError(f"Unaligned memory read at {addr}")
        b = self.mem[addr:addr+4]
        return int.from_bytes(b, 'little', signed=False)

    def write_word(self, addr, val):
        if addr < 0 or addr+4 > len(self.mem):
            raise IndexError(f"Bad memory write at {addr}")
        if addr % 4 != 0:
            raise ValueError(f"Unaligned memory write at {addr}")
        self.mem[addr:addr+4] = int(val & 0xFFFFFFFF).to_bytes(4, 'little', signed=False)

    def trace(self, instr, changed_regs=None, changed_mem=None):
        changed_regs = changed_regs or {}
        changed_mem = changed_mem or {}
        print(f"PC={self.pc:03d} | {instr}")
        if changed_regs:
            for r,v in changed_regs.items():
                print(f"    {r} -> 0x{v:08x} ({v})")
        if changed_mem:
            for a,v in changed_mem.items():
                print(f"    mem[{a}] -> 0x{v:08x} ({v})")
        print()

    def resolve_label(self, token):
        # token may be label or immediate address
        if token in self.labels:
            return self.labels[token]
        return imm_val(token)

    def step(self):
        if self.pc not in self.instrs:
            return False  # finished
        text = self.instrs[self.pc]
        instr = text.strip()
        # simple tokenizing
        parts = re.split(r'[,\s()]+', instr)
        parts = [p for p in parts if p!='']
        op = parts[0]
        changed_regs = {}
        changed_mem = {}

        next_pc = self.pc + 4

        if op == 'halt' or op == 'ecall':
            self.trace(instr)
            return False

        if op == 'add':
            rd = reg_to_index(parts[1]); rs1 = reg_to_index(parts[2]); rs2 = reg_to_index(parts[3])
            val = (self.regs[rs1] + self.regs[rs2]) & 0xFFFFFFFF
            if rd != 0:
                self.regs[rd] = val
                changed_regs[f'x{rd}'] = val

        elif op == 'sub':
            rd = reg_to_index(parts[1]); rs1 = reg_to_index(parts[2]); rs2 = reg_to_index(parts[3])
            val = (self.regs[rs1] - self.regs[rs2]) & 0xFFFFFFFF
            if rd != 0:
                self.regs[rd] = val
                changed_regs[f'x{rd}'] = val

        elif op == 'addi':
            rd = reg_to_index(parts[1]); rs1 = reg_to_index(parts[2]); imm = imm_val(parts[3])
            val = (self.regs[rs1] + imm) & 0xFFFFFFFF
            if rd != 0:
                self.regs[rd] = val
                changed_regs[f'x{rd}'] = val

        elif op == 'lw':
            rd = reg_to_index(parts[1]); offset = imm_val(parts[2]); rs1 = reg_to_index(parts[3])
            addr = (self.regs[rs1] + offset) & 0xFFFFFFFF
            val = self.read_word(addr)
            if rd != 0:
                self.regs[rd] = val & 0xFFFFFFFF
                changed_regs[f'x{rd}'] = self.regs[rd]

        elif op == 'sw':
            rs2 = reg_to_index(parts[1]); offset = imm_val(parts[2]); rs1 = reg_to_index(parts[3])
            addr = (self.regs[rs1] + offset) & 0xFFFFFFFF
            val = self.regs[rs2]
            self.write_word(addr, val)
            changed_mem[addr] = val

        elif op == 'beq':
            rs1 = reg_to_index(parts[1]); rs2 = reg_to_index(parts[2]); target = self.resolve_label(parts[3])
            if self.regs[rs1] == self.regs[rs2]:
                next_pc = target

        elif op == 'bne':
            rs1 = reg_to_index(parts[1]); rs2 = reg_to_index(parts[2]); target = self.resolve_label(parts[3])
            if self.regs[rs1] != self.regs[rs2]:
                next_pc = target

        elif op == 'jal':
            rd = reg_to_index(parts[1]); target = self.resolve_label(parts[2])
            ret = self.pc + 4
            if rd != 0:
                self.regs[rd] = ret & 0xFFFFFFFF
                changed_regs[f'x{rd}'] = self.regs[rd]
            next_pc = target

        elif op == 'jalr':
            rd = reg_to_index(parts[1]); rs1 = reg_to_index(parts[2]); imm = imm_val(parts[3])
            ret = self.pc + 4
            target = (self.regs[rs1] + imm) & ~1
            if rd != 0:
                self.regs[rd] = ret & 0xFFFFFFFF
                changed_regs[f'x{rd}'] = self.regs[rd]
            next_pc = target

        else:
            raise NotImplementedError(f"Unknown op: {op}")

        self.trace(instr, changed_regs, changed_mem)
        self.pc = next_pc
        # ensure x0 stays zero
        self.regs[0] = 0
        return True

    def run(self, max_steps=10000):
        steps = 0
        while steps < max_steps:
            cont = self.step()
            if not cont:
                break
            steps += 1
        print("Simulation finished. Steps:", steps)
        print("Final registers (non-zero):")
        for i,v in enumerate(self.regs):
            if v != 0:
                print(f"x{i} = 0x{v:08x} ({v})")
        print()

# ---------- Main ----------
def main():
    if len(sys.argv) < 2:
        print("Usage: python riscv_sim.py program.s")
        return
    instrs, labels = load_and_assemble(sys.argv[1])
    sim = Simulator(instrs, labels)
    sim.run()

if __name__ == '__main__':
    main()
