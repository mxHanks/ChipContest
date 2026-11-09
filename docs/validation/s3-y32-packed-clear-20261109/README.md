# S3-Y32 public PACK32 clear：紧凑 Git 证据

本目录按原字节保存 READY 基线、packed 清零先导、最终单层和最终 12 层的
plan/result、真实清零 C/recipe、每层原始仿真日志，以及严格比较工具、源
pins/pairs、限定回归、失败诊断和封包验证收据。`.gitattributes` 禁用换行转换；
`provenance.json` 记录原路径、大小和 SHA256，`sha256.json` 可逐项复核。
当前收齐状态以 `collection-summary.json` 为准。

- `campaigns/baseline-ready-full12/`：上一轮 8 PE READY＋偏置流水线基线。
- `campaigns/packed-task0-pilot-observer/`：首次真实 SoC 先导，之后加强每次
  PACK32 响应退休的物理写完成断言；保留先导，不用于最终源冻结结论。
- `campaigns/packed-final-task0/`：最终 helper 冻结后独立重建的单层筛选。
- `campaigns/packed-full12/`：集成后的独立冻结完整 12 层；仅 owner 确认结束后收集。
- `summaries/`：严格工具、源 pins/pairs、比较、源冻结、测试和设计诊断。
- `proofs/`：真实 wrapper 非零前态清零、错误／背压／复位、物理故障注入和
  比较器负例。预期拒绝、fixture 修复及实际失败都保留原日志。
- `portable-package/`：完整大包 SHA、封存与独立重验证收据；最终封包前保持 pending。

packed16-mmio 只通过已有公共 PACK32 MMIO 接口真实写零，不改 RTL、旧 scalar
helper 或 payload 固件／observer。SRAM 模式含 8 次读、8,252 次写、8,260 次
命令和响应；真实覆盖 16,384 个 W 半字、64 个 X 半字、768 个 bias SRAM 字、
legacy bias 与 staging。每次 pack 响应与实际 core/SRAM 写事件逐次对齐；fence
后 STREAM_STATUS、STATUS 都为零，再进入原 payload。source request 以 VALID
进入计时，等待也计入；生成 C 布局变化导致 payload 的 +1 周期原样保留，不加
padding 调相位。

成功状态仍是 `DEVELOPMENT_PASS_POLICY_PENDING`：Verilator 二态开发证据，
150 MHz 为测试台刺激；未运行综合、PPA、STA、能耗、VCS／门级或官方验收。
`REVIEW_PENDING` 清零政策与 FIFO payload physical zero 的 `UNPROVEN` 保留原义。
`failure-log-index.json` 仅定位包含失败文本的原日志，须结合注错上下文阅读。

紧凑目录不含 ELF、加载图像、原生模拟器、完整向量、source/RTL 快照或编译
对象，不能单独运行仿真。完整包位于
`build/packed-clear-20261109/handoff/s3-y32-packed-clear-evidence.tar.gz`。
封存后核对 archive SHA，再使用包内 verifier 和比较器重验证工具只读复核。

`assemble_compact.py` 默认只收 owner 已确认结束的 helper 回归，跳过活动 full12 和封包；
owner 宣布所有原件结束后执行 `python3.12 -E -B assemble_compact.py --final`。
脚本检查复制期间大小／mtime 与目标 SHA，原件变化则失败；不修改任何原件。
