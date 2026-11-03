# xu bank128 PPA 工具本地验证

`raw/host-ppa.log`：63 个 host PPA tests 通过。包含既有 profiles 的 template、mapping identity、宏检查 Tcl 逐字节连续性，以及新 geometry/library/adapter/define/main pin 和 official-model path/bytes/SHA 拒绝测试。

`cli-generate.log`、`cli-prepare.log`：对实际冻结候选 f75880d / child 52cfbea 执行真实 CLI，使用三份标记为 HOST ONLY 的 dummy DB 得到 164 个 SV 输入及 448 个宏的未资格配置。源码、定义、库列表、宏组和 producer SHA 绑定在原始 manifest。`host-*.db` 仅为复现接线准备的无效文本，不是实际工艺库。

此目录没有 DC/PT/面积/时序/能耗验收结果。官方商业128模型未复制，仅固定已观察的官方路径及原始 bytes/SHA。服务器 actual acceptance 和 PPA 日志由独立 campaign 交付。

离线核对：`python3 docs/validation/xu-bank128-ppa-host-20261103/recheck.py`。重跑 host checks 与服务器命令见 `docs/xu-bank128-ppa.md`。
