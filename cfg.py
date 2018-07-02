import re
import ast
import symtab
import vrange
from cg import CG, CGCompressed
from graphviz import Digraph

tele = re.compile("(<.+?>)")
cond_tele = re.compile("\((.+)\)")
num_tele = re.compile("^\d+$")
real_tele = re.compile(r'^\-?[0-9\.]+$')

in_tele = re.compile(r'([_a-zA-Z0-9]+\(D\)(\(.+?\))?)')

reverse_dict = dict({"<":">=", ">":"<=", "<=":">", ">=":"<", "==":"!=", "!=": "=="})


filename = 'benchmark/t9.ssa'

ftab, stab = symtab.get_symtab(filename)
itab = []

for i in range(len(ftab)):
    for j in range(len(ftab[i].args)):
        stab[i].append(ftab[i].args[j])


fin = open(filename, encoding='utf-8')
lines = fin.readlines()
fin.close()
        

for func in ftab:
    flines = lines[func.start: func.end + 1]
    inname_list = in_tele.findall('\n'.join(flines))
    temp_in_list = []
    for arg in func.args:
        for inname in inname_list:
            if inname[0].split('_')[0] == arg.name:
                temp_in_list.append(inname[0])
                break
    itab.append(temp_in_list)
    # print(func.start, func.end)


# op_list = ['plus', 'minus', 'mul', 'div', 'assign', 'int', 'float', 'g', 'ge', 'l', 'le', 'e', 'ne', 'phi']
# for f in ftab:
#     op_list.append(f.name)

# operation = Enum('operation', op_list)


def find_int_def(varname, symbol):
    name = varname.split('_')[0]
    for s in symbol:
        if s.name == name:
            if s.type == 'int':
                return True
            else:
                return False
    # not found
    print("????? Not Found ?????", varname, symbol)
    return True


class expr(object):
    def __init__(self, line='null'):
        if line == 'null':
            return
        if line.startswith('#'):
            # PHI
            sp = line.split('=')
            self.dst = sp[0].split()[1]
            # self.op = operation.phi
            self.op = 'phi'
            self.src = sp[1][6:-1].split(', ')
            return

        if 'return' in line:
            sp = line.split()
            self.dst = None
            self.op = 'return'
            self.src = []
            if len(sp) == 2:
                src = sp[1]
                if real_tele.search(src):
                    num = ast.literal_eval(src)
                    self.src.append(vrange.VRange(num, num))
                else:
                    self.src.append(src)
            return

            
        # function / operation
        sp = line.strip(';').split(' = ')
        self.dst = sp[0]
        right_part = sp[1].split()
        # print(len(right_part))
        if len(right_part) == 1:                            # assign
            self.op = 'assign'
            self.src = []
            if real_tele.search(right_part[0]):
                # num = int(right_part[0])
                num = ast.literal_eval(right_part[0])
                self.src.append(vrange.VRange(num, num))
            else:
                self.src.append(right_part[0])
        elif right_part[0].startswith('('):                 # ) int or float
            # self.op = operation[right_part[0].strip('()')]
            self.op = right_part[0].strip('()')
            self.src = []
            self.src.append(right_part[1])
        elif right_part[1].startswith('('):                 # ) function
            # self.op = operation[right_part[0]]
            for findex in range(len(ftab)):
                if ftab[findex].name == right_part[0]:
                    break
            self.op = right_part[0] + '_' + str(ftab[findex].called_times)
            ftab[findex].called_times += 1
            index = sp[1].find('(')                         # ) find the index
            # print(sp[1], index)
            temp_src = sp[1][index + 1: -1].split(', ')
            self.src = []
            for src in temp_src:
                if real_tele.search(src):
                    num = ast.literal_eval(src)
                    self.src.append(vrange.VRange(num, num))
                else:
                    self.src.append(src)

        else:                                               # operation
            self.op = right_part[1]
            self.src = []
            if real_tele.search(right_part[0]):
                # num = int(right_part[0])
                num = ast.literal_eval(right_part[0])
                self.src.append(vrange.VRange(num, num))
            else:
                self.src.append(right_part[0])
            
            if real_tele.search(right_part[2]):
                # num = int(right_part[2])
                num = ast.literal_eval(right_part[2])
                self.src.append(vrange.VRange(num, num))
            else:
                self.src.append(right_part[2])

    def __str__(self):
        s = ''
        if self.dst:
            s += "dst: " + self.dst + '\t'
        s += 'op: ' + self.op + '\t'
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
        self.pre = []
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
                        self.cond.append(cond_parser("unconditional"))

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

# 处理完goto了

for func in ftab:
    func.new_blocks = []
    temp_set = set()
    temp_set.add(func.blocks[0].name)
    func.new_blocks.append(func.blocks[0])
    bfs = []
    for b in func.blocks[0].goto:
        bfs.append(b)
    while len(func.new_blocks) != len(func.blocks):
        for index in range(len(func.blocks)):
            if func.blocks[index].name == bfs[0]:
                break
        if func.blocks[index].name in temp_set:
            bfs = bfs[1:]
            continue
        func.new_blocks.append(func.blocks[index])
        temp_set.add(func.blocks[index].name)
        for goto_name in func.blocks[index].goto:
            if goto_name not in temp_set:
                bfs.append(goto_name)
        bfs = bfs[1:]
    
    func.blocks = func.new_blocks

for func in ftab:
    for b in func.blocks:
        for g in b.goto:
            flag = False
            for index in range(len(func.blocks)):
                if func.blocks[index].lines[0].startswith(g):
                    flag = True
                    break
            # print(index, b.name)
            if flag:
                func.blocks[index].pre.append(b.name)

# 求DOM集合
for func in ftab:
    dom = {}
    allName = [b.name for b in func.blocks]
    for b in func.blocks:
        dom[b.name] = set(allName)
    dom[func.blocks[0].name] = set([func.blocks[0].name])
    change = True
    while change:
        change = False
        for b in func.blocks:
            if len(b.pre) == 0:
                continue
            predDom = dom[b.pre[0]]
            for pred in b.pre:
                predDom = predDom & dom[pred]
            oldDom = dom[b.name].copy()
            dom[b.name] = set([b.name]).union(predDom)
            if len(oldDom.difference(dom[b.name])) != 0:
                change = True
    print(dom)
    for b in func.blocks:
        b.reverse_dom = []
    for target in dom:
        for source in dom[target]:
            for index in range(len(func.blocks)):
                if func.blocks[index].name == source:
                    func.blocks[index].reverse_dom.append(target)
                    break


for i in range(len(ftab)):
    ftab[i].called_times = 0


for h in range(len(ftab)):
    func = ftab[h]
    for b in func.blocks:
        for i in range(len(b.cond)):
            if b.cond[i].uncond:
                continue
            if b.cond[i].cmp == '!=':
                continue

            index = 0
            flag = False
            for index in range(len(func.blocks)):
                if func.blocks[index].lines[0].startswith(b.goto[i]):
                    flag = True
                    break
            # if index == len(func.blocks):
            if not flag:
                print("not found")
                continue
            # find the block
            cons = expr()
            cons.op = 'inter'
            cons.src = []

            if real_tele.search(b.cond[i].left):
                num = ast.literal_eval(b.cond[i].left)
                cons.dst = b.cond[i].right
                cons.src.append(b.cond[i].right)

                if b.cond[i].cmp == '<':
                    if type(num) == type(1.0):
                        cons.src.append(vrange.VRange(num, '+'))
                    else:
                        cons.src.append(vrange.VRange(num + 1, '+'))
                elif b.cond[i].cmp == '>':
                    if type(num) == type(1.0):
                        cons.src.append(vrange.VRange('-', num))
                    else:
                        cons.src.append(vrange.VRange('-', num - 1))
                elif b.cond[i].cmp == '==':
                    cons.op = 'assign'
                    cons.src = []
                    cons.src.append(vrange.VRange(num, num))
                elif b.cond[i].cmp == '<=':
                    cons.src.append(vrange.VRange(num, '+'))
                elif b.cond[i].cmp == '>=':
                    cons.src.append(vrange.VRange('-', num))
                # else b.cond[i].cmp == '!=': no kaolv

                from_str = cons.dst
                if i == 0:
                    to_str = from_str + 't'
                else:
                    to_str = from_str + 'f'
                
                cons.dst = to_str

                func.blocks[index].constraints.append(cons)
                for shit in func.blocks[index].reverse_dom:
                    for jindex in range(len(func.blocks)):
                        if func.blocks[jindex].name == shit:
                            break
                    # hhh
                    for fi in range(len(func.blocks[jindex].lines)):
                        func.blocks[jindex].lines[fi] = func.blocks[jindex].lines[fi].replace(from_str, to_str)
                    for fi in range(len(func.blocks[jindex].cond)):
                        if func.blocks[jindex].cond[fi].uncond:
                            continue
                        func.blocks[jindex].cond[fi] = cond_parser('(' + func.blocks[jindex].cond[fi].expr.replace(from_str, to_str) + ')')



            elif  real_tele.search(b.cond[i].right):
                num = ast.literal_eval(b.cond[i].right)
                cons.dst = b.cond[i].left
                cons.src.append(b.cond[i].left)

                if b.cond[i].cmp == '<':
                    if type(num) == type(1.0):
                        cons.src.append(vrange.VRange('-', num))
                    else:
                        cons.src.append(vrange.VRange('-', num - 1))
                elif b.cond[i].cmp == '>':
                    if type(num) == type(1.0):
                        cons.src.append(vrange.VRange(num, '+'))
                    else:
                        cons.src.append(vrange.VRange(num + 1, '+'))
                elif b.cond[i].cmp == '==':
                    cons.op = 'assign'
                    cons.src = []
                    cons.src.append(vrange.VRange(num, num))
                elif b.cond[i].cmp == '<=':
                    cons.src.append(vrange.VRange('-', num))
                elif b.cond[i].cmp == '>=':
                    cons.src.append(vrange.VRange(num, '+'))
                # else b.cond[i].cmp == '!=': bukaolv

                from_str = cons.dst
                if i == 0:
                    to_str = from_str + 't'
                else:
                    to_str = from_str + 'f'

                cons.dst = to_str

                func.blocks[index].constraints.append(cons)
                for shit in func.blocks[index].reverse_dom:
                    for jindex in range(len(func.blocks)):
                        if func.blocks[jindex].name == shit:
                            break
                    # hhh
                    for fi in range(len(func.blocks[jindex].lines)):
                        func.blocks[jindex].lines[fi] = func.blocks[jindex].lines[fi].replace(
                            from_str, to_str)
                    for fi in range(len(func.blocks[jindex].cond)):
                        if func.blocks[jindex].cond[fi].uncond:
                            continue
                        # print(func.blocks[jindex].cond[fi].expr.replace(from_str, to_str))
                        func.blocks[jindex].cond[fi] = cond_parser('(' + func.blocks[jindex].cond[fi].expr.replace(from_str, to_str) + ')')
                
            else:
                # both sides are var, you need to use ft()
                cons2 = expr()
                cons2.op = 'inter'
                cons2.src = []

                cons.dst = b.cond[i].left
                cons.src.append(b.cond[i].left)
                cons2.dst = b.cond[i].right
                cons2.src.append(b.cond[i].right)

                if b.cond[i].cmp == '<':
                    if find_int_def(b.cond[i].left, stab[h]):
                        cons.src.append(vrange.VRange('-', (b.cond[i].right, -1)))
                        cons2.src.append(vrange.VRange((b.cond[i].left, 1), '+'))
                    else:
                        cons.src.append(vrange.VRange('-', (b.cond[i].right, 0)))
                        cons2.src.append(vrange.VRange((b.cond[i].left, 0), '+'))
                elif b.cond[i].cmp == '>':
                    if find_int_def(b.cond[i].left, stab[h]):
                        cons.src.append(vrange.VRange((b.cond[i].right, 1), '+'))
                        cons2.src.append(vrange.VRange('-', (b.cond[i].left, -1)))
                    else:
                        cons.src.append(vrange.VRange((b.cond[i].right, 0), '+'))
                        cons2.src.append(vrange.VRange('-', (b.cond[i].left, 0)))
                elif b.cond[i].cmp == '==':
                    cons.src.append(vrange.VRange((b.cond[i].right, 0), (b.cond[i].right, 0)))
                    cons2.src.append(vrange.VRange((b.cond[i].left, 0), (b.cond[i].left, 0)))
                elif b.cond[i].cmp == '<=':
                    cons.src.append(vrange.VRange('-', (b.cond[i].right, 0)))
                    cons2.src.append(vrange.VRange((b.cond[i].left, 0), '+'))
                elif b.cond[i].cmp == '>=':
                    cons.src.append(vrange.VRange((b.cond[i].right, 0), '+'))
                    cons2.src.append(vrange.VRange('-', (b.cond[i].left, 0)))
                # else '!=', buguanle

                from_str = cons.dst
                from_str2 = cons2.dst
                if i == 0:
                    to_str = from_str + 't'
                    to_str2 = from_str2 + 't'
                else:
                    to_str = from_str + 'f'
                    to_str2 = from_str2 + 'f'

                cons.dst = to_str
                cons2.dst = to_str2

                func.blocks[index].constraints.append(cons)
                func.blocks[index].constraints.append(cons2)

                for shit in func.blocks[index].reverse_dom:
                    for jindex in range(len(func.blocks)):
                        if func.blocks[jindex].name == shit:
                            break
                    # hhh
                    for fi in range(len(func.blocks[jindex].lines)):
                        func.blocks[jindex].lines[fi] = func.blocks[jindex].lines[fi].replace(
                            from_str, to_str)
                        func.blocks[jindex].lines[fi] = func.blocks[jindex].lines[fi].replace(
                            from_str2, to_str2)
                    for fi in range(len(func.blocks[jindex].cond)):
                        if func.blocks[jindex].cond[fi].uncond:
                            continue
                        func.blocks[jindex].cond[fi] = cond_parser('(' + func.blocks[jindex].cond[fi].expr.replace(from_str, to_str) + ')')
                        func.blocks[jindex].cond[fi] = cond_parser('(' + func.blocks[jindex].cond[fi].expr.replace(from_str2, to_str2) + ')')



for func in ftab:
    for b in func.blocks:
        for l in b.lines:
            if ' = ' in l or 'return' in l:
                b.constraints.append(expr(l.strip(';')))

graph = CG()
for func, args in zip(ftab, itab):
    constraints = []
    for b in func.blocks:
        constraints.extend(b.constraints)
    for c in constraints:
        print(c)
    graph.addFunc(func.name, constraints, args)

graph.connectFunc()
dot = Digraph('test')
for n in graph.allNodeList:
    dot.node(str(id(n)), n.__str__())

for n in graph.allNodeList:
    for used in n.usedList:
        dot.edge(str(id(n)), str(id(used)))
    if n.control is not None:
        dot.edge(str(id(n)), str(id(n.control)))

dot.render('./test.gv')


# graph.buildEntryExit(inputRanges)
# compressed = CGCompressed(graph)
# compressed.resolveSCC()
# Print(compressed.cg.exitNode.vrange)
