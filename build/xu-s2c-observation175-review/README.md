# xu175 独立复核

对 175 的源码、原 174 包、实际 167 simulation/state/TB/C 和 175 输出进行只读复核，未发现阻断 175 分析交付的问题。
本复核没有修改 175 或生产代码，没有远程操作，也没有新增 EDA 实验。

独立原日志解码再次确认：fatal 八项仅 `bias_commit=x`，其余七项均为已知零；task-local、TB 采样值及同次当前 native 值一致。
131 个起始快照、304 条转换、131 个 fatal 快照合计 566 条事件，包含全部 12 个 shared 端口。
更早的 D 瞬态 X、起始 `NOTIFIER=x`、无效 response data 的 X 均未被遗漏或误称为首发原因。
原 target hold 告警、NOTIFIER/n0/Q 和稍后的 bias X 只有时间关联；callback serial 不表示 scheduler phase，也不能证明电路因果链。
原 unknown fatal 保留，仍未通过完整功能、150MHz 或能耗资格。

本地重新运行 175 至新临时目录，两个输出 JSON 与原 175 输出逐字节相同。
复核脚本另用独立字段解析器直接读取原 simulation.log 并按 aval/bval 解码四态；同时复核 174 包全部成员字节和 175 manifest。
634 项服务器原件只比较已有身份回执；未返回的文件没有被宣称已在本地重新哈希。

建议的最小后继：同 ownS2c `9c16…` 图、自己 SDC/明确冻结时钟方法及相同库上，唯一枚举目标 cell 和 D/CK/Q/RDN，查询 D 驱动、CK 源与完整 native min-delay 数据/时钟路径。
实例组件 `dp_gt0.vec_31_dfflr` 含字面点，不能全局 dot→slash。服务器只读核对同单元模型的 specify/UDP 与哈希，区分库模型 VCS hold 告警与真实 STA/SDF 证明。
遇到未观察或有状态边界继续保持因果未证明。无需先改 TB 采样、屏蔽 timing check、force/初始化或插入任意 delay；新 native 工作仍通过原总控单槽执行。

复现：

```sh
python3 -B build/xu-s2c-observation175-review/review175.py
```

`review175.json` 是复核回执，所有结果继续标记 `NOT_QUALIFIED`。
