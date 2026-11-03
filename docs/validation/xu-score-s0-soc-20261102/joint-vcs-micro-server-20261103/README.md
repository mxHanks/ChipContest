# xu 实际 VCS 联合活动微基准及未关闭差异

服务器 VCS 2020.03-SP2-6 实际编译运行 `vcs-joint-micro-20261103-19`：3项完整模式退出0，未结束 mode3 保留无完成 footer 并被整数 auditor 拒绝。该开放微模块只有1个宏、67 bit，并非指定 SRAM 或真实全 SoC 单任务；不产生能耗或时序资格结论。

`raw/vcs19` 是经 export22 manifest 校验的逐字节原件。`raw/icarus-same-d8` 是本地重新运行的相同 d8 C/TB；两个源码 SHA 与服务器 state 完全相符。完整 mode0 的67 bit 四态驻留完全相同，但 VCS 的875次回调与 Icarus 的878次回调不同：CLK 517/519次 bit 转换，Q[0,1,4,5,8,9,12,13] 各1/2次转换，差异集中于同时间戳 active/#0/NBA 刺激。mode1/2 原始 stats 逐字节一致。全部原件均保留，不把 Icarus 当 golden，也不把整数守恒通过当事件等价校准通过。

`derived/comparison.json` 保留全部16类转换差异；两套模式0/1/2均通过独立整数不变量审查，状态明确不表示 VCS/SAIF/PT/能耗合格。VCS19 没有同时记录 native SAIF，不能单凭该输出决定实际 SAIF 应采用哪个转换定义。

`probe23-inputs` 固定一个独立待执行实验的 b2 C、owner/实际端口 VPI trace、SV event trace 与 native SAIF TB/入口。它不修改旧19原件。其 host receipt 仅证明C编译和 Icarus试跑，未包含 VCS native-SAIF 结果；应由服务器另开 `vcs-joint-micro-saif-20261103-23` 收集再比较。微基准不写 DUT，不强制值，不修改原 SAIF。

复核所有保存的 SHA/size：

```sh
python3 evidence-tools/recheck.py
```

复现原19本地同源试跑的命令、工具版本和输出在 `raw/icarus-same-d8/receipt.json` 与 step logs；服务器实际命令在 `raw/vcs19/state.json`，不将这些旧绝对路径冒充本机存在。全部原始日志空白保持不变。
