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
        self.control = []
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
        if self.op == 'phi':
            # no range is only handled in the case
            # in all other cases, if a src has no range
            # current node also have no range
            if self.srcList[0].vrange is None:
                return self.srcList[1].vrange
            if self.srcList[1].vrange is None:
                return self.srcList[0].vrange
            return self.srcList[0].vrange.union(self.srcList[1].vrange)

        for src in self.srcList:
            if src.vrange is None:
                return None

        # by now all src have a range, note range can be empty
        # bu this is handled in operators
        if self.op == '+':
            return self.srcList[0].vrange + self.srcList[1].vrange
        if self.op == '-':
            return self.srcList[0].vrange - self.srcList[1].vrange
        if self.op == '*':
            return self.srcList[0].vrange * self.srcList[1].vrange
        if self.op == '/':
            return self.srcList[0].vrange / self.srcList[1].vrange
        if self.op == 'assign':
            return self.srcList[0].vrange
        if self.op == 'int':
            return self.srcList[0].vrange.toInt()
        if self.op == 'float':
            return self.srcList[0].vrange.toFloat()
        if self.op == 'inter':
            vr0 = self.srcList[0].vrange
            vr1 = self.srcList[1].vrange
            if not vr0.isEmpty:
                if vr0.beginIsFuture:
                    vr0 = VRange('-', vr0.end)
                if vr0.endIsFuture:
                    vr0 = VRange(vr0.begin, '+')
            if not vr1.isEmpty:
                if vr1.beginIsFuture:
                    vr1 = VRange('-', vr1.end)
                if vr1.endIsFuture:
                    vr1 = VRange(vr1.begin, '+')
            return vr0.intersect(vr1)
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

        stripParen = re.compile('(\(\d+?\))')

        for ex in exprList:
            for i in range(len(ex.src)):
                if isinstance(ex.src[i], str):
                    ex.src[i] = stripParen.sub('', ex.src[i])

        if isinstance(ex.dst, str):
            ex.dst = stripParen.sub('', ex.dst)

        args = [stripParen.sub('', arg) for arg in args]

        for ex in exprList:
            if ex.op == 'return':
                # do not create a node for return (just yet)
                returnList.extend(ex.src)

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
                continue

            opNode = CGNode(False, ex.op)
            self.addNode(opNode)
            if ex.op not in self.op_list:
                self.funcCall.append(opNode)

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
                # even if both ends are futures,
                # they are bounded by the same variable
                if isinstance(r.begin, Future):
                    controller = self.getNode(r.begin.name)
                    node.controlled = controller
                    controller.control.append(node)
                elif isinstance(r.end, Future):
                    controller = self.getNode(r.end.name)
                    node.controlled = controller
                    controller.control.append(node)

        for arg in args:
            eNode = self.getNode(arg)
            if eNode is None:
                eNode = CGNode(True, arg)
            self.entry.append(eNode)

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
        self.srcSet = set()
        self.usedSet = set()

    def widen(self):
        change = True
        while (change):
            change = False
            for node in self.nodeSet:
                if not node.isSym:
                    continue
                # sym node should only have one predecessor
                if len(node.srcList) == 0:
                    if node.vrange is None:
                        node.vrange = VRange('-', '+')
                        change = True
                    continue

                eRange = node.srcList[0].eRange()
                if eRange is None:
                    continue
                elif node.vrange is None:
                    change = True
                    node.vrange = VRange(eRange)
                elif eRange != node.vrange:
                    if node.vrange.isEmpty:
                        node.vrange = VRange(eRange)
                    else:
                        if eRange.begin < node.vrange.begin:
                            node.vrange.begin = XNum('-')
                            change = True
                        if eRange.end > node.vrange.end:
                            node.vrange.end = XNum('+')
                            change = True

    def narrow(self):
        change = True
        while (change):
            change = False
            for node in self.nodeSet:
                if not node.isSym:
                    continue
                # sym node should only have one predecessor
                if len(node.srcList) == 0:
                    continue

                eRange = node.srcList[0].eRange()
                iRange = node.vrange
                assert iRange is not None
                if iRange != eRange:
                    if iRange.isEmpty:
                        node.vrange = VRange(eRange.begin, eRange.end)
                        change = True
                        continue
                    if eRange.isEmpty:
                        node.vrange - VRange()
                        continue
                    if iRange.begin == XNum('-') and eRange.begin != XNum('-'):
                        iRange.begin = XNum(eRange.begin)
                        change = True
                    if iRange.end == XNum('+') and eRange.end != XNum('+'):
                        iRange.end = XNum(eRange.end)
                        change = True
                    if iRange.begin > eRange.begin:
                        iRange.begin = XNum(eRange.begin)
                        change = True
                    if iRange.end < eRange.end:
                        iRange.end = XNum(eRange.end)
                        change = True

    def replaceFuture(self):
        # replace futures in this superNode
        for node in self.nodeSet:
            if not node.isSym and node.op is None and not node.vrange.isEmpty:
                vr = node.vrange
                if vr.beginIsFuture or vr.endIsFuture:
                    ctr = node.controlled
                    if ctr.vrange is None:
                        return
                    if ctr.vrange.isEmpty:
                        node.vrange = VRange()
                        return
                    if vr.beginIsFuture:
                        vr.begin = XNum(vr.begin.delta) + ctr.vrange.begin
                        vr.beginIsFuture = False
                    if vr.endIsFuture:
                        vr.end = XNum(vr.end.delta) + ctr.vrange.end
                        vr.endIsFuture = False


class CGCompressed:
    def __init__(self, cg):
        visited = []
        finished = []
        self.cg = cg
        self.superNodes = []
        self.topologicalOrdering = []

        for node in cg.nodeList:
            if node not in visited:
                self.forwardDFS(visited, finished, node)

        # compress SCC
        visited.clear()
        for node in reversed(finished):
            if node not in visited:
                nodeSet = self.backwardDFS(visited, node)
                self.superNodes.append(CGSuperNode(nodeSet))

        for sn in self.superNodes:
            for node in sn.nodeSet:
                node.superNode = sn

        for node in cg.nodeList:
            for src in node.srcList:
                if node.superNode != src.superNode:
                    node.superNode.srcSet.add(src.superNode)
                    src.superNode.usedSet.add(node.superNode)
            for c in node.control:
                if node.superNode != c.superNode:
                    node.superNode.usedSet.add(c.superNode)
                    c.superNode.srcSet.add(node.superNode)

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
        for succ in node.control:
            if succ not in visited:
                self.forwardDFS(visited, finished, succ)
        finished.append(node)

    def backwardDFS(self, visited, node):
        superNode = set([node])
        visited.append(node)
        for pred in node.srcList:
            if pred not in visited:
                superNode = superNode.union(self.backwardDFS(visited, pred))
        if node.controlled is not None and node.controlled not in visited:
            superNode = superNode.union(
                self.backwardDFS(visited, node.controlled))
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

    def addFunc(self, name, exprList, args):
        sub = CGSub(name, exprList, args)
        self.funcList.append(sub)
        self.nodeList.extend(sub.nodeList)

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
                        self.nodeList.append(assignNode)

                        argCall.usedList.remove(fNode)
                        argCall.addUsed(assignNode)
                        assignNode.addSrc(argCall)
                        assignNode.addUsed(argCalled)
                        argCalled.addSrc(assignNode)
                    else:
                        argCall.usedList.remove(fNode)
                        argCall.addUsed(argCalled)
                        argCalled.addSrc(argCall)

                    nextNode = fNode.usedList[0]
                    nextNode.srcList = [g.masterReturn]
                    g.masterReturn.usedList.append(nextNode)
                    f.nodeList.remove(fNode)
                    self.nodeList.remove(fNode)

    def buildEntryExit(self, inputRanges):
        for f in self.funcList:
            if f.name == entryFuncName:
                for node, vrange in zip(f.entry, inputRanges):
                    node.vrange = vrange
                self.exitNode = f.masterReturn
                break
