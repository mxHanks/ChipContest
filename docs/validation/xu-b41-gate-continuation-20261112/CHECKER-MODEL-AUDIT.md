# 门级检查器与厂商模型审阅

官方根目录为 `/tmp/xu-b41-close-20261111-r1`。原件留在官方服务器，本文由工作区 3 界面读取后整理。

## 厂商 SRAM 物理布局检查

目录 `xu-vendor-preload-20261112-r1`：compile、run 均原生退出 0，当前日志 SHA 与 receipt.json 一致；测试台、VCS 工具、官方 RAMSP1024X16.v 当前 SHA 与回执一致。

原生终态：`XU_VENDOR_PRELOAD_PASS words=1024 four_state_x_words=4`。检查覆盖全部 1,024 地址和 4 个四态未知字，验证 256×64 物理数组中地址低两位选列、数据位 b 对应物理位 4*b+column 的夹具映射。该检查不代替完整 SoC 的真实 DMA 事务、清零、输出或全部 SRAM 的活动覆盖。

厂商模型 SHA256：`81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51`。当前门级使用同一模型。

## 六处 CPU SVA 的展开映射

`xu-gate-20261112-r1/cpu-checker-mapping.json` 共 428 项映射、430 个展开断言：

| 冻结模板位置 | 实例/映射项 | 展开断言 |
|---|---:|---:|
| e203_exu_alu_muldiv.v:552,572,614 | 1 | 3 |
| e203_exu_commit.v:335 | 1 | 1 |
| e203_ifu_ifetch.v:544 | 1 | 1 |
| sirv_gnrl_xchecker.v:41 | 425 | 425 |

已逐项对照冻结源的三个 muldiv 检查、halt/flush onehot、IFU valid 无 X、通用使能无 X。门级 golden 算术由实际 muldiv 输入重建，第三条仍与实际 `muldiv_o_wbck_wdat` 比较，未将实际结果换成参考自身。主测试台包含 cpu-checkers.svh。

门级适配断言增加统一的 `!startup_complete` 启动禁用条件，不能称为逐字未改。测试台先装载/验证 ITCM、执行芯片原生复位启动，等待 rst_core 确定为 1，再经真实外部复位拉低 120 ns，确认 rst_core 为 0，随后 `startup_complete=1; rst_n=1`。此后检查始终开启，覆盖 CPU 正式执行、warmup、13 次清零及全部任务；启动前阶段另有 10 ms 超时和复位到达检查。原冻结 RTL SVA 与其原件保持不变。曾发生的运行期 checker 135 失败未被此启动条件掩盖，已保留在诊断记录中。

主测试台的完整输出比较与本轮既有 85 个 fatal 调用保留。已逐条索引冻结 TB 的 52 条原失败消息：51 条有直接门级对应位置，唯一没有同名调用的是 `public fixture port error %h`。该调用检查原 RTL 独立测试夹具端口的 host_rsp_err；PPA 顶层不包含这一端口，夹具通过厂商物理数组装载和读回，不能虚称门级仍执行了该端口响应检查。

已对全部冻结夹具地址调用及邮箱安全上界共 65,735 项验证：均在 0xa0000000..0xa007fffc、4 字节对齐，仲裁器将 4'hf 正确放入地址位 2 选择的半字，满足原共享端点的 size_ok、range_ok、cpu_mask_ok。原端点 rsp_err 为 !legal，因此该端口检查在这些固定夹具调用中不触发。证明来源和范围见 fixture-legality-scope.json；它不授权任意非法夹具地址，也不替代 DUT 的 DMA 错误检查。

物理夹具保留无效 bank fatal、ITCM 物理装载验证、所有结果四态读回、夹具访问计数/范围及禁止与计时任务重叠的检查。实际 `firmware error code %h` fatal 仍在。官方映射回执 `xu-fatal-mapping-audit-20261113-r1.json` 保存 51 条原消息、对应门级行号、两端测试台 SHA 和这一夹具结构差异。消息索引是定位依据，信号/连接适配的证明仍见独立映射和整体等价原件。

综合后别名空洞仅按实际连接证据映射，当前测试台与检查器 SHA 已绑定在 R15 预检中。
