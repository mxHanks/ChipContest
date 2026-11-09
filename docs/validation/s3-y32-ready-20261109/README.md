# S3-Y32 READY：紧凑 Git 证据

本目录保存四次 campaign 的原始 plan/result、真实清零 C 与 recipe、每层原始
仿真日志，以及严格比较器、完整源 SHA pins/pairs、负例、限定回归和归档验证
收据。原件按字节复制，`.gitattributes` 禁用换行转换；`provenance.json` 记录
每份原件的路径、大小与 SHA256，`sha256.json` 覆盖本目录其余证据（清单自身和
统计文件除外）。具体收齐状态见 `collection-summary.json`。

- `campaigns/baseline-selected-full12/`：上一轮 8 PE stream＋偏置预取流水线基线。
- `campaigns/ready-task0-failed-before-fence/`：初版缺少前置 fence，真实 SoC 的
  STARTROW 响应退休断言失败；保留失败，不计入性能结果。
- `campaigns/ready-fenced-task0/`：READY 专用前 fence 修正后的单层筛选。
- `campaigns/ready-full12/`：生产集成后独立冻结、重新编译的完整 12 层结果。
- `summaries/`：严格工具、源 pins/pairs、比较、设计及失败诊断。
- `proofs/`：单元、真实 MAC wrapper、背压/错误/复位、宏关闭加载字节一致性、
  parser 负例、限定测试与独立审查。
- `portable-package/`：大包封存 SHA、验证／重验证工具和 root 独立复核收据。

READY 0x24 沿用 stream descriptor，但每组预算计数 READY_WAIT 时钟边沿；
旧 0x20/0x23 的预算仍计退休状态响应。新指令的前置 fence 将 STARTROW 的
写响应排在 NICE 接受之前；原有后置 fence、memory clobber、返回码检查保留。
被动 observer 逐边沿核对 live metadata、剩余预算与低 claim，拒绝所有
ROW_STATUS 查询，保留逐 lane 黄金结果、下一边沿 POP、每次共享写响应、最终
写响应与 OITF 退休检查。零查询不代表零等待；以完整 payload＋真实 clear 的
周期比较为准，不把 phase 重分类或重叠活动计数相加作为收益。

所有成功状态仍是 `DEVELOPMENT_PASS_POLICY_PENDING`：Verilator 二态开发
证据；150 MHz 是测试台刺激。没有综合、PPA、STA、能耗、VCS／门级或官方资格
结论。clear policy 的 `REVIEW_PENDING` 与 FIFO payload physical zero 的
`UNPROVEN` 保留原义。`campaign-inventory.json` 不改写原始失败状态；
`failure-log-index.json` 同时可能列出预期注错、fixture 诊断与实际失败，必须
结合原日志上下文阅读。

本紧凑目录不含 ELF、加载图像、原生模拟器、完整向量、RTL/source 快照或中间
编译对象，不能单独运行仿真。完整便携包预计位于：

`build/ready-20261109/handoff/s3-y32-ready-evidence.tar.gz`

封存后先核对 `portable-package/archive.sha256`，解包按包内 README 运行
`verify_evidence.py` 和 `revalidate_comparisons.py`；它们只读校验证据，不启动
仿真。未出现最终封存、归档重验证及 root 收据时，本目录保持 pending。

`assemble_compact.py` 默认只收已结束的三次 campaign 与静态证明，跳过仍活动的
full12 和封包输出。所有 owner 确认结束后，使用 `python3.12 -E -B
assemble_compact.py --final` 最终刷新；脚本检查复制过程中原件大小／mtime 和
目标 SHA，遇到活动原件会失败。所有文件 SHA 可通过读取 `sha256.json` 逐项
复核。
