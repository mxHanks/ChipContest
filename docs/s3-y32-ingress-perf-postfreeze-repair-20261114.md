# 原1064候选：冻结后的复位修复

本轮从已冻结映射SHA `9b1c0688139e15decdeb0a08b31b50f600bfc3f1fe93056d520ccf3ee501e2e8`继续，所有新实验使用20261114独立目录。23:50冻结数据、回执和报告保持原状。频率、IO、uncertainty、库及原SDC不变，每个原生阶段限8核。

## 当前状态

00:19原生17根／128组复位分布编辑阶段已将DRC从292项降为0，DC apply完成；完整新PT重载和回执已经产生，正在回收原件并独立核验。当前不能在原件及结构证明完成前标为最终验收通过。3个catch removal和4个unknown是独立未闭合项。

## 已排除流程阻塞

旧协调器把17条下游复位分布网试验绑定到无关catch只读诊断，导致两项互相等待；新实验直接以已完成的冻结apply／reload为输入。

新r2复现服务器Python兼容错误：`gzip.compress`不支持`mtime`关键字，网表重绑定解析完成却无法写出封包。改用`io.BytesIO`和`gzip.GzipFile(filename='',mtime=0)`，保留确定性压缩与每份输入SHA封存。旧封包及失败目录保留，新r3通过真实服务器重绑定并进入原生probe。

## 验收口径

每条根按min／max、rise／fall及原有时钟查询有限worst64上下文，272种组合；1477接收端仅用作静态身份目录。完整coverage保持类型总量、数值违例身份和untested身份／原因；所有电气违例逐pin／type比较，禁止新增或恶化。0条路径保持无证据状态，worst64截断单独记录。原生DC回放保留自身及祖先SVF，随后以新PT进程重载；最终映射仍需独立完整连接分区证明、353 SRAM及1796死叶白名单核验。

三个catch外源最大传播的只读API补查与编辑流程分开执行，先读取原生`get_timing_arcs`、`report_delay_calculation`手册和arc属性，再作有限路径查询。任何实际到达数值都不能把unknown required time改记通过。
