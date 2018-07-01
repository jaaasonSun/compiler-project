from vrange import XNum, VRange, Future
import re

entryFuncName = 'foo'


class CGNode:
    def __init__(self, isSym, name):
        self.isSym = isSym
        self.op = None
        if isSym:
            self.name = name
        elif name is not None:
            self.op = name
        self.vrange = None
        self.srcList = []
        self.usedList = []
        self.control = None
        self.controlled = None
        self.superNode = self

    def __str__(self):
        if self.isSym:
            if self.name is None:
                return 'name is None'
            else:
                return self.name
        elif self.op is not None:
            return self.op
        elif self.vrange is not None:
            return self.vrange.__str__()
        else:
            return 'None'

    __repr__ = __str__

    def addSrc(self, node):
        self.srcList.append(node)

    def addUsed(self, node):
        self.usedList.append(node)

    def eRange(self):
        if self.isSym:
            return self.vrange
        if self.op is None:
            return self.vrange
        if self.op == 'PHI':
            # no range is only handled in the case
            # in all other cases, if a src has no range
            # current node also have no range
            if self.srcList[0].vrange is None:
                return self.srcList[1].vrange
            if self.srcList[1].vrange is None:
                return self.srcList[0].vrange

        for src in self.srcList:
            if src.vrange is None:
                return None

        # by now all src have a range, note range can be empty
        # bu this is handled in operators
        if self.op == '+':
            return self.srcList[0].vrange + self.srcList[1].vrange
        if self.op == '+':
            return self.srcList[0].vrange - self.srcList[1].vrange
        if self.op == '+':
            return self.srcList[0].vrange * self.srcList[1].vrange
        if self.op == '+':
            return self.srcList[0].vrange / self.srcList[1].vrange
        if self.op == 'assign':
            return self.srcList[0].vrange
        if self.op == 'int':
            return self.srcList[0].vrange.toInt()
        if self.op == 'float':
            return self.srcList[0].vrange.toFloat()
        if self.op == 'inter':
            if isinstance(self.srcList[0], Future):
                return self.srcList[1].eRange()
            if isinstance(self.srcList[1], Future):
                return self.srcList[0].eRange()
            return self.srcList[0].vrange.intersect(self.srcList[1].vrange)
        if self.op in ['<', '>', '<=', '>=', '==', '!=']:
            result = self.srcList[0].vrange.compare(
                self.srcList[1].vrange, self.op)
            begin = 1
            end = 0
            if True in result:
                end = 1
            if False in result:
                begin = 0
            return VRange(begin, end)
        if self.op == 'return':
            raise ValueError('return should be here')
        if self.op == 'return_m':
            if len(self.srcList) == 0:
                return None
            retRange = self.srcList[0].vrange
            for src in self.srcList:
                retRange = retRange.union(src.vrange)
            return retRange
        # function calls
        # should functions be properly handled,
        # this case would never be triggered
        return VRange('-', '+')


class CGSub:
    op_list = ['+', '-', '*', '/', 'assign', 'int', 'float', 'phi', 'inter',
               '<', '>', '<=', '>=', '==', '!=', 'return', 'return_m']

    def __init__(self, name, exprList, args):
        self.name = name
        self.namedNode = {}
        self.nodeList = []
        self.entry = []
        self.funcCall = []
        self.masterReturn = None
        returnList = []

        stripParen = re.compile('(\(.+?\))')

        for ex in exprList:
            opNode = CGNode(False, ex.op)
            self.addNode(opNode)
            if ex.op not in self.op_list:
                self.funcCall.append(opNode)
            elif ex.op == 'return':
                returnList.extend(ex.src)

            print(ex.dst)
            for i in range(len(ex.src)):
                if isinstance(ex.src[i], str):
                    print(ex.src[i])

            for i in range(len(ex.src)):
                if isinstance(ex.src[i], str):
                    ex.src[i] = stripParen.sub('', ex.src[i])

            if isinstance(ex.dst, str):
                ex.dst = stripParen.sub('', ex.dst)

            print(ex.dst)
            for i in range(len(ex.src)):
                if isinstance(ex.src[i], str):
                    print(ex.src[i])

            for src in ex.src:
                if isinstance(src, str):
                    srcNode = self.getNode(src)
                    if srcNode is None:
                        srcNode = CGNode(True, src)
                        self.addNode(srcNode, src)
                else:
                    srcNode = CGNode(False, None)
                    self.addNode(srcNode)
                    srcNode.vrange = src
                opNode.addSrc(srcNode)
                srcNode.addUsed(opNode)

            dstNode = self.getNode(ex.dst)
            if dstNode is None:
                dstNode = CGNode(True, ex.dst)
                self.addNode(dstNode, ex.dst)
            dstNode.addSrc(opNode)
            opNode.addUsed(dstNode)

        for node in self.nodeList:
            if node.vrange is not None:
                r = node.vrange
                controller = None
                # even if both ends are futures,
                # they are bounded by the same variable
                if isinstance(r.begin, Future):
                    controller = self.getNode(r.begin.name)
                elif isinstance(r.end, Future):
                    controller = self.getNode(r.end.name)
                if controller is not None:
                    node.controlled = controller
                    controller.control = node

        for arg in args:
            self.entry.append(self.namedNode[arg])

        if len(returnList) == 0:
            return
        masterReturn = CGNode(False, 'return_m')
        self.masterReturn = masterReturn
        self.addNode(masterReturn)
        for retVal in returnList:
            if isinstance(retVal, str):
                retNode = self.getNode(retVal)
            else:
                retNode = CGNode(False, None)
                self.addNode(retNode)
                retNode.vrange = retVal
            masterReturn.addSrc(retNode)
            retNode.addUsed(masterReturn)

    def addNode(self, newNode, name=None):
        self.nodeList.append(newNode)
        if name is not None:
            self.namedNode[name] = newNode

    def getNode(self, name):
        return self.namedNode.get(name)


class CGSuperNode:
    def __init__(self, nodeList):
        self.nodeSet = set(nodeList)
        self.srcSet = []
        self.usedSet = []

    def widen(self):
        change = True
        while (change):
            change = False
            for node in self.nodeSet:
                if not node.isSym:
                    continue
                # sym node should only have one predecessor
                eRange = node.srcList[0].eRange()
                if eRange != node.vrange:
                    change = True
                    if node.vrange is None:
                        node.vrange = eRange
                    else:
                        if eRange.begin < node.vrange.begin:
                            node.vrange.begin = XNum('-')
                        if eRange.end > node.vrange.end:
                            node.vrange.end = XNum('+')

    def narrow(self):
        change = True
        while (change):
            change = False
            for node in self.nodeSet:
                if not node.isSym:
                    continue
                # sym node should only have one predecessor
                eRange = node.srcList[0].eRange()
                iRange = node.vrange
                assert iRange is not None
                if iRange.begin == XNum('-') and eRange.begin != XNum('-'):
                    iRange.begin = XNum(eRange.begin)
                    change = True
                if iRange.end == XNum('+') and eRange.end != XNum('+'):
                    iRange.end = XNum(eRange.end)
                    change = True
                if iRange.begin > eRange.begin:
                    iRange.begin = XNum(eRange.begin)
                if iRange.end < eRange.end:
                    iRange.end = XNum(eRange.end)

    def replaceFuture(self):
        # replace futures in this superNode
        for node in self.nodeSet:
            if isinstance(node, VRange):
                if node.beginIsFuture or node.endIsFuture:
                    ctr = node.controlled
                    if str.vrange is None:
                        return
                    if node.beginIsFuture:
                        node.begin = XNum(node.begin.delta) + \
                                     ctr.vrange.begin
                        node.beginIsFuture = False
                    if node.endIsFuture:
                        node.end = XNum(node.end.delta) + \
                                   ctr.vrange.end
                        node.endIsFuture = False


class CGCompressed:
    def __init__(self, cg):
        visited = []
        finished = []
        self.cg = cg
        self.superNodes = set()
        self.topologicalOrdering = []

        for node in CG.nodeList:
            if node not in visited:
                self.forwardDFS(visited, finished, node)

        # compress SCC
        visited.clear()
        for node in reversed(finished):
            if node not in visited:
                self.superNodes.add(self.backwardDFS(visited, node))

        for sn in self.superNodes:
            for node in sn.nodeSet:
                node.superNode = sn

        for node in CG.nodeList:
            for src in node.srcList:
                node.superNode.srcSet.add(src)
                src.superNode.usedSet.add(node)

        # order SCC
        visited.clear()
        for sn in self.superNodes:
            if sn not in self.topologicalOrdering:
                self.topologicalSort(visited, self.topologicalOrdering, sn)

    def forwardDFS(self, visited, finished, node):
        visited.append(node)
        for succ in node.usedList:
            if succ not in visited:
                self.forwardDFS(visited, finished, succ)
        finished.append(node)

    def backwardDFS(self, visited, node):
        superNode = set([node])
        visited.append(node)
        for pred in node.srcList:
            if pred not in visited:
                superNode.union(self.backwardDFS(visited, node))
        return superNode

    def topologicalSort(self, visited, ordered, superNode):
        visited.append(superNode)
        for src in superNode.srcSet:
            if src not in visited:
                self.topologicalSort(src)
        ordered.append(superNode)

    def resolveSCC(self):
        for sn in self.topologicalOrdering:
            sn.replaceFuture()  # replace future resolved by previous superNode
            sn.widen()
            sn.replaceFuture()  # replace future resolved just now
            sn.narrow()


class CG:
    def __init__(self):
        self.funcList = []
        self.nodeList = []  # named after CGSub so CGCompressed works for both
        self.allNodeList = []

    def addFunc(self, name, exprList, args):
        sub = CGSub(name, exprList, args)
        self.funcList.append(sub)
        self.allNodeList.extend(sub.nodeList)

    def connectFunc(self):
        for f in self.funcList:
            for fNode in f.funcCall:
                for g in self.funcList:
                    if g.name == fNode.op:
                        break
                for argCall, argCalled in zip(fNode.srcList, g.entry):
                    if argCall.isSym:
                        assignNode = CGNode(False, 'assign')
                        f.nodeList.append(assignNode)
                        self.allNodeList.append(assignNode)

                        argCall.usedList.remove(fNode)
                        argCall.addUsed(assignNode)
                        assignNode.addSrc(argCall)
                        assignNode.addUsed(argCalled)
                        argCalled.addSrc(assignNode)
                    else:
                        argCall.usedList.remove(fNode)
                        argCall.addUsed(argCalled)
                        argCalled.addSrc(argCall)

                    fNode.usedList[0].srcList = [g.masterReturn]
                    f.nodeList.remove(fNode)
                    self.allNodeList.remove(fNode)

    def buildEntryExit(self, inputRanges):
        for f in self.funcList:
            if f.name == entryFuncName:
                self.entryNodes = [f.getNode(name) for name in f.entry]
                for node, vrange in zip(self.entryNodes, inputRanges):
                    node.vrange = vrange
                self.exitNode = f.masterReturn
                break
