# simple test: add and store then load back
.text
start:
    addi x1, x0, 10      # x1 = 10
    addi x2, x0, 20      # x2 = 20
    add  x3, x1, x2      # x3 = 30
    sw   x3, 0(x0)       # mem[0] = x3
    lw   x4, 0(x0)       # x4 = mem[0]
    halt
