# xu H1/H2 独立证据复核器

仅标准库，兼容Python3.6。脚本不导入运行器、契约模块或driver比较函数，不启动仿真/构建/安装；仅读取证据和对应Git对象。

```bash
python3 docs/validation/xu-hw-optimization-20261102/evidence-tools/verify_hw_evidence.py \
  --server-json /绝对路径/server-json \
  --receipt /绝对路径/observed-receipt.json \
  --repo /home/mxhanks/Projects/ChipContest-xu-optimize-hw \
  --extra-source-archive /绝对路径/xu-hw-extra-interface.tar.xz \
  --out /绝对路径/尚不存在的审核目录
```

如需同时验证传输包外层身份，另加`--archive /原始包.tar.xz --archive-sha256 已核对的完整SHA256`。脚本不解包归档，先核对外层SHA，再核对解包后的transfer manifest。

指定归档时，还会在内存读取全部安全常规成员，逐字节哈希绑定到`--server-json`输入目录，包括原始JSON和派生manifest/摘录。补取的原始小日志归档可以另加`--supplemental-archive /补取包.tar.xz --supplemental-archive-sha256 完整SHA256`；它不修改原始transfer manifest。

输入沿用软件阶段包结构：`experiments.json`、`acceptance/acceptance.json`、各case原始`result.json`、`xu-transfer-manifest.json`、完整`acceptance/host.log`与`numeric.log`。数值仿真日志可提供完整`simulation.log`，或由`xu-simulation-pass-lines-derived.json`提供精确`TASK_PASS/PERF_TASK/SOC_PASS`摘录和原全文SHA。其它日志摘录可放`xu-selected-validation-log-lines.json`。VCS验收还须提供`acceptance/host-wrapper-vcs/simulation.log`全文或含`XU_CACHED_WRAPPER_PASS`的明确派生摘录；其全文SHA须与收据对应。

收据兼容`xu_receipt.py`的experiments/cases、acceptance/cases、build/source/memory pools、按相同层分组和integrity_errors结构。实际硬件取回收据若采用不同schema，先适配字段，不将缺失验证静默忽略。

输出`verification.json`、`comparison.json`和`comparison.md`。审核失败只写`verification.json`并返回非零。复核范围包含：

- 全部原始字节/transfer manifest和收据SHA关联；源码逐文件与main/submodule提交的Git对象一致，固定数值/向量/启动文件与499ba54一致。
- 四个mode精确事务、完整12层、六阶段求和、MAC/busy活动、原始输出/写回数、编译宏和静态内存。
- B0-new-RTL在VCS下逐层TB/mcycle及加载image与原软件B0一致；ELF哈希独立记录，不将编译器临时FILE符号导致的差异判为性能回归。
- H1/H2独立参考、组合参考、严格最优/平局、完整验收全部步骤、final重复、150MHz条件换算和原工具二进制SHA。
- 补充接口源包的内部SHA、原TB与提交对象一致、unified patch精确重建、13个RTL与runtime快照一致；独立原始VCS命令和完整日志中的只读窗口16字忽略写、busy期间CTRL/ADDR读回观察、4,967次接受与退休。该busy操作明确违反固件参数稳定约束，数值校验不在这一补充观察范围内。

完整原日志缺失时，脚本只对提供的摘录做局部解析，不能独立排除其它区域的失败标记；`verification.json`逐日志列出“全文本地检查”“派生摘录”“仅源端全文hash”三类。完整日志检查仍由已核对源码身份的服务器runner承担，源端收据核对完整文件SHA。PPA不在本脚本范围内。

实际服务器包已完成端到端审计。`verification.json`逐项列出原始文件、Git对象、source receipt、日志范围与归档绑定。空摘录只当作源端全文哈希身份，不当作已查看原始日志文本。

`selftest_hw_evidence.py`以真实冻结源码的本地combined real1原始JSON和全日志做隔离反例测试；不导入runtime模块，不调用仿真器。它包含1个阳性控制与16个故意损坏反例，不将隔离测试当作端到端服务器验收。可用当前build目录，或把随交付的`xu-hw-local-screening.tar.xz`解到临时目录后指定`--local-runs`：

```bash
python3 selftest_hw_evidence.py --repo /绝对路径/ChipContest \
  --local-runs /临时目录/xu-hw-local-screening --out /临时目录/selftest.json
```
