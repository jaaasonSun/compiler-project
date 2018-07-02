# compiler-project

### 使用方法

    $ cfg.py <ssa file name> <argument count> [arg1 [arg2 [...]]]]

每一个`arg`对应输入函数参数，按照出现在参数列表中的顺序，依次输入。每一个`arg`是一对值，例如：

    $ cfg.py t1.ssa 0
    [100, 100]
    $ cfg.py t3.ssa 2 0 10 20 50
    [20, 50]
    $ cfg.py t4.ssa 1 - +
    [0, +]
    
其中`-`表示负无穷，`+`表示正无穷
