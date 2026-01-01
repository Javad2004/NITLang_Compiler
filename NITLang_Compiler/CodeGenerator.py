from AST import *
import copy

class CodeGenerator:
    def __init__(self, class_table, symbol_table):
        self.code = []
        self.current_function = None
        self.class_table = class_table
        self.global_symbol_table = symbol_table
        self.current_class = None
        
        self.next_register = 1
        self.label_count = 0
        
        self.var_map = {} 
        self.fp_offset = 0
        
        self.global_var_map = {} 
        self.global_base_addr = 10000 
        self.global_offset = 0

    def emit(self, instruction):
        self.code.append(instruction)

    def new_register(self):
        reg = self.next_register
        self.next_register += 1
        return reg

    def new_label(self):
        self.label_count += 1
        return f"L{self.label_count}"
    
    def _is_string_expr(self, expr):
        """Heuristic: does this expression evaluate to a string?"""
        if isinstance(expr, str):
            if expr.startswith('"') or expr.startswith("'") or expr.startswith('"""'):
                return True
            if expr in self.var_map and self.var_map[expr].get('var_type') == 'string':
                return True
            if expr in self.global_var_map and self.global_var_map[expr].get('var_type') == 'string':
                return True
        return False

    def _contains_string_expr(self, node):
        """Does this subtree contain any expression that is (definitely) a string?"""
        if node is None:
            return False

        if self._is_string_expr(node):
            return True

        if isinstance(node, BinaryOperation):
            return self._contains_string_expr(node.left) or self._contains_string_expr(node.right)

        if isinstance(node, ASTNode):
            for v in vars(node).values():
                if isinstance(v, ASTNode) and self._contains_string_expr(v):
                    return True
                if isinstance(v, list):
                    for e in v:
                        if isinstance(e, ASTNode) and self._contains_string_expr(e):
                            return True

        return False

    def _flatten_concat(self, expr, parts):
        """
        Flatten a + chain that involves strings into a list of parts.
        """
        if isinstance(expr, BinaryOperation) and expr.op == '+' and self._contains_string_expr(expr):
            self._flatten_concat(expr.left, parts)
            self._flatten_concat(expr.right, parts)
        else:
            parts.append(expr)

    def _emit_print_value(self, expr):
        value_reg, type_str = self.visit(expr)
        if type_str == 'vector':
            self.emit(f"call vprint, r{value_reg}")
        elif type_str == 'string':
            self.emit(f"call sprint, r{value_reg}")
        else:
            self.emit(f"call iput, r{value_reg}")

    def get_var_addr_reg(self, name):
        """Returns a register holding the *address* of a variable"""
        addr_reg = self.new_register()

        if name in self.var_map: 
            info = self.var_map[name]
            
            if info['scope'] == 'local':
                offset_reg = self.new_register()
                self.emit(f"mov r{offset_reg}, {info['offset']}")
                self.emit(f"sub r{addr_reg}, fp, r{offset_reg}")
            elif info['scope'] == 'param':
                offset_reg = self.new_register()
                self.emit(f"mov r{offset_reg}, {info['offset']}")
                self.emit(f"add r{addr_reg}, fp, r{offset_reg}")
            elif info['scope'] == 'field':
                this_ptr_addr_reg = self.get_var_addr_reg('this')
                this_ptr_reg = self.new_register()
                self.emit(f"ld r{this_ptr_reg}, [r{this_ptr_addr_reg}]")
                
                offset_reg = self.new_register()
                self.emit(f"mov r{offset_reg}, {info['offset']}")
                self.emit(f"add r{addr_reg}, r{this_ptr_reg}, r{offset_reg}")
            
            return addr_reg
        
        elif name in self.global_var_map: 
            info = self.global_var_map[name]
            base_addr_reg = self.new_register()
            offset_reg = self.new_register()
            self.emit(f"mov r{base_addr_reg}, {self.global_base_addr}")
            self.emit(f"mov r{offset_reg}, {info['offset']}")
            self.emit(f"add r{addr_reg}, r{base_addr_reg}, r{offset_reg}")
            return addr_reg
            
        else:
            self.emit(f"mov r{addr_reg}, 0 # Error: Var {name} not in map")
            return addr_reg

    def visit(self, node):
        if node is None: return 0, "null"
        if isinstance(node, int): return self.visit_Number(node)
        if isinstance(node, str): return self.visit_Identifier(node)
        if isinstance(node, ASTNode):
            method_name = f'visit_{type(node).__name__}'
            method = getattr(self, method_name, self.generic_visit)
            return method(node)
        if isinstance(node, list):
            for item in node: self.visit(item)
            return 0, "null"
        return 0, "unknown"

    def generic_visit(self, node):
        if not hasattr(node, '__dict__'): return 0, "null"
        for _, value in vars(node).items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ASTNode): self.visit(item)
            elif isinstance(value, ASTNode):
                self.visit(value)
        return 0, "null"

    def visit_ProgramNode(self, node):
        for child in node.children:
            self.visit(child)
        return 0, "null"

    def visit_ClassNode(self, node):
        self.current_class = self.class_table[node.name]
        for method_name, method_info in self.current_class['methods'].items():
            self.visit(method_info['node'])
        self.current_class = None
        return 0, "null"

    def visit_FunctionNode(self, node):
        self.current_function = node
        
        old_var_map = self.var_map
        old_fp_offset = self.fp_offset
        
        self.var_map = {}
        self.fp_offset = 1
        self.next_register = 1
        
        func_label = node.name
        if self.current_class:
            func_label = f"{self.current_class['name']}_{node.name}"
            
        self.emit(f"proc {func_label}")
        
        self.emit("push fp")
        self.emit("mov fp, sp")
        
        local_count = self.count_locals(node.body)
        if local_count > 0:
            count_reg = self.new_register()
            self.emit(f"mov r{count_reg}, {local_count}")
            self.emit(f"sub sp, sp, r{count_reg}")
        
        param_offset = 2
        if self.current_class:
            class_name = self.current_class['name']
            self.var_map['this'] = {'scope': 'param', 'offset': param_offset, 'var_type': class_name}
            param_offset += 1
            
            for fname, finfo in self.current_class['fields'].items():
                self.var_map[fname] = {'scope': 'field', 'offset': finfo['offset'], 'var_type': finfo['var_type']}

        for pname, ptype in node.params:
            self.var_map[pname] = {'scope': 'param', 'offset': param_offset, 'var_type': ptype}
            param_offset += 1
            
        self.visit(node.body)
        
        self.emit(f"L_{func_label}_return:")
        if local_count > 0:
            count_reg = self.new_register()
            self.emit(f"mov r{count_reg}, {local_count}")
            self.emit(f"add sp, sp, r{count_reg}")
        self.emit("pop fp")
        self.emit("ret")

        self.current_function = None
        self.var_map = old_var_map
        self.fp_offset = old_fp_offset
        return 0, "null"

    def count_locals(self, node):
        count = 0
        if isinstance(node, VariableDeclarationNode):
            count += 1
        
        for field in getattr(node, '__dict__', {}):
            child = getattr(node, field)
            if isinstance(child, ASTNode):
                if not isinstance(child, (FunctionNode, ClassNode)):
                    count += self.count_locals(child)
            elif isinstance(child, list):
                for elem in child:
                    if isinstance(elem, ASTNode):
                         if not isinstance(elem, (FunctionNode, ClassNode)):
                            count += self.count_locals(elem)
        return count

    def visit_VariableDeclarationNode(self, node):
        if self.current_function is None:
            offset = self.global_offset
            self.global_var_map[node.name] = {'scope': 'global', 'offset': offset, 'var_type': node.var_type}
            self.global_offset += 1
            
            if node.value is not None:
                value_reg, _ = self.visit(node.value)
                addr_reg = self.new_register()
                base_addr_reg = self.new_register()
                offset_reg = self.new_register()
                
                self.emit(f"mov r{base_addr_reg}, {self.global_base_addr}")
                self.emit(f"mov r{offset_reg}, {offset}")
                self.emit(f"add r{addr_reg}, r{base_addr_reg}, r{offset_reg}")
                self.emit(f"st [r{addr_reg}], r{value_reg}")
        else:
            offset = self.fp_offset
            
            extra_info = {}
            if node.var_type == 'vector':
                if isinstance(node.value, VectorNode):
                    types = []
                    for e in node.value.elements:
                        if isinstance(e, int): 
                            types.append('int')
                        elif isinstance(e, str):
                            if e.startswith('"') or e.startswith("'"): 
                                types.append('string')
                            elif e in self.var_map: 
                                types.append(self.var_map[e].get('var_type', 'unknown'))
                            else: 
                                types.append('unknown')
                        else: 
                            types.append('unknown')
                    extra_info['element_types'] = types
                elif isinstance(node.value, ListNode):
                    if isinstance(node.value.size, int):
                         extra_info['element_types'] = ['unknown'] * node.value.size

            self.var_map[node.name] = {'scope': 'local', 'offset': offset, 'var_type': node.var_type, **extra_info}
            self.fp_offset += 1
            
            if node.value is not None:
                value_reg, _ = self.visit(node.value)
                addr_reg = self.get_var_addr_reg(node.name)
                self.emit(f"st [r{addr_reg}], r{value_reg}")
        
        return 0, "null"

    def visit_AssignmentNode(self, node):
        value_reg, value_type = self.visit(node.value)
        
        if isinstance(node.var, str):
            addr_reg = self.get_var_addr_reg(node.var)
            self.emit(f"st [r{addr_reg}], r{value_reg}")
            
        elif isinstance(node.var, VectorAccessNode):
            array_ptr_reg, _ = self.visit(node.var.array_name)
            index_reg, _ = self.visit(node.var.index)
            addr_reg = self.new_register()
            self.emit(f"add r{addr_reg}, r{array_ptr_reg}, r{index_reg}")
            self.emit(f"st [r{addr_reg}], r{value_reg}")
            
            arr_name = node.var.array_name
            if isinstance(arr_name, str) and arr_name in self.var_map:
                 if 'element_types' in self.var_map[arr_name]:
                     idx = node.var.index
                     if isinstance(idx, int):
                         try:
                             self.var_map[arr_name]['element_types'][idx] = value_type
                         except IndexError:
                             pass

        elif isinstance(node.var, FieldAccessNode):
            obj_ptr_reg, obj_type = self.visit(node.var.object_expr)
            
            if obj_type in self.class_table:
                field_info = self.class_table[obj_type]['fields'][node.var.field_name]
                offset_reg = self.new_register()
                self.emit(f"mov r{offset_reg}, {field_info['offset']}")
                addr_reg = self.new_register()
                self.emit(f"add r{addr_reg}, r{obj_ptr_reg}, r{offset_reg}")
                self.emit(f"st [r{addr_reg}], r{value_reg}")
            else:
                self.emit(f"# Error: Cannot assign to field of unknown class {obj_type}")
        
        return value_reg, value_type

    def visit_RefAssignmentNode(self, node):
        value_reg, value_type = self.visit(node.value)
        ptr_reg, _ = self.visit(node.ref_var)
        
        valid_addr_label = self.new_label()
        self.emit(f"bnz r{ptr_reg}, {valid_addr_label}")
        exit_code_reg = self.new_register()
        self.emit(f"mov r{exit_code_reg}, 1 # Null Pointer Assignment")
        self.emit(f"call exit, r{exit_code_reg}")
        self.emit(f"{valid_addr_label}:")

        self.emit(f"st [r{ptr_reg}], r{value_reg}")
        return value_reg, value_type

    def visit_BinaryOperation(self, node):
        left_reg, left_type = self.visit(node.left)
        right_reg, right_type = self.visit(node.right)

        if node.op == '+':
            if left_type == 'string' or right_type == 'string':
                
                if left_type in ('int', 'bool'):
                    new_reg = self.new_register()
                    self.emit(f"call itos, r{new_reg}, r{left_reg}")
                    left_reg = new_reg
                elif left_type == 'vector':
                    new_reg = self.new_register()
                    self.emit(f"call vtos, r{new_reg}, r{left_reg}")
                    left_reg = new_reg
                
                if right_type in ('int', 'bool'):
                    new_reg = self.new_register()
                    self.emit(f"call itos, r{new_reg}, r{right_reg}")
                    right_reg = new_reg
                elif right_type == 'vector':
                    new_reg = self.new_register()
                    self.emit(f"call vtos, r{new_reg}, r{right_reg}")
                    right_reg = new_reg
                
                result_reg = self.new_register()
                self.emit(f"call sconcat, r{result_reg}, r{left_reg}, r{right_reg}")
                return result_reg, "string"

        result_reg = self.new_register()

        op_map = {
            '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'mod',
            '<': 'cmp<', '<=': 'cmp<=', '>': 'cmp>', '>=': 'cmp>=',
            '==': 'cmp==', '!=': 'cmp!=', '&&': 'and', '||': 'or'
        }

        if node.op not in op_map:
            self.emit(f"# Error: Unknown binary operator {node.op}")
            return result_reg, "unknown"

        self.emit(f"{op_map[node.op]} r{result_reg}, r{left_reg}, r{right_reg}")

        return_type = "int"
        if node.op in ['<', '<=', '>', '>=', '==', '!=', '&&', '||']:
            return_type = "bool"

        return result_reg, return_type

    def visit_SingleOperation(self, node):
        operand_reg, operand_type = self.visit(node.right)
        result_reg = self.new_register()
        
        if node.op == '-':
            zero_reg = self.new_register()
            self.emit(f"mov r{zero_reg}, 0")
            self.emit(f"sub r{result_reg}, r{zero_reg}, r{operand_reg}")
            return result_reg, "int"
            
        elif node.op == '!':
            if operand_type == "ref" or operand_type.startswith("ref_"):
                
                valid_addr_label = self.new_label()
                self.emit(f"bnz r{operand_reg}, {valid_addr_label}")
                exit_code_reg = self.new_register()
                self.emit(f"mov r{exit_code_reg}, 1 # Null Pointer Dereference")
                self.emit(f"call exit, r{exit_code_reg}")
                self.emit(f"{valid_addr_label}:")
                
                self.emit(f"ld r{result_reg}, [r{operand_reg}]")
                
                return_type = operand_type.split("_", 1)[1] if "_" in operand_type else "int"
                return result_reg, return_type
            else:
                zero_reg = self.new_register()
                self.emit(f"mov r{zero_reg}, 0")
                self.emit(f"cmp== r{result_reg}, r{operand_reg}, r{zero_reg}")
                return result_reg, "bool"
                
        return result_reg, "unknown"

    def visit_FunctionCallNode(self, node):
        if node.name == 'print':
            if node.params:
                expr = node.params[0]
                if isinstance(expr, BinaryOperation) and self._contains_string_expr(expr):
                    parts = []
                    self._flatten_concat(expr, parts)
                    for part in parts:
                        self._emit_print_value(part)
                else:
                    self._emit_print_value(expr)

            self.emit("call nl")
            return 0, "null"

        elif node.name == 'scan':
            result_reg = self.new_register()
            self.emit(f"call iget, r{result_reg}")
            return result_reg, "int"

        elif node.name == 'exit':
            code_reg, _ = self.visit(node.params[0])
            self.emit(f"call exit, r{code_reg}")
            return 0, "noreturn"

        regs_to_save = [i for i in range(1, self.next_register)]
        for r in regs_to_save:
            self.emit(f"push r{r}")

        arg_count = 0
        for arg in reversed(node.params):
            arg_reg, _ = self.visit(arg)
            self.emit(f"push r{arg_reg}")
            arg_count += 1
            
        self.emit(f"call {node.name}")
        
        if arg_count > 0:
            pop_reg = self.new_register()
            self.emit(f"mov r{pop_reg}, {arg_count}")
            self.emit(f"add sp, sp, r{pop_reg}")
            
        for r in reversed(regs_to_save):
            self.emit(f"pop r{r}")

        result_reg = self.new_register()
        self.emit(f"mov r{result_reg}, r0")
        
        finfo = self.global_symbol_table.get(node.name)
        return_type = finfo['return_type'] if finfo else "unknown"
        
        return result_reg, return_type

    def visit_MethodCallNode(self, node):
        regs_to_save = [i for i in range(1, self.next_register)]
        for r in regs_to_save:
            self.emit(f"push r{r}")

        arg_count = 0
        for arg in reversed(node.args):
            arg_reg, _ = self.visit(arg)
            self.emit(f"push r{arg_reg}")
            arg_count += 1

        this_ptr_reg, class_name = self.visit(node.object_expr)
        self.emit(f"push r{this_ptr_reg}")
        
        if class_name not in self.class_table:
            self.emit(f"# Error: Attempt to call method on unknown class '{class_name}'")
            return 0, "unknown"
        
        self.emit(f"call {class_name}_{node.method_name}")
        
        pop_count = arg_count + 1
        pop_reg = self.new_register()
        self.emit(f"mov r{pop_reg}, {pop_count}")
        self.emit(f"add sp, sp, r{pop_reg}")
        
        for r in reversed(regs_to_save):
            self.emit(f"pop r{r}")

        result_reg = self.new_register()
        self.emit(f"mov r{result_reg}, r0")
        
        method_info = self.class_table[class_name]['methods'][node.method_name]
        return_type = method_info['return_type']
        
        return result_reg, return_type

    def visit_NewNode(self, node):
        class_info = self.class_table.get(node.class_name)
        if not class_info:
            self.emit(f"# Error: 'new' on unknown class {node.class_name}")
            reg = self.new_register()
            self.emit(f"mov r{reg}, 0")
            return reg, "unknown"
            
        obj_ptr_reg = self.new_register()
        size_reg = self.new_register()
        field_count = len(class_info['fields'])
        self.emit(f"mov r{size_reg}, {field_count}")
        self.emit(f"call mem, r{obj_ptr_reg}, r{size_reg}")
        
        if 'init' in class_info['methods']:
            regs_to_save = [i for i in range(1, self.next_register)]
            for r in regs_to_save:
                self.emit(f"push r{r}")

            arg_count = 0
            for arg in reversed(node.args):
                arg_reg, _ = self.visit(arg)
                self.emit(f"push r{arg_reg}")
                arg_count += 1
            
            self.emit(f"push r{obj_ptr_reg}")
            
            self.emit(f"call {node.class_name}_init")
            
            pop_count = arg_count + 1
            pop_reg = self.new_register()
            self.emit(f"mov r{pop_reg}, {pop_count}")
            self.emit(f"add sp, sp, r{pop_reg}")

            for r in reversed(regs_to_save):
                self.emit(f"pop r{r}")
        
        return obj_ptr_reg, node.class_name

    def visit_FieldAccessNode(self, node):
        obj_ptr_reg, obj_type = self.visit(node.object_expr)
        
        if obj_type not in self.class_table:
            self.emit(f"# Error: Access field on unknown class {obj_type}")
            reg = self.new_register()
            self.emit(f"mov r{reg}, 0")
            return reg, "unknown"

        class_info = self.class_table[obj_type]
        field_info = class_info['fields'][node.field_name]
        offset_reg = self.new_register()
        self.emit(f"mov r{offset_reg}, {field_info['offset']}")
        
        addr_reg = self.new_register()
        self.emit(f"add r{addr_reg}, r{obj_ptr_reg}, r{offset_reg}")
        
        result_reg = self.new_register()
        self.emit(f"ld r{result_reg}, [r{addr_reg}]")
        return result_reg, field_info['var_type']

    def visit_RefNode(self, node):
        addr_reg = self.get_var_addr_reg(node.var_name)
        var_type = "unknown"
        if node.var_name in self.var_map:
            var_type = self.var_map[node.var_name].get('var_type', 'unknown')
        elif node.var_name in self.global_var_map:
             var_type = self.global_var_map[node.var_name].get('var_type', 'unknown')
        return addr_reg, f"ref_{var_type}"

    def visit_ReturnStatementNode(self, node):
        if node.returnVar is not None:
            return_reg, _ = self.visit(node.returnVar)
            self.emit(f"mov r0, r{return_reg}")
        
        func_label = self.current_function.name
        if self.current_class:
            func_label = f"{self.current_class['name']}_{self.current_function.name}"
            
        self.emit(f"br L_{func_label}_return")
        return 0, "null"

    def visit_IfWhileNode(self, node):
        if node.is_while:
            start_label = self.new_label(); end_label = self.new_label()
            self.emit(f"{start_label}:")
            cond_reg, _ = self.visit(node.expr)
            self.emit(f"bz r{cond_reg}, {end_label}")
            self.visit(node.stmt)
            self.emit(f"br {start_label}")
            self.emit(f"{end_label}:")
        else:
            else_label = self.new_label(); end_label = self.new_label()
            cond_reg, _ = self.visit(node.expr)
            self.emit(f"bz r{cond_reg}, {else_label}")
            self.visit(node.stmt)
            self.emit(f"br {end_label}")
            self.emit(f"{else_label}:")
            if node.stmtelse: self.visit(node.stmtelse)
            self.emit(f"{end_label}:")
        return 0, "null"

    def visit_TernaryOperation(self, node):
        else_label = self.new_label(); end_label = self.new_label()
        result_reg = self.new_register()
        
        cond_reg, _ = self.visit(node.condition)
        self.emit(f"bz r{cond_reg}, {else_label}")
        
        true_val_reg, true_type = self.visit(node.body)
        self.emit(f"mov r{result_reg}, r{true_val_reg}")
        self.emit(f"br {end_label}")
        self.emit(f"{else_label}:")
        
        false_val_reg, false_type = self.visit(node.bodyelse)
        self.emit(f"mov r{result_reg}, r{false_val_reg}")
        
        self.emit(f"{end_label}:")
        return result_reg, true_type

    def visit_ForNode(self, node):
        self.visit(node.stmt)
        return 0, "null"

    def visit_ScanNode(self, node):
        result_reg = self.new_register()
        self.emit(f"call iget, r{result_reg}"); return result_reg, "int"

    def visit_PrintNode(self, node):
        value = node.value

        if isinstance(value, BinaryOperation) and self._contains_string_expr(value):
            parts = []
            self._flatten_concat(value, parts)
            for part in parts:
                self._emit_print_value(part)
        else:
            self._emit_print_value(value)

        self.emit("call nl")
        return 0, "null"
        
    def visit_ListNode(self, node):
        size_reg, _ = self.visit(node.size)
        one_reg = self.new_register(); self.emit(f"mov r{one_reg}, 1")
        alloc_size_reg = self.new_register(); self.emit(f"add r{alloc_size_reg}, r{size_reg}, r{one_reg}")
        base_ptr_reg = self.new_register(); self.emit(f"call mem, r{base_ptr_reg}, r{alloc_size_reg}")
        self.emit(f"st [r{base_ptr_reg}], r{size_reg}")
        elem_ptr_reg = self.new_register(); self.emit(f"add r{elem_ptr_reg}, r{base_ptr_reg}, r{one_reg}")
        return elem_ptr_reg, "vector"

    def visit_LengthNode(self, node):
        array_reg, _ = self.visit(node.array)
        result_reg = self.new_register()
        one_reg = self.new_register(); self.emit(f"mov r{one_reg}, 1")
        base_ptr_reg = self.new_register(); self.emit(f"sub r{base_ptr_reg}, r{array_reg}, r{one_reg}")
        self.emit(f"ld r{result_reg}, [r{base_ptr_reg}]");
        return result_reg, "int"

    def visit_VectorAccessNode(self, node):
        array_ptr_reg, _ = self.visit(node.array_name)
        index_reg, _ = self.visit(node.index)
        result_reg = self.new_register()
        self.emit(f"call vget, r{result_reg}, r{array_ptr_reg}, r{index_reg}")
        return result_reg, "int"

    def visit_VectorNode(self, node):
        size = len(node.elements)
        one_reg = self.new_register(); self.emit(f"mov r{one_reg}, 1")
        
        alloc_size_reg = self.new_register(); self.emit(f"mov r{alloc_size_reg}, {size + 1}")
        base_ptr_reg = self.new_register(); self.emit(f"call mem, r{base_ptr_reg}, r{alloc_size_reg}")
        
        size_reg = self.new_register(); self.emit(f"mov r{size_reg}, {size}")
        self.emit(f"st [r{base_ptr_reg}], r{size_reg}")
        
        elem_ptr_reg = self.new_register(); self.emit(f"add r{elem_ptr_reg}, r{base_ptr_reg}, r{one_reg}")
        
        for i, elem in enumerate(node.elements):
            elem_reg, _ = self.visit(elem)
            offset_reg = self.new_register(); self.emit(f"mov r{offset_reg}, {i}")
            temp_addr_reg = self.new_register(); self.emit(f"add r{temp_addr_reg}, r{elem_ptr_reg}, r{offset_reg}")
            self.emit(f"st [r{temp_addr_reg}], r{elem_reg}")
            
        return elem_ptr_reg, "vector"

    def visit_LambdaNode(self, node):
        self.emit("# Error: Lambda visited directly")
        return 0, "function"

    def visit_MapNode(self, node):
        lambda_node = node.lambda_node
        list_expr_node = node.list_expr
        
        element_types = []
        if isinstance(list_expr_node, str):
            if list_expr_node in self.var_map:
                element_types = self.var_map[list_expr_node].get('element_types', [])
            elif list_expr_node in self.global_symbol_table:
                element_types = self.global_symbol_table[list_expr_node].get('element_types', [])

        if not element_types:
            element_types = ['int']

        non_unknown_types = [t for t in element_types if t != 'unknown']

        unique_types = set(non_unknown_types)
        if not unique_types:
            unique_types = {'int'}

        type_label_map = {}
        
        old_var_map = self.var_map
        old_fp_offset = self.fp_offset
        old_func = self.current_function
        
        for t in unique_types:
            lambda_func_name = self.new_label() + f"_lambda_{t}"
            type_label_map[t] = lambda_func_name
            lambda_end_label = self.new_label() + f"_end_{t}"

            self.emit(f"br {lambda_end_label}")
            
            self.var_map = {}
            self.fp_offset = 1
            self.current_function = lambda_node
            
            self.emit(f"proc {lambda_func_name}")
            self.emit("push fp")
            self.emit("mov fp, sp")
            
            self.var_map[lambda_node.param] = {
                'scope': 'param',
                'offset': 2,
                'var_type': t
            }
            
            body_reg, _ = self.visit(lambda_node.body)
            
            self.emit(f"mov r0, r{body_reg}") 
            self.emit("pop fp")
            self.emit("ret")
            
            self.emit(f"{lambda_end_label}:")

        self.var_map = old_var_map
        self.fp_offset = old_fp_offset
        self.current_function = old_func

        list_ptr_reg, _ = self.visit(list_expr_node)
        one_reg = self.new_register()
        self.emit(f"mov r{one_reg}, 1")

        size_reg = self.new_register()
        base_ptr_reg = self.new_register()
        self.emit(f"sub r{base_ptr_reg}, r{list_ptr_reg}, r{one_reg}")
        self.emit(f"ld r{size_reg}, [r{base_ptr_reg}]")

        alloc_size_reg = self.new_register()
        self.emit(f"add r{alloc_size_reg}, r{size_reg}, r{one_reg}")
        new_list_base_ptr = self.new_register()
        self.emit(f"call mem, r{new_list_base_ptr}, r{alloc_size_reg}")
        self.emit(f"st [r{new_list_base_ptr}], r{size_reg}") 
        new_list_ptr_reg = self.new_register()
        self.emit(f"add r{new_list_ptr_reg}, r{new_list_base_ptr}, r{one_reg}")

        i_reg = self.new_register()
        self.emit(f"mov r{i_reg}, 0")
        loop_start = self.new_label()
        loop_end = self.new_label()
        
        self.emit(f"{loop_start}:")
        cond_reg = self.new_register()
        self.emit(f"cmp>= r{cond_reg}, r{i_reg}, r{size_reg}")
        self.emit(f"bnz r{cond_reg}, {loop_end}")

        elem_reg = self.new_register()
        self.emit(f"call vget, r{elem_reg}, r{list_ptr_reg}, r{i_reg}")
        
        regs_to_save = [r for r in range(1, self.next_register)]
        for r in regs_to_save:
            self.emit(f"push r{r}")

        self.emit(f"push r{elem_reg}")
        
        result_reg = self.new_register()
        dispatch_end = self.new_label()

        if len(set(non_unknown_types)) <= 1:
            default_type = next(iter(unique_types))
            target_func = type_label_map[default_type]
            self.emit(f"call {target_func}")
            self.emit(f"mov r{result_reg}, r0")
        else:
            for idx, t in enumerate(element_types):
                if t not in type_label_map:
                    continue
                
                target_func = type_label_map[t]
                next_check = self.new_label()
                
                idx_check_reg = self.new_register()
                self.emit(f"mov r{idx_check_reg}, {idx}")
                cmp_idx_reg = self.new_register()
                self.emit(f"cmp!= r{cmp_idx_reg}, r{i_reg}, r{idx_check_reg}")
                self.emit(f"bnz r{cmp_idx_reg}, {next_check}")
                
                self.emit(f"call {target_func}")
                self.emit(f"mov r{result_reg}, r0")
                self.emit(f"br {dispatch_end}")
                
                self.emit(f"{next_check}:")

        self.emit(f"{dispatch_end}:")

        pop_reg = self.new_register()
        self.emit(f"mov r{pop_reg}, 1")
        self.emit(f"add sp, sp, r{pop_reg}")

        for r in reversed(regs_to_save):
            self.emit(f"pop r{r}")

        new_addr_reg = self.new_register()
        self.emit(f"add r{new_addr_reg}, r{new_list_ptr_reg}, r{i_reg}")
        self.emit(f"st [r{new_addr_reg}], r{result_reg}")

        self.emit(f"add r{i_reg}, r{i_reg}, 1")
        self.emit(f"br {loop_start}")
        
        self.emit(f"{loop_end}:")
        
        return new_list_ptr_reg, "vector"

    def visit_Number(self, num):
        reg = self.new_register()
        self.emit(f"mov r{reg}, {num}")
        return reg, "int"

    def visit_Identifier(self, name):
        if name == 'true':
            reg = self.new_register(); self.emit(f"mov r{reg}, 1")
            return reg, "bool"
        if name == 'false':
            reg = self.new_register(); self.emit(f"mov r{reg}, 0")
            return reg, "bool"
        if name == 'null':
            reg = self.new_register(); self.emit(f"mov r{reg}, 0")
            return reg, "null"
        
        if name.startswith('"') or name.startswith("'") or name.startswith('"""'):
            reg = self.new_register()
            self.emit(f"sload r{reg}, {name}") 
            return reg, "string"

        addr_reg = self.get_var_addr_reg(name)
        val_reg = self.new_register()
        self.emit(f"ld r{val_reg}, [r{addr_reg}]")
        
        var_type = "unknown"
        if name in self.var_map:
            var_type = self.var_map[name].get('var_type', 'unknown')
        elif name in self.global_var_map:
            var_type = self.global_var_map[name].get('var_type', 'unknown')
            
        return val_reg, var_type

    def generate(self, ast):
        self.visit(ast)
        return "\n".join(self.code)