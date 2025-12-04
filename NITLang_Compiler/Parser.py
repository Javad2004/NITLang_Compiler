import ply.yacc as yacc
from Tokenizer import tokens
from AST import *
from SemanticAnalysis import *
from CodeGenerator import CodeGenerator


precedence = (
    ('right', 'EQ', 'ASSIGN'),
    ('left', 'OR'),
    ('left', 'AND'),
    ('left', 'EQUAL', 'NEQUAL'),
    ('nonassoc', 'LESS_THAN', 'GREATER_THAN', 'GEQUAL', 'LEQUAL'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
    ('right', 'EXCLAMATION', 'UMINUS', 'REF'),
    ('right', 'ARROW'),
    ('left', 'LPAREN', 'RPAREN', 'LSQUAREBR', 'RSQUAREBR', 'DOT'),
    ('right', 'TERNARY'),
)

def p_prog(p):
    '''prog : stmt_list'''
    p[0] = ProgramNode(p[1])

def p_stmt_list(p):
    '''stmt_list : stmt stmt_list
                 | empty'''
    if len(p) == 3:
        p[0] = [p[1]] + p[2]
    else:
        p[0] = []

def p_block(p):
    '''block : LCURLYEBR stmt_list RCURLYEBR'''
    p[0] = ProgramNode(p[2])

def p_class_decl(p):
    '''class_decl : CLASS ID LCURLYEBR field_list method_list RCURLYEBR'''
    p[0] = ClassNode(p[2], p[4], p[5])

def p_field_list(p):
    '''field_list : let_decl SEMI_COLON field_list
                  | empty'''
    if len(p) == 4:
        p[0] = [p[1]] + p[3]
    else:
        p[0] = []

def p_method_list(p):
    '''method_list : func method_list
                   | empty'''
    if len(p) == 3:
        p[0] = [p[1]] + p[2]
    else:
        p[0] = []

def p_func(p):
    '''func : FUNC ID LPAREN param_list RPAREN LESS_THAN type GREATER_THAN block'''
    p[0] = FunctionNode(p[2], p[4], p[7], p[9])

def p_param_list(p):
    '''param_list : param COMMA param_list
                  | param
                  | empty'''
    if len(p) == 4:
        p[0] = [p[1]] + p[3]
    elif len(p) == 2:
        p[0] = [p[1]] if p[1] else []
    else:
        p[0] = []

def p_param(p):
    '''param : ID COLON type'''
    p[0] = (p[1], p[3]) 

def p_stmt(p):
    '''stmt : expr SEMI_COLON
            | let_decl SEMI_COLON
            | func
            | class_decl
            | if_stmt
            | while_stmt
            | block
            | RETURN expr SEMI_COLON
            | RETURN SEMI_COLON'''
    
    if len(p) == 4:
        p[0] = ReturnStatementNode(p[2])
    elif len(p) == 3:
        if p[1] == 'return':
            p[0] = ReturnStatementNode(None)
        else:
            p[0] = p[1] 
    else:
        p[0] = p[1]

def p_if_stmt(p):
    '''if_stmt : IF expr THEN block
               | IF expr THEN block ELSE block'''
    if len(p) == 5:
        p[0] = IfWhileNode(p[2], p[4], is_while=False)
    else:
        p[0] = IfWhileNode(p[2], p[4], p[6], is_while=False)

def p_while_stmt(p):
    '''while_stmt : WHILE expr DO block'''
    p[0] = IfWhileNode(p[2], p[4], is_while=True)

def p_let_decl(p):
    '''let_decl : LET ID COLON type
                | LET ID COLON type EQ expr
                | LET ID EQ expr'''
    if len(p) == 5 and p[3] == ':':
        p[0] = VariableDeclarationNode(p[2], p[4])
    elif len(p) == 7:
        p[0] = VariableDeclarationNode(p[2], p[4], p[6])
    elif len(p) == 5 and p[3] == '=':
        p[0] = VariableDeclarationNode(p[2], None, p[4])
        

def p_clist(p):
    '''clist : expr
             | expr COMMA clist
             | empty'''
    if len(p) == 4:
        p[0] = [p[1]] + p[3]
    elif len(p) == 2:
        if p[1] is None:
            p[0] = []
        else:
            p[0] = [p[1]]
    else:
        p[0] = []


def p_type(p):
    '''type : INT
            | VECTOR
            | STRING_TYPE
            | BOOLEAN
            | REF
            | ID
            | NULL'''
    p[0] = p[1]


def p_builtin(p):
    '''builtin : SCAN LPAREN RPAREN
            | PRINT LPAREN expr RPAREN
            | LIST LPAREN expr RPAREN
            | LEN LPAREN expr RPAREN
            | EXIT LPAREN expr RPAREN'''
    
    if p[1] == 'scan':
        p[0] = ScanNode()
    elif p[1] == 'print':
        p[0] = PrintNode(p[3])
    elif p[1] == 'list':
        p[0] = ListNode(p[3])
    elif p[1] == 'length':
        p[0] = LengthNode(p[3])
    elif p[1] == 'exit':
        p[0] = ExitNode(p[3])
    
# =============== EXPRESSION GRAMMAR ===============
def p_expr(p):
    '''expr : assignment_expr'''
    p[0] = p[1]

def p_assignment_expr(p):
    '''assignment_expr : ternary_expr
                      | lvalue EQ expr
                      | lvalue ASSIGN expr'''  
    if len(p) == 2:
        p[0] = p[1]
    elif p[2] == '=': 
        p[0] = AssignmentNode(p[1], p[3])
    else:
        p[0] = RefAssignmentNode(p[1], p[3])

def p_field_access(p):
    '''field_access : postfix_expr DOT ID'''
    p[0] = FieldAccessNode(p[1], p[3])

def p_lvalue(p):
    '''lvalue : ID
              | vector_access
              | field_access'''
    p[0] = p[1]

def p_vector_access(p):
    '''vector_access : ID LSQUAREBR expr RSQUAREBR
                     | vector_literal LSQUAREBR expr RSQUAREBR'''
    p[0] = VectorAccessNode(p[1], p[3])

def p_vector_literal(p):
    '''vector_literal : LSQUAREBR clist RSQUAREBR'''
    p[0] = VectorNode(p[2])

def p_ternary_expr(p):
    '''ternary_expr : logical_or_expr
                    | logical_or_expr QUESTION_MARK expr COLON ternary_expr %prec TERNARY'''
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = TernaryOperation(p[1], p[3], p[5])

def p_logical_or_expr(p):
    '''logical_or_expr : logical_and_expr
                       | logical_or_expr OR logical_and_expr'''
    if len(p) == 2: p[0] = p[1]
    else: p[0] = BinaryOperation(p[1], p[2], p[3])
    
def p_logical_and_expr(p):
    '''logical_and_expr : equality_expr
                        | logical_and_expr AND equality_expr'''
    if len(p) == 2: p[0] = p[1]
    else: p[0] = BinaryOperation(p[1], p[2], p[3])

def p_equality_expr(p):
    '''equality_expr : relational_expr
                     | equality_expr EQUAL relational_expr
                     | equality_expr NEQUAL relational_expr'''
    if len(p) == 2: p[0] = p[1]
    else: p[0] = BinaryOperation(p[1], p[2], p[3])

def p_relational_expr(p):
    '''relational_expr : additive_expr
                       | relational_expr LESS_THAN additive_expr
                       | relational_expr GREATER_THAN additive_expr
                       | relational_expr LEQUAL additive_expr
                       | relational_expr GEQUAL additive_expr'''
    if len(p) == 2: p[0] = p[1]
    else: p[0] = BinaryOperation(p[1], p[2], p[3])

def p_additive_expr(p):
    '''additive_expr : multiplicative_expr
                     | additive_expr PLUS multiplicative_expr
                     | additive_expr MINUS multiplicative_expr'''
    if len(p) == 2: p[0] = p[1]
    else: p[0] = BinaryOperation(p[1], p[2], p[3])

def p_multiplicative_expr(p):
    '''multiplicative_expr : unary_expr
                           | multiplicative_expr TIMES unary_expr
                           | multiplicative_expr DIVIDE unary_expr'''
    if len(p) == 2: p[0] = p[1]
    else: p[0] = BinaryOperation(p[1], p[2], p[3])

def p_unary_expr(p):
    '''unary_expr : postfix_expr
                  | EXCLAMATION unary_expr
                  | MINUS unary_expr %prec UMINUS
                  | REF unary_expr %prec REF'''
    if len(p) == 2:
        p[0] = p[1]
    elif p[1] == 'ref':
        p[0] = RefNode(p[2])
    else:
        p[0] = SingleOperation(p[1], p[2])

def p_postfix_expr(p):
    '''postfix_expr : primary_expr
                    | field_access
                    | postfix_expr LPAREN clist RPAREN
                    | field_access LPAREN clist RPAREN'''
    if len(p) == 2:
        p[0] = p[1] 
    elif len(p) == 5:
        if isinstance(p[1], FieldAccessNode):
            field_access_node = p[1]
            p[0] = MethodCallNode(field_access_node.object_expr, field_access_node.field_name, p[3])
        else:
            p[0] = FunctionCallNode(p[1], p[3])


def p_lambda_expr(p):
    '''lambda_expr : LAMBDA ID ARROW expr'''
    p[0] = LambdaNode(p[2], p[4])

def p_map_expr(p):
    '''map_expr : MAP LPAREN lambda_expr COMMA expr RPAREN'''
    p[0] = MapNode(p[3], p[5])

def p_primary_expr(p):
    '''primary_expr : ID
                    | NUMBER
                    | BOOL
                    | STRING
                    | MULTI_STRING
                    | NULL 
                    | builtin
                    | LPAREN expr RPAREN
                    | vector_literal
                    | vector_access
                    | NEW ID LPAREN clist RPAREN
                    | lambda_expr
                    | map_expr'''
    if len(p) == 2:
        p[0] = p[1]
    elif p[1] == '(':
        p[0] = p[2]
    elif p[1] == 'new':
        p[0] = NewNode(p[2], p[4])
# =============== END EXPRESSION GRAMMAR ===============

def p_empty(p):
    'empty :'
    pass

def p_error(p):
    synchronizing_tokens = ('SEMI_COLON', 'RCURLYEBR', 'END', 'ELSE', 'RPAREN')
    if p:
        error_msg = f"Syntax error at token '{p.value}' on line {p.lineno}"
        print(error_msg)
        error.append(error_msg)
        
        while True:
            tok = parser.token()
            if not tok or tok.type in synchronizing_tokens:
                break
        parser.errok()
        if tok:
            return tok
    else:
        error_msg = "Syntax error at EOF"
        print(error_msg)
        error.append(error_msg)


error = []

try:
    inputFile = open("test.txt", "r")
    data = inputFile.read()
    inputFile.close()
except FileNotFoundError:
    print("Error: test.txt not found. Please create it.")
    data = ""
    error.append("test.txt not found.")

parser = yacc.yacc()
ast = parser.parse(data)

checker = SemanticChecker()
errors = checker.check(ast)

print("\n=============|Syntax Errors|=============\n")
if error:
    for err in error:
        print(err)
else:
    print("No syntax errors found.")

print("\n=============|Semantic Errors|=============\n")
if errors:
    for error in errors:
        print(error)
else:
    print("No semantic errors found.")

print("\n=============|Code Generation|=============\n")
if not error and not errors:
    generator = CodeGenerator(checker.class_table, checker.global_symbol_table)
    tsvm_code = generator.generate(ast)

    with open("output.tsvm", "w") as outfile:
       outfile.write(tsvm_code)
    print("Code written to output.tsvm")
    
    print("Code generated successfully.")
else:
    print("Code generation skipped due to syntax or semantic errors.")