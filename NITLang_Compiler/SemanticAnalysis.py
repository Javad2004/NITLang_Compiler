from AST import *
import copy

class SemanticChecker:
    def __init__(self):
        self.symbol_table = {}
        self.class_table = {} 
        self.errors = []
        self.current_function = None
        self.current_class = None
        self.global_symbol_table = self.symbol_table
        self.function_has_return = False

    def error(self, msg):
        prefix = ""
        if self.current_class:
            prefix = f"in class '{self.current_class.name}': "
        if self.current_function:
            prefix += f"in function '{self.current_function.name}': "
        self.errors.append(f"Error {prefix}{msg}")

    # -------- CLASS REGISTRATION --------
    def register_class(self, node):
        if node.name in self.class_table:
            self.error(f"Class '{node.name}' is already defined.")
            return
        
        class_info = {
            "name": node.name,
            "fields": {},
            "methods": {}
        }
        
        field_offset = 0
        for field in node.fields:
            if field.name in class_info['fields']:
                self.error(f"Field '{field.name}' already defined in class '{node.name}'")
            class_info['fields'][field.name] = {
                "var_type": field.var_type,
                "offset": field_offset
            }
            field_offset += 1
        
        for method in node.methods:
            if method.name in class_info['methods']:
                self.error(f"Method '{method.name}' already defined in class '{node.name}'")
            
            class_info['methods'][method.name] = {
                "return_type": method.return_type,
                "params": method.params,
                "node": method 
            }
        
        self.class_table[node.name] = class_info
        return

    # -------- FUNCTION REGISTRATION --------
    def register_function(self, node):
        func_name = node.name
        if self.current_class:
            return
            
        if func_name in self.symbol_table:
            self.error(f"Function '{func_name}' is already defined.")
            return
        self.symbol_table[func_name] = {
            "kind": "function",
            "params": node.params,
            "return_type": node.return_type,
            "node": node 
        }
        return

    # -------------- UTILITY METHODS ------------------
    def _is_bool_literal(self, v):
        return isinstance(v, str) and v.lower() in ('true', 'false')
        
    def _is_string_literal(self, v):
        return isinstance(v, str) and (
            (v.startswith('"') and v.endswith('"')) or
            (v.startswith("'") and v.endswith("'"))
        )
        
    def _is_mstring_literal(self, v):
        return isinstance(v, str) and (v.startswith('"""') and v.endswith('"""'))

    def _get_vector_size(self, value):
        if value is None:
            return None
        if hasattr(value, 'elements'):
            return len(value.elements)
        if hasattr(value, 'size'):
            return self._get_constant_int(value.size)
        return None
        
    def _get_element_types(self, value):
        if hasattr(value, 'elements'):
            return [self._get_type(elem) for elem in value.elements]
        return []

    def _is_int_literal(self, v):
        return isinstance(v, int)
        
    def _deduce_literal_type(self, v):
        if self._is_int_literal(v): return "int"
        elif self._is_bool_literal(v): return "bool"
        elif self._is_mstring_literal(v): return "string"
        elif self._is_string_literal(v): return "string"
        elif isinstance(v, list): return "vector"
        elif v == 'null': return "null"
        else: return "unknown"
        
    def _get_constant_int(self, expr):
        if isinstance(expr, int): return expr
        if isinstance(expr, str):
            varinfo = self.symbol_table.get(expr)
            if varinfo and varinfo.get('var_type') == 'int' and varinfo.get('value') is not None:
                return varinfo['value']
        if isinstance(expr, BinaryOperation):
            left = self._get_constant_int(expr.left)
            right = self._get_constant_int(expr.right)
            if left is None or right is None: return None
            op = expr.op
            if op == '+': return left + right
            if op == '-': return left - right
            if op == '*': return left * right
            if op == '/': 
                if right == 0: return None
                return left // right
        return None

    def _get_type(self, expr):
        if isinstance(expr, ASTNode):
            if isinstance(expr, BinaryOperation):
                left = self._get_type(expr.left)
                right = self._get_type(expr.right)
                if expr.op in ['+', '-', '*', '/']:
                    if left == 'int' and right == 'int': return 'int'
                elif expr.op in ['&&', '||']:
                    if left == 'bool' and right == 'bool': return 'bool'
                elif expr.op in ['==', '!=', '<', '<=', '>', '>=']:
                    if left in ('int', 'bool') and right in ('int', 'bool'):
                        return 'bool'
                return 'unknown'
            elif isinstance(expr, SingleOperation):
                sub_type = self._get_type(expr.right)
                if expr.op == '!' and sub_type == 'bool': return 'bool'
                elif expr.op in ['+', '-'] and sub_type == 'int': return 'int'
                return 'unknown'
            elif isinstance(expr, VariableDeclarationNode):
                return expr.var_type
            elif isinstance(expr, AssignmentNode):
                return self._get_type(expr.value)
            elif isinstance(expr, VectorNode):
                return "vector"
            elif isinstance(expr, VectorAccessNode):
                arrname = expr.array_name
                if isinstance(arrname, VectorNode):
                    return "int"
                
                arrinfo = self.symbol_table.get(arrname)
                if arrinfo and arrinfo['var_type'] == "vector":
                    if arrinfo.get('kind') == 'param': return 'int'
                    idx = self._get_constant_int(expr.index)
                    if 'element_types' in arrinfo and isinstance(idx, int):
                        if 0 <= idx < len(arrinfo['element_types']):
                            return arrinfo['element_types'][idx]
                    return 'int' 
                return 'unknown' 
            elif isinstance(expr, ListNode):
                return "vector"
            elif isinstance(expr, FunctionCallNode):
                if expr.name in ['print', 'exit']: return 'null'
                if expr.name in ['scan', 'length']: return 'int'
                
                finfo = self.symbol_table.get(expr.name)
                if finfo: return finfo['return_type']
            elif isinstance(expr, LengthNode): return 'int'
            elif isinstance(expr, ScanNode): return 'int'
            elif isinstance(expr, PrintNode): return 'null'
            elif isinstance(expr, ExitNode): return 'noreturn'
            elif isinstance(expr, TernaryOperation):
                body_type = self._get_type(expr.body)
                bodyelse_type = self._get_type(expr.bodyelse)
                return body_type if body_type == bodyelse_type else 'unknown'
            elif isinstance(expr, RefNode):
                return "ref"
            elif isinstance(expr, NewNode):
                if expr.class_name in self.class_table:
                    return expr.class_name
                self.error(f"Unknown class '{expr.class_name}'")
                return "unknown"
            elif isinstance(expr, FieldAccessNode):
                obj_type = self._get_type(expr.object_expr)
                if obj_type in self.class_table:
                    class_info = self.class_table[obj_type]
                    if expr.field_name in class_info['fields']:
                        return class_info['fields'][expr.field_name]['var_type']
                    self.error(f"Class '{obj_type}' has no field '{expr.field_name}'")
                return "unknown"
            elif isinstance(expr, MethodCallNode):
                obj_type = self._get_type(expr.object_expr)
                if obj_type in self.class_table:
                    class_info = self.class_table[obj_type]
                    if expr.method_name in class_info['methods']:
                        return class_info['methods'][expr.method_name]['return_type']
                    self.error(f"Class '{obj_type}' has no method '{expr.method_name}'")
                return "unknown"
            elif isinstance(expr, LambdaNode):
                return "function"
            elif isinstance(expr, MapNode):
                return "vector"
            
        if isinstance(expr, str):
            lit_type = self._deduce_literal_type(expr)
            if lit_type != "unknown":
                return lit_type
                
            if expr in self.symbol_table:
                return self.symbol_table[expr]['var_type']
            
            return "unknown"
            
        if isinstance(expr, int):
            return "int"
            
        return "unknown"
    
    def _check_variable_initialized(self, name, context):
        if self._is_bool_literal(name) or \
           self._is_string_literal(name) or \
           self._is_mstring_literal(name) or \
           name == 'null':
            return

        if name in self.symbol_table:
            varinfo = self.symbol_table[name]
            if varinfo['kind'] in ['var', 'loopvar', 'global_var'] and not varinfo.get('initialized', False):
                self.error(f"Variable '{name}' used without being initialized in {context}")
        else:
            self.error(f"Variable '{name}' not declared in {context}")

    # ---------------------------------------------------

    def visit(self, node):
        if node is None:
            return

        if isinstance(node, int):
            return
        
        if isinstance(node, str):
            self._check_variable_initialized(node, "expression")
            return

        if isinstance(node, BinaryOperation):
            self.visit(node.left)
            self.visit(node.right)
            return
        
        if isinstance(node, SingleOperation):
            self.visit(node.right)
            return

        # -------- PROGRAM --------
        if isinstance(node, ProgramNode):
            for child in node.children:
                self.visit(child)
            return

        # -------- CLASS DECLARATION --------
        if isinstance(node, ClassNode):
            self.current_class = node
            class_info = self.class_table[node.name]
            for method_name, method_info in class_info['methods'].items():
                self.visit(method_info['node'])
            self.current_class = None
            return

        # -------- FUNCTION DEF --------
        if isinstance(node, FunctionNode):
            prev_vars = copy.deepcopy(self.symbol_table)
            self.current_function = node
            
            self.function_has_return = False
            
            if self.current_class:
                self.symbol_table['this'] = {
                    "kind": "param",
                    "var_type": self.current_class.name,
                    "initialized": True
                }
                class_info = self.class_table[self.current_class.name]
                for fname, finfo in class_info['fields'].items():
                    if fname in self.symbol_table:
                        self.error(f"Field '{fname}' conflicts with a parameter.")
                    self.symbol_table[fname] = {
                        "kind": "field",
                        "var_type": finfo['var_type'],
                        "initialized": True
                    }

            for pname, ptype in node.params:
                if pname in self.symbol_table:
                    self.error(f"Parameter '{pname}' already defined.")
                self.symbol_table[pname] = {
                    "kind": "param",
                    "var_type": ptype,
                    "initialized": True
                }
                if ptype == 'vector':
                    self.symbol_table[pname]['size'] = None
                
            self.visit(node.body)
            
            if not self.function_has_return and self.current_function.return_type != "null":
                self.error(f"Function '{self.current_function.name}' should return '{self.current_function.return_type}', but implicitly returned 'null'")

            self.symbol_table = prev_vars
            self.current_function = None
            return

        # -------- VARIABLE DECL --------
        if isinstance(node, VariableDeclarationNode):
            
            if node.name in self.symbol_table and self.symbol_table[node.name]['kind'] != 'field':
                
                existing_kind = self.symbol_table[node.name]['kind']
                
                if self.current_function is None:
                    self.error(f"Variable '{node.name}' already defined in this scope.")
                    return

                if existing_kind == 'param' or existing_kind == 'var':
                     self.error(f"Variable '{node.name}' already defined in this scope.")
                     return
            
            initialized = node.value is not None
            var_type = node.var_type
            value = node.value
            valtype = None
            
            if initialized:
                self.visit(node.value) 
                valtype = self._get_type(node.value)
            
            if var_type is None:
                if not initialized:
                    self.error(f"Cannot declare '{node.name}' without type or initial value.")
                    return
                var_type = valtype
                node.var_type = var_type
            
            elif initialized:
                if isinstance(node.value, RefNode):
                    var_type = "ref"
                    self.symbol_table[node.name] = { "points_to_type": valtype }
                
                if var_type == "vector" and valtype != "vector":
                    self.error(f"Declared '{node.name}' as vector but assigned '{valtype}'")
                elif var_type != valtype and valtype != "unknown":
                    self.error(f"Variable '{node.name}': assigned value of wrong type (expected {var_type}, got {valtype})")

            kind = "var" 
            if self.current_function is None:
                kind = "global_var" 
            
            if var_type == 'vector':
                self.symbol_table[node.name] = {
                    "kind": kind, "var_type": var_type, "initialized": initialized,
                    "size": self._get_vector_size(value),
                    "element_types": self._get_element_types(value)
                }
            else:
                value_to_store = None
                if isinstance(node.value, (int, str, bool)):
                    value_to_store = node.value
                
                entry = {
                    "kind": kind, "var_type": var_type,
                    "initialized": initialized, "value": value_to_store
                }
                if var_type == "ref":
                    ref_type = self._get_type(node.value.var_name)
                    entry['points_to_type'] = ref_type

                self.symbol_table[node.name] = entry
            return

        # -------- ASSIGNMENT (var = value) --------
        if isinstance(node, AssignmentNode):
            self.visit(node.value)
            
            if isinstance(node.var, FieldAccessNode):
                self.visit(node.var.object_expr)
                obj_expr = node.var.object_expr
                
                if isinstance(obj_expr, str) and obj_expr == 'this':
                    if not self.current_class:
                        self.error("'this' can only be used inside a method.")
                        return
                    
                    obj_type = self.current_class.name
                    field_name = node.var.field_name
                    class_info = self.class_table.get(obj_type)
                    
                    if not class_info or field_name not in class_info['fields']:
                        self.error(f"No field '{field_name}' in class '{obj_type}'")
                        return
                        
                    expected_type = class_info['fields'][field_name]['var_type']
                    val_type = self._get_type(node.value)
                    
                    if expected_type != val_type and val_type != "unknown":
                        self.error(f"Type error assigning to field '{field_name}' (expected {expected_type}, got {val_type})")
                else:
                    self.error("Fields are private and cannot be modified from outside the class.")
                return

            varname_or_node = node.var
            varinfo = None
            varname = ""
            is_vec_access = isinstance(varname_or_node, VectorAccessNode)

            if is_vec_access:
                self.visit(varname_or_node)
                varname = varname_or_node.array_name
                if isinstance(varname, VectorNode):
                    self.error("Cannot assign to element of a vector literal.")
                    return
                varinfo = self.symbol_table.get(varname)
            else:
                varname = varname_or_node 
                varinfo = self.symbol_table.get(varname)

            if not varinfo:
                self.error(f"Assign to undeclared variable '{varname}'")
                return
            
            exprtype = self._get_type(node.value)
            vtype = varinfo['var_type']
            
            if vtype != exprtype and not is_vec_access and exprtype != "unknown":
                self.error(f"Type error in assignment to '{varname}' (expected {vtype}, got {exprtype})")
            elif is_vec_access and vtype != "vector":
                 self.error(f"Cannot index variable '{varname}' which is not a vector.")
            else:
                varinfo['initialized'] = True
            
            return

        # -------- REF ASSIGNMENT (var := value) --------
        if isinstance(node, RefAssignmentNode):
            self.visit(node.value)
            varname = node.ref_var
            
            if isinstance(varname, ASTNode):
                self.error(f"Cannot use ':=' on complex expression.")
                return

            varinfo = self.symbol_table.get(varname)
            
            if not varinfo:
                self.error(f"Assign to undeclared variable '{varname}'")
                return
            
            if varinfo['var_type'] != 'ref':
                self.error(f"Cannot use ':=' on non-reference variable '{varname}'")
                return
                
            expected_type = varinfo.get('points_to_type', 'unknown')
            val_type = self._get_type(node.value)
            
            if expected_type != val_type and val_type != "unknown":
                self.error(f"Type error in ref assignment to '{varname}' (expected {expected_type}, got {val_type})")
            return

        # -------- RETURN --------
        if isinstance(node, ReturnStatementNode):
            if not self.current_function:
                self.error("Return used outside of function")
                return
                
            self.function_has_return = True
                
            expected_type = self.current_function.return_type
            rv_type = "null"
            
            if node.returnVar is not None:
                self.visit(node.returnVar)
                rv_type = self._get_type(node.returnVar)
            
            if expected_type != rv_type and rv_type != "unknown":
                self.error(
                    f"Function '{self.current_function.name}' should return '{expected_type}', but returned '{rv_type}'"
                )
            return

        # -------- FUNCTION CALL --------
        if isinstance(node, FunctionCallNode):
            if node.name in ['print', 'scan', 'list', 'length', 'exit']:
                for arg in node.params: self.visit(arg)
                return
                
            finfo = self.symbol_table.get(node.name)
            if not finfo or finfo.get('kind') != 'function':
                self.error(f"Call to undefined function '{node.name}'")
                return

            expected_params = finfo['params']
            if len(expected_params) != len(node.params):
                self.error(f"Function '{node.name}' expects {len(expected_params)} arguments, got {len(node.params)}")
                return
            for i, ((pname, expt), arg) in enumerate(zip(expected_params, node.params)):
                self.visit(arg) 
                argtype = self._get_type(arg)
                if argtype != expt and argtype != "unknown":
                    self.error(f"Function '{node.name}' argument {i+1} type mismatch: expected {expt}, got {argtype}")
                if isinstance(arg, str):
                    self._check_variable_initialized(arg, f"function call to '{node.name}'")
            return

        # -------- METHOD CALL --------
        if isinstance(node, MethodCallNode):
            self.visit(node.object_expr)
            obj_type = self._get_type(node.object_expr)
            if obj_type not in self.class_table:
                self.error(f"Cannot call method '{node.method_name}' on non-class type '{obj_type}'")
                return
                
            class_info = self.class_table[obj_type]
            method_info = class_info['methods'].get(node.method_name)
            
            if not method_info:
                self.error(f"Class '{obj_type}' has no method '{node.method_name}'")
                return
            
            expected_params = method_info['params']
            if len(expected_params) != len(node.args):
                self.error(f"Method '{node.method_name}' expects {len(expected_params)} arguments, got {len(node.args)}")
                return
                
            for i, ((pname, expt), arg) in enumerate(zip(expected_params, node.args)):
                self.visit(arg)
                argtype = self._get_type(arg)
                if argtype != expt and argtype != "unknown":
                    self.error(f"Method '{node.method_name}' argument {i+1} type mismatch: expected {expt}, got {argtype}")
            return

        # -------- NEW OBJECT --------
        if isinstance(node, NewNode):
            if node.class_name not in self.class_table:
                self.error(f"Cannot 'new' undefined class '{node.class_name}'")
                return
            
            for arg in node.args: self.visit(arg)
            
            class_info = self.class_table[node.class_name]
            constructor = class_info['methods'].get('init')
            
            if constructor:
                expected_params = constructor['params']
                if len(expected_params) != len(node.args):
                    self.error(f"Constructor 'init' for class '{node.class_name}' expects {len(expected_params)} arguments, got {len(node.args)}")
                
                for i, ((pname, expt), arg) in enumerate(zip(expected_params, node.args)):
                    argtype = self._get_type(arg)
                    if argtype != expt and argtype != "unknown":
                        self.error(f"Constructor 'init' argument {i+1} type mismatch: expected {expt}, got {argtype}")
            elif len(node.args) > 0:
                self.error(f"Class '{node.class_name}' has no 'init' constructor but arguments were provided.")
            return

        # -------- FIELD ACCESS --------
        if isinstance(node, FieldAccessNode):
            self.visit(node.object_expr)
            if isinstance(node.object_expr, str) and node.object_expr == 'this':
                if not self.current_class:
                    self.error("'this' can only be used inside a method.")
                    return
            else:
                self.error("Fields are private and cannot be accessed from outside the class.")
            return

        # -------- IF / WHILE / FOR --------
        if isinstance(node, IfWhileNode):
            self.visit(node.expr)
            cond_type = self._get_type(node.expr)
            if cond_type != 'bool': self.error('Condition in if/while must be bool')
            
            self.visit(node.stmt)
            if node.stmtelse: self.visit(node.stmtelse)
            return
            
        if isinstance(node, ForNode):
            self.visit(node.exp1); self.visit(node.exp2)
            start_type = self._get_type(node.exp1); end_type = self._get_type(node.exp2)
            if start_type != 'int': self.error("For loop start expression must be integer")
            if end_type != 'int': self.error("For loop end expression must be integer")
            
            prev = copy.deepcopy(self.symbol_table)
            self.symbol_table[node.var] = {"kind": "loopvar", "var_type": "int", "initialized": True}
            self.visit(node.stmt)
            self.symbol_table = prev
            return

        # -------- VECTOR --------
        if isinstance(node, VectorNode):
            for elem in node.elements: self.visit(elem)
            return
            
        if isinstance(node, VectorAccessNode):
            self.visit(node.index)
            arrname = node.array_name
            
            if isinstance(arrname, VectorNode):
                self.visit(arrname)
                return
                
            arrinfo = self.symbol_table.get(arrname)
            if not arrinfo or arrinfo['var_type'] != "vector":
                self.error(f"Cannot index '{arrname}': not a vector"); return
            
            if not arrinfo.get('initialized', False):
                self.error(f"Vector '{arrname}' indexing before initialize"); return 
            
            index_type = self._get_type(node.index)
            if index_type != 'int':
                self.error(f"Vector index must be integer, got {index_type}"); return

            if arrinfo.get('size') is not None:
                idx_val = self._get_constant_int(node.index)
                if idx_val is not None:
                    if idx_val < 0 or idx_val >= arrinfo['size']:
                        self.error(f"Index {idx_val} out of bounds for vector '{arrname}' (size {arrinfo['size']})")
            return
        
        # -------- BUILTINS --------
        if isinstance(node, ScanNode): return
        if isinstance(node, PrintNode): self.visit(node.value); return
        if isinstance(node, ListNode):
            self.visit(node.size)
            size_type = self._get_type(node.size)
            if size_type != 'int': self.error("List() argument must be int")
            return
        if isinstance(node, LengthNode):
            self.visit(node.array)
            arr_type = self._get_type(node.array)
            if not arr_type == 'vector': self.error("Length() argument must be a vector, not " + arr_type)
            return
        if isinstance(node, ExitNode):
            self.visit(node.code)
            code_type = self._get_type(node.code)
            if code_type != 'int': self.error("Exit code must be an integer")
            return
            
        # -------- TERNARY --------
        if isinstance(node, TernaryOperation):
            self.visit(node.condition); self.visit(node.body); self.visit(node.bodyelse)
            cond_type = self._get_type(node.condition)
            if cond_type != "bool": self.error("Ternary condition must be bool")
            left_type = self._get_type(node.body); right_type = self._get_type(node.bodyelse)
            if left_type != right_type and "unknown" not in (left_type, right_type):
                self.error(f"Ternary branches must have the same type but got '{left_type}' and '{right_type}'")
            return

        if isinstance(node, LambdaNode):
            prev = copy.deepcopy(self.symbol_table)
            self.symbol_table[node.param] = {"kind": "param", "var_type": "int", "initialized": True}
            self.visit(node.body)
            self.symbol_table = prev
            return

        if isinstance(node, MapNode):
            self.visit(node.lambda_node)
            self.visit(node.list_expr)
            
            func_type = self._get_type(node.lambda_node)
            if func_type != "function":
                self.error(f"Argument 1 for 'map' must be a lambda, got {func_type}")
                
            list_type = self._get_type(node.list_expr)
            if list_type != "vector":
                self.error(f"Argument 2 for 'map' must be a vector, got {list_type}")
            return

        # -------- DEFAULT: traverse children if any --------
        if not isinstance(node, (int, str)):
            for field in getattr(node, '__dict__', {}):
                child = getattr(node, field)
                if isinstance(child, ASTNode):
                    self.visit(child)
                elif isinstance(child, list):
                    for elem in child:
                        if isinstance(elem, ASTNode):
                            self.visit(elem)

    def check(self, ast):
        if isinstance(ast, ProgramNode):
            for child in ast.children:
                if isinstance(child, ClassNode):
                    self.register_class(child)
            
            for child in ast.children:
                if isinstance(child, FunctionNode):
                    self.register_function(child)
            
            for child in ast.children:
                self.visit(child)
        elif ast:
             self.visit(ast)
             
        return self.errors