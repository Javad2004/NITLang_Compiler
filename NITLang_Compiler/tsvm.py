import sys
import re
import shlex

class TSVM:
    def __init__(self, memory_size=50000):
        # --- Architecture ---
        # Registers: r0-rN, fp, sp
        # Stack starts at 9000 and grows downwards
        self.registers = {
            'r0': 0, 'sp': 9000, 'fp': 9000, 
        }
        # Memory: 0-9000 (Stack), 10000+ (Globals), 20000+ (Heap)
        self.memory = [0] * memory_size
        self.heap_ptr = 20000 
        
        self.program = []
        self.labels = {}
        self.ip = 0 

    def load_program(self, filepath):
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(f"Error: File '{filepath}' not found.")
            sys.exit(1)

        valid_lines = []
        for line in lines:
            line = line.split('#')[0].strip()
            if not line:
                continue
            
            if line.endswith(':'):
                label = line[:-1]
                self.labels[label] = len(valid_lines)
                continue
            
            if line.startswith('proc '):
                label = line.split()[1]
                self.labels[label] = len(valid_lines)
                valid_lines.append(['proc', label]) 
                continue
            
            try:
                parts = shlex.split(line)
                clean_parts = []
                for p in parts:
                    if p.endswith(','): p = p[:-1]
                    if p == ',': continue
                    clean_parts.append(p)
                valid_lines.append(clean_parts)
            except ValueError as e:
                print(f"Error parsing line: {line}\n{e}")
                sys.exit(1)
        
        self.program = valid_lines

    def get_val(self, arg):
        try:
            return int(arg)
        except ValueError:
            return self.registers.get(arg, 0)

    def set_reg(self, reg, val):
        self.registers[reg] = int(val)

    def run(self):
        if 'main' not in self.labels:
            print("Error: No 'main' procedure found.")
            sys.exit(1)

        self.ip = 0
        running_globals = True

        while running_globals and self.ip < len(self.program):
            inst = self.program[self.ip]
            op = inst[0]

            if op == 'proc':
                depth = 1
                self.ip += 1
                while self.ip < len(self.program) and depth > 0:
                    next_inst = self.program[self.ip]
                    if next_inst[0] == 'proc':
                        depth += 1
                    elif next_inst[0] == 'ret':
                        depth -= 1
                    self.ip += 1
                continue

            self._execute_instruction(inst)

            if self.ip >= len(self.program) - 1:
                running_globals = False
            else:
                self.ip += 1

        self.registers['sp'] -= 1
        self.memory[self.registers['sp']] = -1

        self.ip = self.labels['main']

        while self.ip < len(self.program):
            inst = self.program[self.ip]

            if inst[0] == 'proc':
                self.ip += 1
                continue

            self._execute_instruction(inst)
            self.ip += 1

    def _execute_instruction(self, inst):
        op = inst[0]
        
        if op == 'mov':
            self.set_reg(inst[1], self.get_val(inst[2]))

        elif op == 'sload':
            dest_reg = inst[1]
            string_content = inst[2] 
            
            ptr = self.heap_ptr
            self.set_reg(dest_reg, ptr)
            
            for char in string_content:
                self.memory[self.heap_ptr] = ord(char)
                self.heap_ptr += 1
            
            self.memory[self.heap_ptr] = 0
            self.heap_ptr += 1

        elif op == 'push':
            val = self.get_val(inst[1])
            self.registers['sp'] -= 1
            self.memory[self.registers['sp']] = val

        elif op == 'pop':
            val = self.memory[self.registers['sp']]
            self.registers['sp'] += 1
            self.set_reg(inst[1], val)

        elif op == 'ld':
            src_str = inst[2].strip('[]')
            addr = self.get_val(src_str)
            if 0 <= addr < len(self.memory):
                val = self.memory[addr]
                if val is None:
                    print(f"Runtime Error: Read uninitialized memory at address {addr}")
                    sys.exit(1)
                self.set_reg(inst[1], val)
            else:
                print(f"Runtime Error: Memory access out of bounds (ld) at {addr}")
                sys.exit(1)

        elif op == 'st':
            dest_str = inst[1].strip('[]')
            addr = self.get_val(dest_str)
            val = self.get_val(inst[2])
            if 0 <= addr < len(self.memory):
                self.memory[addr] = val
            else:
                print(f"Runtime Error: Memory access out of bounds (st) at {addr}")
                sys.exit(1)

        elif op == 'add':
            res = self.get_val(inst[2]) + self.get_val(inst[3])
            self.set_reg(inst[1], res)
        
        elif op == 'sub':
            res = self.get_val(inst[2]) - self.get_val(inst[3])
            self.set_reg(inst[1], res)
        
        elif op == 'mul':
            res = self.get_val(inst[2]) * self.get_val(inst[3])
            self.set_reg(inst[1], res)
        
        elif op == 'div':
            denom = self.get_val(inst[3])
            if denom == 0:
                print("Runtime Error: Division by zero")
                sys.exit(1)
            res = int(self.get_val(inst[2]) / denom)
            self.set_reg(inst[1], res)

        elif op == 'mod':
            res = self.get_val(inst[2]) % self.get_val(inst[3])
            self.set_reg(inst[1], res)

        elif op.startswith('cmp'):
            v1 = self.get_val(inst[2])
            v2 = self.get_val(inst[3])
            res = 0
            condition = op[3:]
            if condition == '==': res = 1 if v1 == v2 else 0
            elif condition == '!=': res = 1 if v1 != v2 else 0
            elif condition == '>': res = 1 if v1 > v2 else 0
            elif condition == '>=': res = 1 if v1 >= v2 else 0
            elif condition == '<': res = 1 if v1 < v2 else 0
            elif condition == '<=': res = 1 if v1 <= v2 else 0
            self.set_reg(inst[1], res)

        elif op == 'br':
            self.ip = self.labels[inst[1]]
            self.ip -= 1 

        elif op == 'bz':
            if self.get_val(inst[1]) == 0:
                self.ip = self.labels[inst[2]]
                self.ip -= 1

        elif op == 'bnz':
            if self.get_val(inst[1]) != 0:
                self.ip = self.labels[inst[2]]
                self.ip -= 1

        elif op == 'call':
            target = inst[1]
            if target == 'iput':
                print(self.get_val(inst[2]))
            
            elif target == 'sprint':
                ptr = self.get_val(inst[2])
                while True:
                    val = self.memory[ptr]
                    if val == 0: 
                        break
                    if val is None:
                        break
                    print(chr(val), end="")
                    ptr += 1
                print()

            elif target == 'iget':
                try:
                    val = int(input())
                    self.set_reg(inst[2], val)
                except ValueError:
                    print("Runtime Error: Invalid input")
                    sys.exit(1)
            elif target == 'exit':
                sys.exit(self.get_val(inst[2]))
            elif target == 'mem':
                dst_reg = inst[2]
                size = self.get_val(inst[3])
                ptr = self.heap_ptr
                self.heap_ptr += size
                self.set_reg(dst_reg, ptr)
                for i in range(ptr, ptr + size):
                    self.memory[i] = None 

            elif target == 'vprint':
                ptr = self.get_val(inst[2])
                size_addr = ptr - 1
                if size_addr < 0 or size_addr >= len(self.memory):
                        print("Runtime Error: Invalid vector pointer")
                        sys.exit(1)
                size = self.memory[size_addr]
                if size is None:
                        print("Runtime Error: Vector corrupted")
                        sys.exit(1)
                
                print("[", end="")
                for i in range(size):
                    elem_addr = ptr + i
                    val = self.memory[elem_addr]
                    if val is None:
                        print(f"\nRuntime Error: Vector index {i} is uninitialized")
                        sys.exit(1)
                    print(val, end="")
                    if i < size - 1:
                        print(",", end="")
                print("]")

            elif target == 'vget':
                dst_reg = inst[2]
                ptr = self.get_val(inst[3])
                idx = self.get_val(inst[4])
                
                if ptr < 10000: 
                     print("Runtime Error: Invalid vector pointer")
                     sys.exit(1)

                size_addr = ptr - 1
                size = self.memory[size_addr]
                
                if idx < 0 or idx >= size:
                    print(f"Runtime Error: Vector index {idx} out of bounds (size {size})")
                    sys.exit(1)

                elem_addr = ptr + idx
                val = self.memory[elem_addr]

                if val is None:
                    print(f"Runtime Error: Vector index {idx} is uninitialized")
                    sys.exit(1)

                self.set_reg(dst_reg, val)

            else:
                ret_addr = self.ip + 1
                self.registers['sp'] -= 1
                self.memory[self.registers['sp']] = ret_addr
                self.ip = self.labels[target]
                self.ip -= 1

        elif op == 'ret':
            ret_addr = self.memory[self.registers['sp']]
            self.registers['sp'] += 1
            if ret_addr == -1:
                sys.exit(0)
            self.ip = ret_addr
            self.ip -= 1

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tsvm.py <input_file.tsvm>")
        sys.exit(1)
        
    vm = TSVM()
    vm.load_program(sys.argv[1])
    vm.run()