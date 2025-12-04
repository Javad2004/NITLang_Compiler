class ASTNode:
    pass

class ProgramNode(ASTNode):
    def __init__(self,children=None):
        self.children = children or []

class FunctionNode(ASTNode):
    def __init__(self, name, params, return_type, body):
        self.name = name
        self.params = params
        self.return_type = return_type
        self.body = body
        self.parent_class = None

class ReturnStatementNode(ASTNode):
    def __init__(self, returnVar=None):
        self.returnVar = returnVar

class FunctionCallNode(ASTNode):
    def __init__(self, name, params,returnVar=None):
        self.name = name
        self.params = params

class BinaryOperation(ASTNode):
    def __init__(self,left,op,right):
        self.left = left
        self.right = right
        self.op = op

class SingleOperation(ASTNode):
    def __init__(self,op,right):
        self.right = right
        self.op = op

class VariableDeclarationNode(ASTNode):
    def __init__(self, name, var_type, value=None , size=None):
        self.name = name
        self.var_type = var_type
        self.value = value
        self.initialized = value is not None
        self.size = size

class AssignmentNode(ASTNode):
    def __init__(self, var, value):
        self.var = var
        self.value = value

class IfWhileNode(ASTNode):
    def __init__(self, expr, stmt ,stmtelse=None , is_while=False):
        self.expr = expr
        self.stmt = stmt
        self.stmtelse = stmtelse
        self.is_while = is_while

class TernaryOperation(ASTNode):
        def __init__(self, condition, body ,bodyelse):
            self.condition = condition
            self.body = body
            self.bodyelse = bodyelse

class ForNode(ASTNode):
    def __init__(self, var,exp1 , exp2, stmt ):
        self.var = var
        self.exp1 = exp1
        self.exp2 = exp2
        self.stmt = stmt

class VectorNode(ASTNode):
    def __init__(self, elements):
        self.elements = elements

class VectorAccessNode(ASTNode):
    def __init__(self, array_name, index):
        self.array_name = array_name
        self.index = index

class BuiltinNode(ASTNode):
    def __init__(self, name, return_type):
        self.name = name
        self.return_type = return_type

class ScanNode(BuiltinNode):
    def __init__(self):
        super().__init__("scan", "int")

class PrintNode(BuiltinNode):
    def __init__(self, value):
        super().__init__("print", "null")
        self.value = value

class ListNode(BuiltinNode):
    def __init__(self, size_expr):
        super().__init__("list", "vector")
        self.size = size_expr

class LengthNode(BuiltinNode):
    def __init__(self, array_expr):
        super().__init__("length", "int") 
        self.array = array_expr

class ExitNode(BuiltinNode):
    def __init__(self, code_expr):
        super().__init__("exit", "noreturn")
        self.code = code_expr

class RefNode(ASTNode):
    """Represents 'ref x' [cite: 88]"""
    def __init__(self, var_name):
        self.var_name = var_name

class RefAssignmentNode(ASTNode):
    """Represents 'x := 5' [cite: 89, 91]"""
    def __init__(self, ref_var, value):
        self.ref_var = ref_var
        self.value = value

class ClassNode(ASTNode):
    """Represents 'class Point { ... }' [cite: 70, 98]"""
    def __init__(self, name, fields, methods):
        self.name = name
        self.fields = fields
        self.methods = methods
        for m in self.methods:
            m.parent_class = self.name
        for f in self.fields:
            f.parent_class = self.name

class NewNode(ASTNode):
    """Represents 'new Point(2, 3)' [cite: 106, 127]"""
    def __init__(self, class_name, args):
        self.class_name = class_name
        self.args = args

class MethodCallNode(ASTNode):
    """Represents 'p.move(1, 1)' [cite: 106]"""
    def __init__(self, object_expr, method_name, args):
        self.object_expr = object_expr
        self.method_name = method_name
        self.args = args

class FieldAccessNode(ASTNode):
    """Represents 'p.x'"""
    def __init__(self, object_expr, field_name):
        self.object_expr = object_expr
        self.field_name = field_name

class LambdaNode(ASTNode):
    """Represents 'lambda x -> x*2' [cite: 109, 128]"""
    def __init__(self, param, body):
        self.param = param
        self.body = body

class MapNode(ASTNode):
    """Represents 'map(lambda..., list)' [cite: 109, 129]"""
    def __init__(self, lambda_node, list_expr):
        self.lambda_node = lambda_node
        self.list_expr = list_expr