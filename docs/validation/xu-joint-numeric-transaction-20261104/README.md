# xu 联合采集事务编码调整与本地验收

生产改动提交 `f0341fad21a3735647fd946d0517cddb16256dd8`。这里归档的
实际服务器 string probe56 原件来自已严格校验的 export60；不改动
capture36 的损坏头部、不重新解释其原字节。

实际 `simulation.log` SHA256 为
`e65e2ec32fbb39794695184e755943308d791042a864bae2139cec380e8123b7`。
18/18 实参读取组合全部逐字节正确：动态 `$sformatf`、保存的 SV string、
字面量分别按三种 handle/求值顺序读取。因此 probe 没有复现36的损坏，
不能认定 `vpi_scan` 顺序或简单临时字符串寿命已被证明是根因。

新 API 改用实际边界处的已观察整数。C 即时复制四态向量值、拒绝 X/Z，
在自身缓冲区生成 ASCII；task、源地址范围、读/valid/ready、最终地址、
写回数和请求/退休周期顺序均检查。S2c 仍在原 `$toggle_start` 后与
`$toggle_stop` 后的同一 procedural event 调用，后处理仍核对冻结
REQUEST→final-Y-RETIRE 日志与原 SAIF ticks，未更改十二任务窗口。
原字符串 API 保留；DUT/Chisel/RTL、数值格式、MMIO ABI、向量未改。

本地结果：实际 C/Icarus 联合记录器10项通过，包含352宏计数、原回调
顺序/四态/篡改拒绝、新整数事务一项正例与四项拒绝例（X/Z、错task、
错误请求/退休顺序、错写回数）；带冻结 S2c 源树的 collector 集成10项
全部通过，包含336宏/22,512路径 elaboration、固件生成和身份防篡改。
Python 3.6语法检查通过。原始日志及 SHA/字节数见 `manifest.json`。

复现命令，在干净已提交工具树执行：

```sh
XU_JOINT_TEST_EVIDENCE="$PWD/build/xu-joint-numeric-host" \
python3 -m unittest discover -s tests/host -p test_xu_sram_joint_activity.py -v

XU_S2C_SOURCE_ROOT=/home/mxhanks/Projects/ChipContest-xu-s2c-autogroup \
XU_JOINT_COLLECTOR_TEST_EVIDENCE="$PWD/build/xu-joint-numeric-collector" \
python3 -m unittest discover -s tests/host -p test_xu_candidate_joint_task_activity.py -v

python3 tools/ppa/xu_joint_activity/xu_joint_numeric_smoke.py \
  --out /path/to/new-numeric-smoke62 \
  --vcs /path/to/same-vcs/bin/vcs --include /path/to/same-vcs/include --cc gcc
```

最后一条服务器 smoke 此归档时尚未执行；其结果必须另行收取。
该 smoke 只使用一个合成 pin fixture，周期数字用于参数传递检查，
没有 vendor SRAM、full SoC、SAIF/PT 条件弧或能耗验收。新 full-SoC
采集必须使用独立新输出；当前生产后处理仍需避免一次性读取12GB
sidecar，不能把既有离线流式审查当作新采集完成。
