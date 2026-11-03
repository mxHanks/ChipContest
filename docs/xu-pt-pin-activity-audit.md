# xu PT SRAM pin activity 离线审核

`tools/ppa/xu_soc_pin_activity_audit.py` 审核实际 PrimeTime 逐 pin 查询与已冻结的 measured SAIF 状态提取。它不调用 EDA、不访问输入里声明的服务器路径、不改写旧 SAIF/collector/power helper。输出的固定结论为 `PARTIAL_KNOWN_UNRESOLVED_REVIEW_PENDING`、`qualification=NOT_QUALIFIED`；命令成功只表示完成本次离线审核。

## 输入和运行

```sh
python3 tools/ppa/xu_soc_pin_activity_audit.py \
  --request /absolute/path/xu-pin-review.request.json \
  --out /absolute/path/new-xu-pin-review
python3 -m unittest discover -s tests/host \
  -p test_xu_soc_pin_activity_audit.py -v
```

输出目录必须不存在，其父目录必须已存在且为规范路径。所有输入均为绝对路径的普通文件，拒绝文件或父目录符号链接。request 必须包含下列精确字段：

```json
{
  "schema": "xu-pt-pin-activity-review-request-v1",
  "task_id": 0,
  "expected_macro_count": 336,
  "expected_pin_bit_count": 22512,
  "numeric_policy": "decimal-exact-with-print-and-binary32-hypotheses-v1",
  "files": {
    "probe_result": {
      "local_path": "/local/exact/result.json",
      "origin_path": "/server/exact/result.json",
      "bytes": 123,
      "sha256": "replace-with-original-64-lowercase-hex-digits"
    }
  }
}
```

`files` 必须完整包含 11 个 role，每项均使用上述四个字段：`probe_result`、`probe_tcl`、`pt_log`、`tool_version`、`units`、`before`、`after`、`inventory`、`measured`、`prepared`、`execution`。示例只展示一项，不能直接运行。预期 bytes/SHA 应来自先前已校验的原始导出 manifest/收据，而非读取待审核文件后为其重新“签认”。本工具验证这些值和收据间的引用一致性，不声称它们具备密码学身份认证或替代原始采集流程审计。

`origin_path` 是 provenance，只作精确引用比较；程序只打开 `local_path`。同名文件、点号与斜杠互换、方括号转义差异均不可用于替代实际 pin。request 文件本身也在开始和结束时冻结。

输入契约为实际已使用的 `xu-soc-saif-power-prepared-v2`、`xu-soc-saif-power-execution-v1` 和 `xu-mapped-sram-pin-inventory-v1`。当前支持每颗恰好 67 位的 `RAMSP1024X16`；宏数显式声明并与 prepared、actual inventory 和查询行数逐项核对。其他宏引脚布局需要独立扩展契约，不能省略引脚后沿用此结果。

必须同时满足 terminal compact status、实际 PT exit 0、两个独立唯一完成 marker、精确工具版本和日志/Tcl/TSV/units 身份。原始功耗收据必须终态且该 task exit 0；原始 prepared/execution、mapped netlist、analysis SDC、实际工艺库及前后 input freeze 必须相互一致。prepared 与 PT executable 的 after-run SHA、原 task execution log 与 artifact 引用也需匹配。冻结 Tcl 的 `link_path`、`read_verilog`、`source`、`read_saif`/strip path 使用保守的实际唯一命令行格式核对；注释中包含正确路径不算加载证据，不求值任意 Tcl。功耗收据终态仍为 review pending，本工具不会将其提升为验收通过。

## 状态和比较

TSV 必须保留原始 9 列表头和 LF 换行：

```
phase desired_name reported_name toggle_rate toggle_source glitch_rate glitch_source static_probability static_source
```

分隔符为 TAB。每阶段的 actual inventory pin 恰好出现一次，`desired_name=reported_name`，phase 不可互换。每项 source 单独保留，支持安装版命令所列的 `file`、`propagated`、`default`、`UNINITIALIZED`、`create_clock`、`set_switching_activity`、`set_case_analysis`、`implied`。`-2`、NaN/Inf、非法负数、额外/缺失/重复 pin 和无效数值均为结构失败；`-1` 保留为未标注发现。安装版 man 的 time-based VCD 示例明确允许数值为 `-1`、来源仍为 `file`：来源已知而查询值尚未解析完成，需单列待审，不能据此称来源矛盾。来源为 `UNINITIALIZED` 却具有非 `-1` 值时仍单列不一致。此区别不把任何 `-1` 转成零。

measured 状态必须恰好 join actual inventory，保留 `T0/T1/TX/TZ/TB/TC/IG`；非负整数 dwell 总和必须等于正式任务 duration。未识别统计字段会失败，避免静默丢弃。原始路径必须为 prepared strip path 加实际 mapped pin 路径。程序审核的是先前冻结的 measured 提取文件，本次不重新解析原始 SAIF；该限制写入结果。

只有 `TX=TZ=TB=IG=0` 的位进入 known-only 数值计算：

- simple toggle：`TC × actual library time unit / (duration_ticks × SAIF timescale)`；
- static probability：`T1 / duration_ticks`；
- 无 IG 的 glitch rate 预期值为 0。

SAIF timescale 取正式窗口，并与 mapped bridge 收据精确核对；library 单位必须来自本次实际 `report_units` 中唯一的 `Time_unit : … Second`，不假设默认 ns。公式使用高精度 Decimal，保留原始查询文本、期望、差值和 count 等价误差。静态 0/1、零 toggle 与正值变成零单列严格边界判断，不能用粗容差抹平。

非零残差仅进一步区分“落在显示十进制最后位半个单位内”和“仍需 conversion 审核”。显示区间不是内部浮点误差容差，也不能证明整数计数相同。区间宽度达到一个 count 时明确标记 `INSUFFICIENT_TO_DISTINGUISH_ONE_COUNT`。

另记录一个对所有 pin 相同的经验假设：`binary32(binary32(binary32(TC)/binary32(duration_ticks)) × library_unit/timescale)` 再打印 6 位有效数字；SP 假设为已知 dwell 比率转 binary32，全部未知时尝试 0.5。其状态固定为 `UNIFORM_EMPIRICAL_HYPOTHESIS_ONLY_NOT_CONVERSION_PROOF`。它只帮助选择真实 PT 合成 probe，既不设逐 pin 自由容差，也不将命中数当作 conversion 证明。含未知态的 SP 或 TC 符合该假设，也不能表示物理状态已知或能耗为零。

## 产物和实测审核边界

新目录保存 request 原字节、逐 pin `pin-observations.jsonl` 和摘要 `result.json`。每个 pin 都保留实际库存属性、完整 measured 原统计、before/after 三项数值和来源、比较及待审理由。摘要包含各 source/分类计数、所有 phase 变化和 raw artifact SHA。所有输入在结束前再次核查；运行中变化只写 `failure.json` 并失败，不生成成功结果。未改写或补齐旧收据。

已对 2026-11-03 实际 compact 导出和对应 P6 measured/inventory 运行审核：336 宏、22,512 位（17,136 输入/5,376 输出），两阶段的三属性全部来自 `file`，phase 变化 0；known/no-IG 17,232 位，未知 dwell 5,280 位且均为 Q，其中 4,256 位整个窗口为 X。已知 0/1/零边界没有差异，非零打印/转换残差继续保留。该运行的原始证据和离线结果需由根协调追加到 validation 归档；不把 build 内暂存路径作为长期复现入口。

剩余审查包括：真实 PT 独立合成转换 probe、未知态与条件 Liberty internal/leakage power 的处理、标准单元覆盖和冲突映射、全 SoC 正式任务能耗以及完整 150MHz 时序。逐 pin 来源为 `file` 不能单独关闭这些资格项。
