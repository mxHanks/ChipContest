# 41 位内部累加：可选真实 RTL 原型

## 范围与结论

保持 signed16×signed16 乘法、signed40 bias、每个点积 64 项、所有 signed48 输出、Y32/RNE 和 CPU/总线/固件配置。仅将 8 个 MacPE 的内部 ACC 从 48 位缩至 41 位；resultReg 仍为 8×48 位，两槽 FIFO 仍为 2×8×48 位。历史默认仍为 48 位，可通过显式 `LinearAutoGroupCore41` 生成 41 位候选。通用 `MacPE()` 仍使用 48 位，不把有限 64 项的证明扩张为无限次累加契约。

当前原型生产输入是 `../acc41-repo`，其 `rtl/e203/perips/MacPE.sv` 已换成显式 41 位生成结果供同条件仿真；它是独立实验目录，不改变主工作目录或默认生产版本。生产源码初始冻结记录见 `production-source-frozen.json`；v2 仅增加固定 64 项 engine 的 elaboration guard，记录见 `production-source-frozen-v2.json`。显式拒绝 `DotProductEngine(accWidth=40)`，默认 48/可选41 的全部生成 SV SHA 均与 guard 前一致。

41 位覆盖完整输入域的每个 0..64 前缀。40 位不够：`bias=549755813887, x=1, w=1`，一步后精确值为 `549755813888`，signed40 却变成 `-549755813888`。

## 完整域证明

16 位有符号输入均在 `[-32768,32767]`。乘法对每个操作数均线性，因此矩形域的极值落在四个角，得到：

- 单个乘积最小值 `-1073709056`，最大值 `1073741824`。
- signed40 bias 范围 `[-549755813888,549755813887]`。
- 对任意前缀长度 n∈[0,64]，精确部分和属于 `[bias_min+n*product_min, bias_max+n*product_max]`。
- 最宽的 n=64 区间为 `[-618473193472,618475290623]`，完整落在 signed41 范围 `[-1099511627776,1099511627775]`。

基例是 INIT 的 bias，归纳步骤是增加任意一个合法乘积。每个中间值均可表示，因此 RTL 加法不会截断精确值；停顿不更新 ACC，INIT 覆盖前值并优先于 enable，reset 返回零。这里证明的是所有输入值，不是由随机采样推断。

脚本以 Python 精确整数计算四角极值，并列出全部 65 个前缀区间；见 `full-domain-proof.json`。该数学证明不依赖模拟器的随机覆盖。

## 已完成检查

`result.json` 和原始日志保存完整结果：

- 真实 Chisel 生成的 48/41/40 位 MacPE 同时运行，每个边沿与独立 64 位整数参考值比较；36 类输入、65 个前缀、3345 次检查。
- 36 类场景包括两个 bias 极值、乘积四角、混合符号/抵消、确定性任意输入、正负 ties；396 个 enable 停顿、4 个 reset、39 次 INIT（含 enable 同时有效的优先级）。
- Y32 使用幅值除法 oracle 与 RTL 风格 floor/余数 RNE 比较，覆盖 351 个正 ties、506 个负 ties。
- 40 位原型出现 1127 次与精确值不同，最短一步反例单独断言。
- 默认 48 位另测 600 项连续累加，保留通用使用能力；41 位契约仅覆盖 0..64 项。
- 既有真实 READY wrapper 回归通过：32 组/256 个 Y32、输入域上下界、正负奇偶 ties、bundle/commit/共享写入/完成背压、写入错误、旧 MMIO POP 竞争，以及 capture/valid/owned 三阶段 reset。
- 418 个 READY 单元场景、19 个旧 direct 错误场景、功能禁用/无副作用路径通过。
- 默认完整 `LinearAutoGroupCore` 的 12 个生成模块与冻结基线逐文件 SHA256 一致；显式41 variant 中仅 `MacPE.sv` 不同。见 `generated-structure-check.json`。
- 初版冻结后的唯一源码变动是上述 engine 参数合法性 guard；更新 v2 冻结后漂移为空。没有改受测 SV；见 `guard-v2-*-unchanged.json`。

复验命令（在 `acc41-repo` 下）：

```bash
python3 ../acc41-checks/check_acc41.py
XU_READY_LOG_DIR=../acc41-checks/ready-logs python3 -B -m unittest discover -s tests/e203 -p test_nice_ready_wrapper.py
```

主脚本记录所有实际命令与退出码到 `commands.json`、独立编译/仿真日志；`initial-generation.log` 记录第一次完整41 variant 生成。测试中的模块改名仅为允许三个真实生成实现同场比较，不修改算术逻辑；源文件分别来自 `generated/MacPE`、`generated/LinearAutoGroupCore41` 和 `generated/MacPE40Counterexample`。

## 成本与限制

原始 8 个 ACC 的逻辑存储位数由 384 降到 328，仅节省 56 位。加法表达式宽度随 ACC 改变，16×16 乘法不变。这里只统计源码可证的寄存器位数，不等同于标准单元面积、时序、动态功耗或整体 PPA 改善。

没有综合；没有改变流水深度和任何接口握手，预计周期相同。同条件单层及 full12 的实际周期/输出验证由外层 campaign 保存，不能把本单元检查代替完整 SoC 实测。应作为可选面积候选保留，不能凭“位宽更小”认定其优于默认版本。

保留已有正式状态：开发仿真通过仍不能替代正式验收，物理清零/策略审核等既有未关闭项不因本实验自动通过。
