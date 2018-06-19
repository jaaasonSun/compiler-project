

class var_parser(object):
    def __init__(self, line):
        line = line.strip().strip(';,').strip()
        sp = line.split()
        self.type = sp[0]
        self.name = sp[1]

    def __str__(self):
        return self.type + ' ' + self.name

    __repr__ = __str__

class function_parser(object):
    def __init__(self, line):
        index = line.find('(')          # )
        self.name = line[:index].strip()
        args = line[index + 1: line.find(')')].strip()
        self.args = []
        if len(args) > 0:
            sp = args.split(',')            
            for arg in sp:
                self.args.append(var_parser(arg))
        self.start = self.end = 0
    
    def __str__(self):
        s = '{'
        s += self.name + ': ' + 'start from %d, end to %d: ' % (self.start, self.end)
        for arg in self.args:
            s += arg.__str__() + ', '
        s += '}'
        return s

    __repr__ = __str__


def get_symtab(filename):
    fin = open(filename, encoding='utf-8')
    lines = fin.readlines()
    fin.close()

    status = 0
    # 0: outside any function
    # 1: start of a define of a function
    # 2: declare of var
    # 3: declare of blocks

    functab = []
    symtab = []

    for no in range(len(lines)):
        line = lines[no].strip()
        
        if status == 0:
            if line[:2] == ';;':
                status = 1

        elif status == 1:
            if len(line) == 0:
                continue
            func = function_parser(line)
            func.start = no
            status = 2
            functab.append(func)
            temp_symtab = []

        elif status == 2:
            if len(line) == 0:
                continue
            elif line == '{':
                continue
            elif '<' in line and '>' in line: 
                status = 3
                symtab.append(temp_symtab)
            else:
                temp_symtab.append(var_parser(line))

        elif status == 3:
            if line == '}':
                status = 0
                functab[-1].end = no
    
    return functab, symtab
    

if __name__ == '__main__':
    for i in range(1, 11):
        a, b = get_symtab('benchmark/t%d.ssa' % (i))
        print(a)
        print(b)

