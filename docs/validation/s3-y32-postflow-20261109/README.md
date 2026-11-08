# S3-Y32 后续优化：紧凑 Git 证据

这里只保存原始 plan/result/clear recipe、每层原始仿真日志、严格比较与源
SHA pins/pairs、限定测试日志、结构补丁和路线评估。所有原件按字节复制；
`provenance.json` 给出原路径、SHA256 与大小，`sha256.json` 覆盖本目录其余
证据文件（清单自身和统计文件除外）。本目录 `.gitattributes` 禁用文本换行转换。

- `campaigns/`：稳定 direct 8 PE/16 PE 基线、偏置流水化、批量16、组合、
  direct stream、旧固件兼容和完整12层结果。确切原状态见 `campaign-inventory.json`。
- `summaries/`：完整源 SHA pins/pairs、严格比较器及负例、集成源核对、
  单层对比和双缓冲/两行/DMA/41位累加评估。
- `proofs/`：独立单元、真实 MAC wrapper、错误/背压/复位、最终限定回归、
  原失败诊断和源改动差分。
- `portable-package/`：大包验证与重放工具、清单及封存时可用的归档 SHA。

全部 PASS 都只表示 `DEVELOPMENT_PASS_POLICY_PENDING`：Verilator 二态开发
证据，开启 `--assert` 并保留 Chisel 断言，vendor SVA 关闭；150 MHz 是测试台
刺激。没有综合、面积、STA、能耗、VCS/门级或官方资格结论。原始 clear policy
`REVIEW_PENDING`、FIFO payload physical zero `UNPROVEN` 保留原义。

`failure-log-index.json` 原样列出含失败/异常诊断的日志；失败运行、fixture
修复前输出和注错测试的诊断都不能充当成功测量，需结合原日志上下文。
后续修复成功不覆盖其原字节。完整周期收益以 payload + 真实 physical clear
为准；clear 到首请求间隙另列，不能把 phase 重分类或重叠计数加成收益。

本紧凑目录不含 RTL/source 快照、完整向量、ELF、加载图像及原生模拟器，
不能独立重新验证所有可执行工件或运行仿真。完整便携证据包位于：

`build/postflow-20261108/handoff/s3-y32-postflow-evidence.tar.gz`

解包后按包内 `README.md` 运行 `verify_evidence.py` 和
`revalidate_comparisons.py`，它们只读取证据而不启动仿真。封存归档 SHA
见 `portable-package/archive.sha256`；若尚在收齐，见 `collection-summary.json`
的 pending 列表。不得将仍为 RUNNING 的结果视作完成。

归档校验工具首版误将原层号当作进程内层号，曾定位错向量目录；原失败日志、
helper字节与差分、初始归档SHA在`portable-package/packaging-diagnostics/`保留，
不计PASS。解包需保留权限（`tar -xpzf`）；Python data-filter 会去掉组写权限，
会触发权限一致性检查。最终包及独立新路径的字节／权限校验、六项严格比较
收据见`portable-package/`，原campaign未因修正归档工具而改变。
