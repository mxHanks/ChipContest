# 全 SoC 功耗审阅

当前尚无已验收功耗或选型数值。原 PID 299096 及原 PT 已自然退出；`tight-O2-ss/receipt.json` 记录 native_exit=124、complete=false、seconds=2400.007，SHA256 `bd765e8f210b9faf07e9e6e92ada22d31f81ce133b6b0d97eebf9d55940eb479`。原失败证据和 `xu-b41-power-r1.py` 均保留，不重跑旧控制器。R16 正连续完成两份剩余门级，随后串行测量必要功耗。

按用户最新优先级，正式比较只要求指南评分边界内的 12 段 payload 全 SoC 功耗。clear 的功能及周期证据保留，额外 clear+payload 功耗不再作为收尾依赖。下文的 24 段定义为原失败方案的口径记录，不表示已取得有效结果。

## 已核对的采集定义

每份固件要求完整 12 个 D4K_TASK_PASS 和 D4K_SOC_PASS，才选取对应原生日志与 VCD；部分通过的 R14 不满足该条件。物理网表固定为 2d5adc61…，官方 SS 库由既有 execution.json 中的路径及 SHA 绑定。

对 12 个非 warmup 任务，将原生 GATE_EVENT 的绝对纳秒时间戳与 D4K_WINDOW 周期计数配对，独立检查周期约为 6.666666 ns，clear 和 payload 的推导周期一致。每任务采集两个闭合周期窗口：

- clear_request 至 clear_done + 一个周期。
- first_request 至 last_y_response + 一个周期。

任务间 gap 和软件上报不包含在该合集内。既有输出 total_principal_ns 是全部 24 段 clear+payload 的时长之和。它不是 payload 单独的时长，也不是含 gap 的连续墙钟区间。

脚本使用 averaged 模式，对完整 SoC 的 tb_dma64_soc/dut 读入上述时间段，输出 units、check_power、switching、power、hierarchy-power 及 power-attributes TSV；原生成功后才在 windows.json 写入 output_sha256。完成标记仍要求人工审阅覆盖和单位，不能把它直接当成功耗验收。

已通过官方安装自带的 `doc/pt/man/cat2/read_vcd.2` 核对：-time 接受递增的偶数长度浮点列表，各成对元素表示窗口，单位为 ns。当前 24 段导入方式符合这一语法。没有仅凭对命令的记忆作推断。

## 后续必须完成

1. 完成三固件完整门级，审阅输入、输出、VCD 与 gate log 的绑定；旧控制器自然终态已确认。
2. 对应指南从输入/参数开始装载的计时边界，测量同一 VCD 的 12 段 payload；不再要求重复测 clear+payload。
3. 审阅完整 SoC、E203、互连、加速器及 337 SRAM 的活动映射、未知/默认活动、泄漏和动态功耗、单位及库模型；未标注或未建模部分不能计零。
4. 用同一窗口总时长和平均功耗复算平均单任务能量；如仅取得合集平均功耗，不将其伪装为各层独立测得的功耗。
5. 三固件同配置比较后冻结所选固件，保留精度、开发夹具与正式评测范围说明。

payload 补测脚本已在服务器本地由既有脚本适配为 `xu-b41-power-payload-r1.py`，6,314 字节，SHA 前缀 0fca06fa；尚未启动。输出独立放在 xu-power-payload-20261113-r1。它要求原控制器的开始标识已消失、三份 R15 verified-binding 的配置相同且 full12/warmup/13 clear 齐全、三份原 clear+payload 功耗输出 SHA 齐全；复核 native log、VCD 大小与流式 SHA 后，再测 12 个 payload 时间段。实际 f.execute 的 AST 锁范围为第 79 行。

上述旧补测脚本及窗口 helper 均未启动，因依赖旧功耗或未成功的裁剪输出，不作为当前入口。当前准备直接从保留原波形使用厂商 `vcd2saif` 的重复 `-time` 窗口，随后原生 `read_saif`。小型原生预检已证明时间参数单位为 VCD 的 fs，且 disjoint 窗口可累计；跨 dumpoff 会缩短 SAIF DURATION，故正式入口必须逐份核对 DURATION 等于全部评分窗口时长。边界切换计数尚需与原生直接 VCD 导入一致性核对，未通过前不能将转换结果作为有效功耗。

## 当前已排队入口

服务器 08:10，`xu-b41-power-payload-r3.py --launch` 返回 PID 160819；08:11 日志为 WAIT_GATE_R16_NATURAL_COMPLETION，未启动并发 EDA。脚本 4,664 字节，SHA256 `46e2c0586463fdbcc7fbc3d47ae99b7e30706a327787c4c429d8e9b87f0629d5`；helper 13,474 字节，SHA256 `ecc6be2b6da2a36997513543f64e2815030629450775eb63e2d82d1801f3b72f`。父脚本 SHA256 `473fd0c2ed3e7662638f4e9dab60b47eb8f6262df21025bb2f93cea452cc0b26`，原脚本保持原样。

新入口只在整轮 R16 自然完成后启动，并复核三份同配置 gate binding、独立 r2 复算、原始日志与固件身份。12 段 payload 的原绝对时间戳及逐任务周期推导保留；转换时间按原 VCD 1 fs 分辨率就近取整，每端误差不超过 0.5 fs。厂商 SAIF 的 toggle_rate、static_probability、x_probability 必须与原生 VCD 导入的边界夹具相符，否则整轮使用直接 VCD。转换失败或 DURATION 不符也直接回退，不手工修正切换计数。

原生 PT 与厂商转换均受原 eda.lock 和本账号实际重任务扫描保护。新增报告包含 337 个宏的逐实例四类功耗、活动库存、未标注和默认活动；它们用于后续实际覆盖及单位审阅。输出根为 `xu-power-payload-20261113-r3`，当前尚无有效功耗数值。直接导入上限扩为 14,400 秒，避免沿用已确认不足的 2,400 秒限额。

## 宏功耗模型与任务工作点

服务器只读核对的同角公开源模型为 `RAMSP1024X16_ss_0p99v_0p99v_125c.lib`，230,114 字节，SHA256 `7375bbc68c8a5e396c8f69c722f5b487c6b41dc2e1f3789a1d9c92fe516422a6`。其中有 80 个 internal_power、80 个 rise_power、80 个 fall_power 和 4 个 leakage_power 组；time_unit=1 ns、leakage_power_unit=1 mW、capacitance=1 pF、nominal voltage=0.99 V、temperature=125°C。实际链接仍以 execution.json 内已校验的 SS 标准单元及 SRAM `.db` 为准；原生报告还须确认全部 337 宏及其实际非零模型输出，源表存在本身不代替覆盖验收。

门级 TB 的 bootrom_n 固定为 0、dwakeup_n 固定为 1，erst_n 接 rst_n；rst_n 最后一次释放在第 954 行，正式任务期间保持 1。四个低频 unknown 的补充工作点因此限定为任务执行期间 bootrom_n=0、dwakeup_n=1、erst_n=1，启动阶段异步释放另行明确范围。

最终能量采用 `P_payload_avg × T_payload_total / 12`，其中平均功耗和总时长对应完全相同的 12 段合集；不将合集功耗填写为各层独立实测值。

## 独立复算版本接续

phased 的原生计时与冻结 RTL 有小幅差异，R2 额外的跨模型常量比较失败。新 R3 保留原始功能与解析不变量、实际时钟和窗口预算，改为记录全部差异，并通过同一原件重放。phased 实际 payload=416,580 周期，功耗控制器继续从实际 GATE_EVENT/窗口推导时间，不能填入 RTL 的 416,568 周期。

已排队控制器不改动或重启。其稳定 R2 campaign 引用以带来源的符号链接指向新 R3 原件，内容 SHA 相同、reviewer_version 与源程序 SHA 明示；tight 原 R2 回执保持原样。backoff 的同版复算已排队，在绑定封存后完成相同发布。详见 REVIEW-CONTRACT-CORRECTION.md。当前仍无有效功耗数值。
