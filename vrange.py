class XNum:
    def __init__(self, num):
        if isinstance(num, XNum):
            self.num = num.num
        elif isinstance(num, str):
            if num != '+' and num != '-':
                raise ValueError('string not infinity')
        self.num = num

    def __str__(self):
        return '{}'.format(self.num)

    __repr__ = __str__

    def __lt__(self, other):
        if self == other:
            return False
        if self.num == '-' or other.num == '+':
            return True
        if self.num == '+' or other.num == '-':
            return False
        return self.num < other.num

    def __le__(self, other):
        if self == other:
            return True
        if self < other:
            return True
        return False

    def __gt__(self, other):
        return not self < other

    def __ge__(self, other):
        return not self <= other

    def __add__(self, other):
        if not isinstance(self.num, str) and not isinstance(other.num, str):
            num = self.num + other.num
            return XNum(num)
        elif not isinstance(self.num, str):
            return XNum(other.num)
        elif not isinstance(other.num, str):
            return XNum(self.num)
        else:
            if (self.num == '-' and other.num == '+') or \
               (self.num == '-' and other.num == '+'):
                raise ValueError('adding - and +')
            else:
                return XNum(self.num)

    def __neg__(self):
        if self.num == '-':
            return XNum('+')
        elif self.num == '+':
            return XNum('-')
        else:
            return XNum(-self.num)

    def __sub__(self, other):
        return self + (-other)

    def __mul__(self, other):
        if self.num == 0 or other.num == 0:
            return XNum(0)
        elif isinstance(self.num, str) or isinstance(self.num, str):
            if (self < XNum(0) and other < XNum(0)) or \
               (self > XNum(0) and other > XNum(0)):
                return XNum('+')
            else:
                return XNum('-')
        else:
            return self.num * other.num

    def __truediv__(self, other):
        if other.num == 0:
            return XNum('+') if self > XNum(0) else XNum('-')
        elif other.num == '+' or other.num == '-':
            if isinstance(self.num, str):
                raise ValueError('inf div inf')
            return XNum(0)
        elif (self.num == '+' and other.num > 0) or \
             (self.num == '-' and other.num < 0):
            return XNum('+')
        elif (self.num == '-' and other.num > 0) or \
             (self.num == '+' and other.num < 0):
            return XNum('-')
        elif isinstance(self.num, int) and isinstance(other.num, int):
            return XNum(self.num // other.num)
        else:
            return XNum(self.num / other.num)


class Future:
    def __init__(self, name, delta):
        self.name = name
        self.delta = delta

    def __str__(self):
        return 'ft({}){}{}'.format(self.name, '' if self.delta == 0 else
                                   ('+' if self.delta > 0 else '-'),
                                   '' if self.delta == 0 else abs(self.delta))

    __repr__ = __str__


class VRange:
    def __init__(self, begin=None, end=None):
        if begin is None:
            self.isEmpty = True
            return
        else:
            self.isEmpty = False
        if type(begin) is tuple:
            self.beginIsFuture = True
            self.begin = Future(begin[0], begin[1])
        else:
            self.beginIsFuture = False
            self.begin = XNum(begin)

        if type(end) is tuple:
            self.endIsFuture = True
            self.end = XNum(end)
        else:
            self.endIsFuture = False
            self.end = XNum(end)

    def __str__(self):
        return "[{}, {}]".format(self.begin, self.end)

    __repr__ = __str__

    def __add__(self, other):
        if self.isEmpty or other.isEmpty:
            return VRange()
        return VRange(self.begin + other.begin, self.end + other.end)

    def __sub__(self, other):
        if self.isEmpty or other.isEmpty:
            return VRange()
        return VRange(self.begin - other.end, self.end - other.begin)

    def __mul__(self, other):
        if self.isEmpty or other.isEmpty:
            return VRange()
        ends = [self.begin*other.begin, self.begin*other.end,
                self.end*other.begin, self.end*other.end]
        return VRange(min(ends), max(ends))

    def __truediv__(self, other):
        if self.isEmpty or other.isEmpty:
            return VRange()
        if other.begin <= 0 and 0 <= other.end:
            return VRange('-', '+')
        ends = [self.begin/other.begin, self.begin/other.end,
                self.end/other.begin, self.end/other.end]
        return VRange(min(ends), max(ends))

    def intersect(self, other):
        if self.isEmpty or other.isEmpty or \
           max(self.begin, other.begin) > min(self.end, other.end):
            return VRange()
        return VRange(max(self.begin, other.begin), min(self.end, other.end))

    def union(self, other):
        if self.isEmpty and other.isEmpty:
            return VRange()
        elif self.isEmpty:
            return VRange(other.begin, other.end)
        elif other.isEmpty:
            return VRange(self.begin, self.end)
        else:
            return VRange(min(self.begin, other.begin),
                          max(self.end, other.end))
