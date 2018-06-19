import re
from enum import Enum
import symtab
import vrange


tele = re.compile("(<.+?>)")
cond_tele = re.compile("\((.+)\)")
num_tele = re.compile("^\d+$")

reverse_dict = dict({"<":">=", ">":"<=", "<=":">", ">=":"<", "==":"!=", "!=": "=="})


filename = 'benchmark/t2.ssa'

ftab, stab = symtab.get_symtab(filename)

op_list = ['plus', 'minus', 'mul', 'div', 'assign', 'int', 'float', 'g', 'ge', 'l', 'le', 'e', 'ne', 'phi']
for f in ftab:
    op_list.append(f.name)

operation = Enum('operation', op_list)


class expr(object):
    def __init__(self, line):
        if line.startswith('#'):
            # PHI
            sp = line.split('=')
            self.dst = sp[0].split()[1]
            # self.op = operation.phi
            self.op = 'phi'
            self.src = sp[1][6:-1].split(', ')
            return
            
        # function / operation
        sp = line.strip(';').split(' = ')
        self.dst = sp[0]
        right_part = sp[1].split()
        if right_part[0].startswith('('):                   # ) int or float
            # self.op = operation[right_part[0].strip('()')]
            self.op = right_part[0].strip('()')
            self.src = []
            self.src.append(right_part[1])
        elif right_part[1].startswith('('):                 # ) function
            # self.op = operation[right_part[0]]
            self.op = right_part[0]
            index = sp[1].find('(')                         # ) index
            # print(sp[1], index)
            self.src = sp[1][index + 1: -1].split(', ')
        else:                                               # operation
            self.op = right_part[1]
            self.src = []
            if right_part[0].isnumeric():
                num = int(right_part[0])
                self.src.append(vrange.VRange(num, num))
            else:
                self.src.append(right_part[0])
            
            if right_part[2].isnumeric():
                num = int(right_part[2])
                self.src.append(vrange.VRange(num, num))
            else:
                self.src.append(right_part[2])

    def __str__(self):
        s = "dst: " + self.dst + '\n'
        s += 'op: ' + self.op + '\n'
        s += "src: " + str(self.src) 
        return s

    __repr__ = __str__


class block_parser(object):
    def __init__(self, lines):
        self.constraints = []
        self.lines = []
        for line in lines:
            self.lines.append(line.strip())
        while len(self.lines[-1]) == 0:
            self.lines.pop()
        
        self.name = self.lines[0].strip(':')
        self.goto = []
        self.cond = []
        for i in range(len(self.lines)):
            line = self.lines[i]
            if line.startswith('goto'):
                name = line[4:].strip(';').strip()
                all_goto = tele.findall(name)
                for label in all_goto:
                    self.goto.append(label)
                if "if" in self.lines[i-1]:
                    for _ in all_goto:
                        self.cond.append(cond_parser(self.lines[i-1]))
                elif "else" in self.lines[i-1]:
                    # the end of self.cond is the cond_parser of "if"
                    index = len(self.cond) - 1
                    for _ in all_goto:
                        self.cond.append(self.cond[index].reverse())
                else:
                    # unconditional
                    for _ in all_goto:
                        self.cond.append("unconditional")

    def __str__(self):
        s = 'block: ' + self.name + ', ' + 'goto: '
        for i in range(len(self.goto)):
            s += self.cond[i].__str__() + ' ' + self.goto[i] + ','
        return s
    
    __repr__ = __str__


class cond_parser(object):
    def __init__(self, s):
        if s == None:
            return
        if s == 'unconditional':
            self.uncond = True
            return
        self.uncond = False
        self.expr = cond_tele.findall(s)[0]
        sp = self.expr.split()
        self.cmp = sp[1]
        self.left = sp[0]
        self.right = sp[2]
        if len(num_tele.findall(self.left)) == 0:
            self.left_num = False
        else:
            self.left_num = True
        
        if len(num_tele.findall(self.right)) == 0:
            self.right_num = False
        else:
            self.right_num = True
        
    def __str__(self):
        if self.uncond:
            return "unconditional"
        return self.expr

    __repr__ = __str__

    def reverse(self):
        return cond_parser("(" + self.left + " " + reverse_dict[self.cmp] + " " + self.right + ")")

fin = open(filename, encoding='utf-8')
lines = fin.readlines()
fin.close()

for func in ftab:
    flines = lines[func.start: func.end + 1]
    split = []
    for no in range(func.start, func.end + 1):
        line = lines[no].strip()
        if line.startswith('<') and line.endswith('>:'):
            split.append(no)
    split.append(func.end)

    blocks = []
    for i in range(len(split) - 1):
        # print(lines[split[i]: split[i + 1]])
        blocks.append(block_parser(lines[split[i]: split[i+1]]))
    
    for i in range(len(blocks) - 1):
        if len(blocks[i].goto) == 0:
            blocks[i].goto.append(blocks[i + 1].name)
            blocks[i].cond.append(cond_parser("unconditional"))
        # only if and no else, seems this will not happen, thus i xjb write cond
        if len(blocks[i].lines) >= 2:
            if 'goto' in blocks[i].lines[-1] and 'if' in blocks[i].lines[-2]:
                blocks[i].goto.append(blocks[i+1].name)
                blocks[i].cond.append(cond_parser("unconditional"))
    # 最后一个基本块 后接end
    lb = len(blocks) - 1
    if len(blocks[lb].goto) == 0:
        blocks[lb].goto.append('end')
        blocks[lb].cond.append(cond_parser("unconditional"))
    # the same, seems will not happen, xjb write cond
    if len(blocks[lb].lines) >= 2:
        if 'goto' in blocks[lb].lines[-1] and 'if' in blocks[lb].lines[-2]:
            blocks[lb].goto.append('end')
            blocks[lb].cond.append(cond_parser("unconditional"))

    func.blocks = blocks
    

