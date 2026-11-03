# xu S1 全SoC综合前后等价原始证据

两个独立S1候选实际服务器Formality均退出0、Verification SUCCEEDED。H2-only为31213个通过点（17136 SRAM黑盒pin、144port、13894DFF、39latch）；SRAM-bias为32748点（18288黑盒pin、144port、14277DFF、39latch）。两者各511 unread DFF；unmatched reference H2为17、SRAM-bias为25，分别包含16/24个adapter valid_read和固定PMU count[15]。原unmatched/report/日志保留。

每次使用实际候选物化RTL、原标准/SRAM库、当次DC的mapped.v/default.svf，输入前后SHA一致；SRAM-bias另读128×16库。网表SHA分别45ea28b8571c58e73a254e27e8a095da95d13792e62e944ac9f44a89932a2f9d、b20516c5dd52e44b355828a9cc2f7e508528612d3e6d584ed6ca599023fafb7d，均与同级formality-and-area-server-20261103此前原面积receipt匹配。没有把其他候选网表的证明拼接过来。

Formality auto_setup采用synthesis未驱动信号处理、直接未驱动输出不验证，SRAM内部作为black box。因此只称条件全SoC数字逻辑综合一致性，不声称SRAM内部、完整150MHz时序、全SoC能耗或比赛资格。源Chisel变更与实际12层/面积见S1验收及此前面积归档；本目录不产生新硬件或选型。

```bash
python3 docs/validation/xu-score-s0-soc-20261102/s1-formality-server-20261103/check-evidence.py
```

检查11个唯一原文件SHA/长度、真实工具状态、比较点/未比较范围、输入冻结及与原面积网表身份一致。原网表/SVF/库本地未取得，未声称重新哈希这些字节。完整campaign原状态包含S2b/S2c条目，相关原文件在另归档；本目录只复核S1两条。

复现时使用对应冻结S1源及同版库，重新物化综合后按原verify.tcl的参考RTL/filelist/incdir、DB、SVF、网表身份执行fm_shell -f verify.tcl；全部路径和实际命令原文已保存，须新输出目录。原始传输包291288 bytes，SHA f78ba592a0ce0ef285dbafdce5368eb636b36cfdfd7d36e9a688d9a8bed479a9，163项原清单及11项选择清单保留，不改日志空白或历史值。
