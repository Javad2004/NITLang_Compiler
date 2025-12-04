import ply.lex as lex

reserved = {
   'int' : 'INT',
   'vector' : 'VECTOR',
   'string' : 'STRING_TYPE',
   'bool' : 'BOOLEAN',
   'null' : 'NULL',
   'func': 'FUNC',
   'return' : 'RETURN',
   'let' : 'LET',
#    'for' : 'FOR',
   'if' : 'IF',
   'else' : 'ELSE',
   'then' : 'THEN',
   'length' : 'LEN',
   'scan' : 'SCAN',
   'print' : 'PRINT',
   'list' : 'LIST',
   'exit' : 'EXIT',
#    'to' : 'TO',
   'while' : 'WHILE',
   'do' : 'DO',
   'ref'   : 'REF',
   'class' : 'CLASS',
   'new'   : 'NEW',
   'lambda': 'LAMBDA',
   'map'   : 'MAP',
}

tokens = [
   'EQUAL',
   'NEQUAL',
   'GEQUAL',
   'LEQUAL',
   'NUMBER',
   'PLUS',
   'MINUS',
   'TIMES',
   'DIVIDE',
   'LPAREN',
   'RPAREN',
   'LESS_THAN',
   'GREATER_THAN',
   'LCURLYEBR',
   'RCURLYEBR',
   'EQ',
   'SEMI_COLON',
   'LSQUAREBR',
   'RSQUAREBR',
   'COMMA',
   'STRING',
   'EXCLAMATION',
   'OR',
   'AND',
   'QUESTION_MARK',
   'COLON',
   'ID',   
   'BOOL',
#    'DOUBLE_QUOTE',
#    'SINGLE_QUOTE',
   'MULTI_STRING',
   'ASSIGN',
   'DOT',
   'ARROW',
] + list(reserved.values())


t_EQUAL = r'=='
t_NEQUAL = r'!='
t_GEQUAL = r'>='
t_LEQUAL = r'<='
t_AND = r'&&'
t_OR = r'\|\|'
t_PLUS    = r'\+'
t_TIMES   = r'\*'
t_LPAREN  = r'\('
t_RPAREN  = r'\)'
t_LSQUAREBR = r'\['
t_RSQUAREBR = r'\]'
t_QUESTION_MARK = r'\?'
t_DIVIDE  = r'/'
t_MINUS   = r'-'
t_LESS_THAN = r'<'
t_GREATER_THAN = r'>'
t_LCURLYEBR = r'{'
t_RCURLYEBR = r'}'
t_EQ = r'='
t_SEMI_COLON = r';'
t_COMMA = r','
t_EXCLAMATION = r'!'
t_COLON =r':'
t_DOT = r'\.'
t_ASSIGN = r':='
t_ARROW = r'->'

t_ignore  = ' \t'
# t_DOUBLE_QUOTE = r'"'
# t_SINGLE_QUOTE = r"'"
t_ignore_COMMENT = r'\#.*'

states = (
   ('comment', 'exclusive'),
   ('mstring', 'exclusive'),
)

def t_comment(t):
    r'</'
    t.lexer.comment_level = 1
    t.lexer.begin('comment')

def t_comment_open(t):
    r'</'
    t.lexer.comment_level += 1

def t_comment_close(t):
    r'/>'
    t.lexer.comment_level -= 1
    if t.lexer.comment_level == 0:
        t.lexer.begin('INITIAL')
        
def t_comment_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

t_comment_ignore = ' \t'
def t_comment_error(t):
    t.lexer.skip(1)

def t_mstring(t):
    r'"""'
    t.lexer.begin('mstring')
    t.lexer.mstr_buf = []
    t.lexer.mstr_start_line = t.lexer.lineno

def t_mstring_newline(t):
    r'\n+'
    t.lexer.mstr_buf.append(t.value)
    t.lexer.lineno += len(t.value)

def t_mstring_content(t):
    r'(\\.|[^"\\\n]|"(?!"")|""(?!"))+'
    t.lexer.mstr_buf.append(t.value)

def t_mstring_end(t):
    r'"""'
    content = ''.join(t.lexer.mstr_buf)
    t.value = '"""' + content + '"""'
    t.type = 'MULTI_STRING'
    t.lineno = t.lexer.mstr_start_line
    t.lexer.begin('INITIAL')
    return t

def t_mstring_error(t):
    print(f"Illegal character in multi-line string at line {t.lexer.mstr_start_line}")
    t.lexer.skip(1)
t_mstring_ignore = ' \t'

def t_STRING(t):
    r'\"(\\.|[^"\\\n])*\"|\'(\\.|[^\'\\\n])*\''
    return t

def t_NUMBER(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_BOOL(t):
    r'false|true'
    return t

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    t.type = reserved.get(t.value,'ID')
    return t

def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def find_column(input, token):
    line_start = input.rfind('\n', 0, token.lexpos) + 1
    return (token.lexpos - line_start) + 1

def findtoken():
    lexer = lex.lex()
    inputFile = open("test.txt", "r") 
    data=inputFile.read()
    lexer.input(data)
    print(f"| {'Line':^10} | {'Column':^10} | {'Token':^15} | {'Value':^10}")
    print("|------------|------------|-----------------|------------")
    for tok in lexer:
        print(f"| {tok.lineno:^10} | {find_column(data, tok):^10} | {tok.type:^15} |   {tok.value}")


findtoken()