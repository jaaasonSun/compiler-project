from vrange import XNum, VRange, Future


class CGNode:
    def __init__(self, isSym, name):
        self.isSym = isSym
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

    def addSrc(self, node):
        self.srcList.append(node)

    def addUsed(self, node):
        self.usedList.append(node)

    def eRangeWithoutFuture(self):
        if self.op == 'union':
            if isinstance(self.srcList[0], Future):
                return self.srcList[1].eRange()
            if isinstance(self.srcList[1], Future):
                return self.srcList[0].eRange()
            return self.eRange()

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
        if self.op == 'phi':
            pass
        if self.op == 'inter':
            pass
        if self.op == '<':
            pass
        if self.op == '>':
            pass
        if self.op == '<=':
            pass
        if self.op == '>=':
            pass
        if self.op == '==':
            pass
        if self.op == '!=':
            pass
        if self.op == 'return':
            raise ValueError('return should be here')
        if self.op == 'return_m':
            pass

        # function calls
        pass


class CGSub:
    op_list = ['+', '-', '*', '/', 'assign', 'int', 'float', 'phi', 'inter',
               '<', '>', '<=', '>=', '==', '!=', 'return', 'return_m']

    def __init__(self, exprList, args):
        self.namedNode = {}
        self.nodeList = []
        self.entry = []
        self.funcCall = []
        self.masterReturn = None
        returnList = []

        for ex in exprList:
            opNode = CGNode(False, ex.op)
            self.addNode(opNode)
            if ex.op not in self.op_list:
                self.funcCall.append(opNode)
            elif ex.op == 'return':
                returnList.extend(ex.srcList)

            for src in ex.srcList:
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
                # even if both ends arre futures,
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
        for retVal in self.returnList:
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
            self.nodeDic[name] = newNode

    def getNode(self, name):
        return self.nodeDic.get(name)


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
        pass


class CGCompressed:
    def __init__(self, CG):
        visited = []
        finished = []
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

    def futureReplacement(self, superNode):
        pass

    def resolveSCC(self):
        for sn in self.topologicalOrdering:
            sn.widen()
            # replace futures in this superNode
            # --
            sn.narrow()
            # replace futures resolved in this superNode
            # --


class CG:
    def __init__(self):
        self.funcList = {}
        self.nodeList = []  # named after CGSub so CGCompressed works for both

    def addFunc(self, exprList, name, args):
        sub = CGSub(exprList)
        self.funcList[name] = sub
        self.allNodeList.extend(sub.nodeList)

    # work in progress
    def connectFunc(self):
        for f in self.funcList:
            for fNode in f.funcCall:
                pass
