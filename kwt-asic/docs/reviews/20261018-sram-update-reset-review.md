# SRAM overwrite/reset 定向资格化独立审查

日期：2026-10-18。结论：**PASS，限开发功能与检查器资格化；未发现阻断本轮结论的问题。** 官方宏功能仍为 **NOT_RUN**，官方 PPA 为 **BLOCKED**；核心、SoC、综合均 **NOT_RUN**。三后端签名一致不构成真实宏、指定工艺或全部地址/输入的证明。

本审查只读检查源码、JSON、原生日志及状态，并用独立标准库 Python 重算 SHA、来源身份、地址集合、计数和签名；没有运行 harness、主机测试、HDL、EDA，也没有改生产源码或既有证据。唯一新增文件为本审查记录。

## 已审查的冻结证据

- 资格化入口：`artifacts/diagnostics/20261018-sram-update-reset/qualify.py`。
- 父结果：`artifacts/diagnostics/20261018-sram-update-reset/final-v1/result.json`，SHA-256 `4d3ccdd89e0a23b3c9eea18e7ebbcd9a7f4670add17ee5599e276608815d1576`；父 source_id 为 `f1acc54759aae1a87127f479a8cf955df3f071744147ab1f554793fd4288fc7a`。
- 测试台、runner、主机解析器测试：`sim/tb_kwt_sram_update_reset.sv`、`scripts/verify/run_sram_update_reset.py`、`tests/test_sram_update_reset.py`。
- 父结果引用的五份完整子报告，以及其中全部输入、私有故障源、二进制、命令日志和 `.command.json`。

| 子运行后缀 | 结果 | 实际内容 |
|---|---|---|
| `052753.181129Z…efa3b73b` | PASS | 默认 BACKEND 0/2，16 case、720 个分组检查、8 组 MATCH |
| `052753.959231Z…37aa22df` | PASS | 显式开发 BACKEND 0/2/3，24 case、1080 个分组检查、8 组 MATCH |
| `052755.037720Z…cb3bbd34` | FAIL，预期拒绝 | 丢弃同址后续写，实际 vvp exit 1 |
| `052755.160180Z…1ec7a853` | FAIL，预期拒绝 | reset 写使能泄漏，实际 vvp exit 1 |
| `052755.285672Z…5ea75a38` | FAIL，预期拒绝 | reset 读使能泄漏，实际 vvp exit 1 |

完整子目录均位于 `artifacts/runs/20261018T<表中后缀的时间>-sram-update-reset-<末尾ID>/`；精确绝对路径及 SHA 以父结果的五个 `reports` 记录为准。

独立复核六份 identity：按去掉 source_id 的规范 JSON 重新计算，六个 source_id 均相符，磁盘 `source_identity.json` 与内嵌对象相同。共核对 **502 次文件记录、307 个唯一绑定文件**，当前 SHA-256 和 size 全部相符。父报告及五个子报告中的 **103 条唯一原生命令**，其磁盘状态与报告的 argv/cwd/log/status/exit/timeout/interrupted 相符：97 条 exit 0；6 条预期 exit 1 是三个故障 CLI 及各自 vvp。全部为 EXITED，均无 timeout/interrupted。

五个 CLI 日志均只有一次 `KWT_SRAM_UPDATE_RESET_COMPLETE` 和一条结果 JSON，引用报告与父记录一致。40 个正常仿真均有唯一、形状正确的 PASS 和 `$finish` 结束信息，编译/运行日志无阻断诊断。每个故障均只有一个符合预期阶段的 FATAL，且没有正常 PASS。`host.log` 完整结束于 `Ran 246 tests` / `OK`；`verify.log` 有 static/reference PASS，原生命令均 exit 0。此处复核既有执行证据，没有重跑。

## 覆写、复位与计数审查

1. **真正不同值覆写成立。** 测试台 146–158 行先写 A、读回确认，再写全 WIDTH 补码 B 并读回确认；比较使用四态 `!==`。每个选址的所有有效逻辑位均翻转，涵盖 40/41 位 bank 最后切片中的有效位。`flipped_bits` 必须全 1。未将物理补零位或全部地址覆盖算入结论。
2. **地址包含首末及每个现用物理 tile 边界两侧。** TB 使用 tile 除余公式，runner 52–64 行使用剩余容量递减法；审查另以 4096/1024/128 容量分解重建，结果如下。
3. **reset 期间 enable 跨多个 posedge。** 160–182 行保持 wr_en 高，每个选址至少两个上升沿尝试不同数据；禁用写后再释放 reset，并逐个读回确认 payload 保留。184–202 行持续 rd_en 高、改变地址，每个地址两个上升沿检查 valid=0 且 Q 保持。204–222 行另验写使能持续到释放，首个有效上升沿写入新值，并读回确认。
4. **短 reset 无上升沿。** 224–240 行先产生已知 Q/valid，再在 negedge 后发 2 ns 低脉冲，以独立 posedge_count 确认脉冲及释放检查间没有上升沿；异步 valid 清零、Q 保留，并回读所有选址。持续读/写使能情况下释放后的首个有效上升沿接受请求，由前述两个释放场景验证。短脉冲场景本身使用低使能，不能据此宣称已覆盖任意 enable 与短 reset 的全部相位组合。
5. **未知初始 Q 不会被当成有效数据。** `q_known` 在成功四态读回前禁止 hold 比较；写阶段只有已知 Q 才检查保持。正常读、保持和 valid 均用 `!==`，X/Z 不会被普通二态相等比较漏过；初始 payload/Q 不要求清零，也不读取未写单元。

| 形状 | 选址顺序 | N | 每后端分组检查数 |
|---|---|---:|---:|
| unit 16×128/1024/4096 | 各自 0、DEPTH−1 | 2 | 各 25 |
| bank 16×3136 | 0,3135,1023,1024,2047,2048,3071,3072 | 8 | 73 |
| bank 16×3200 | 0,3199,1023,1024,2047,2048,3071,3072 | 8 | 73 |
| bank 16×2048 | 0,2047,1023,1024 | 4 | 41 |
| bank 40×32 | 0,31 | 2 | 25 |
| bank 41×512 | 0,511,127,128,255,256,383,384 | 8 | 73 |

五组计数分别为 `2N, 3N+2, 2N, N+3, 4`，合计 `8N+9`。八形状每后端合计 360，因此默认为 720，显式三后端为 1080；计数不包含全部辅助断言。审查没有调用 runner 的 expected_counts：独立重建每次读/hold 的数据与 tag，按 64 位截断 fold 重算全部 **40 个正常 case** 的签名，逐一与日志/报告一致；三后端八组 MATCH 及默认运行对应签名也一致。

## 私有故障灵敏度及来源保持

逐字 diff 确认三个 `private_fault_primitive.sv` 只位于对应新 run 目录，并作为实际编译输入取代原 primitive；原 primitive 未作为该次编译输入混入。

| 故障 | 实际修改 | 单一 FATAL 的准确原因 |
|---|---|---|
| overwrite-dropped | behavioral payload 增加首次写位图，后续同址写丢弃 | `UPDATE_RESET_READ phase=overwrite-B address=0`，got=253c / expected=dac3 |
| reset-write-leak | 仅 BACKEND=3 的 wr_en 去掉 rst_n gating | `UPDATE_RESET_READ phase=payload-after-reset-write address=0`，got=253c / expected=dac3 |
| reset-read-leak | 仅 BACKEND=3 的 rd_en 去掉 rst_n gating | `UPDATE_RESET_HOLD phase=reset-read address=0`，valid=0，got=dac3 / expected=02f0 |

三者均编译成功后因预期功能错误退出，非编译失败、缺模块、超时或伪造 FAIL。私有源、二进制及未改原始输入均有已重核的 SHA 记录。故障实验只跑 unit16×128/BACKEND=3，证明这三个错误在该场景可检出；不扩展为每个 bank/后端、每类缺陷的穷尽变异测试。

`docs/runs/official-sram-contract-20261018.json` 当前 SHA-256 为 `5533650189b22c4d0c3f077af95febededc3c9269df9f63f3cd506c40f78737e`、221198 bytes，与 `artifacts/checkpoints/20261018T052232Z-39daf2-official-sram-contract-qualified/` 内实际索引副本逐字节相同；索引中的 **830 个唯一文件** 全部仍满足 SHA 和 size。旧来源索引及其中生产源/既有证据没有为本轮实验改写。

## 接受边界

接受新增定向开发覆盖与实际故障检出证据。BACKEND=3 使用显式开发夹具，内部复用 behavioral 模型；签名相符是逻辑契约及包装行为一致的证据，不是第三个独立官方 SRAM 模型。没有官方材料输入或官方硬件任务；没有新核心/SoC/综合/时序/PPA 验收。本轮不改变既有数值语义、payload/Q 保持契约或已记录的官方材料阻塞。
