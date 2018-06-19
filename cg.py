from cfg import expr
from vrange import VRange, Future


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

        self.conditionalConstraint = None

    def addSrc(self, node):
        self.srcList.append(node)

    def addUsed(self, node):
        self.usedList.append(node)


class CG:
    def __init__(self, exprList):
        self.nodeDic = {}
        self.nodeList = []
        for ex in exprList:
            opNode = CGNode(False, ex.op)
            self.addNode(opNode)
            for src in ex.srcList:
                if isinstance(src, str):
                    srcNode = self.nodeDic.get(src)
                    if srcNode is None:
                        srcNode = CGNode(True, src)
                        self.addNode(srcNode)
                else:
                    srcNode = CGNode(False, None)
                    self.addNode(srcNode)
                    srcNode.vrange = src
                opNode.addSrc(srcNode)
                srcNode.addUsed(opNode)
            dstNode = self.nodeDic.get(ex.dst)
            assert dstNode is None
            dstNode = CGNode(True, ex.dst)
            self.addNode(dstNode)
            dstNode.addSrc(opNode)
            opNode.addUsed(dstNode)

        for node in self.nodeList:
            if node.vrange is not None:
                r = node.vrange
                controller = None
                if isinstance(r.begin, Future):
                    controller = self.nodeDic.get(r.begin.name)
                if isinstance(r.end, Future):
                    controller = self.nodeDic.get(r.end.name)
                if controller is not None:
                    node.controlled = controller
                    controller.control = node

    def addNode(self, newNode):
        self.nodeList.append(newNode)
        self.nodeDic[len(self.nodeList)-1] = newNode
