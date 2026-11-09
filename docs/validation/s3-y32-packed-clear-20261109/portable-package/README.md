# S3-Y32 PACK32真实清零交付

本轮在原READY＋stream＋bias方案上，复用现有PACK32公共MMIO端口完成相同真实清零。12层304,128个Y32输出逐位通过；计入clear总周期7,487,304→5,908,104，减少21.0917040%。payload每层多1拍已计入，收益来自清零事务减少，没有矩阵吞吐或PPA提升声明。

[完整报告](../../../docs/s3-y32-packed-clear-results.md)说明物理工作、非零前态探针、失败和资格边界。源码/数值/RTL不变性、所有25个最终native探针、60输入快照、4份campaign、3次严格比较及全部负例保存在不可变复现包中。

- 包：`s3-y32-packed-clear-evidence.tar.gz`，12,764,162 bytes。
- SHA256：`2e1edd2cb7e0467244b7b9e39c2f072e35b6521ef08d8c41fca8890a32c53630`。
- `assembly.json`、`archive-verification.json`、`final-seal-receipt.json`记录封包及异目录核验；`SHA256SUMS`列各交付摘要。
- 已在新目录保mode解包，1,596个manifest文件、1,590原件身份、4campaign及3项严格比较重验通过，未重跑仿真。
- `verify_evidence.py`核字节/模式/source/image/vector/log身份；包内`revalidate_comparisons.py`重新执行精确C/TB生成和独立ELF→image验证，结果与原保存比较一致。

只SRAM模式用于正式候选开发测试；可选寄存bias变体因未提供生成RTL而明确skip。原始失败fixture、638f中间helper、故障RTL副本均单独保存，不冒充最终PASS。未综合、未推送。clear政策REVIEW_PENDING、FIFO payload physical zero UNPROVEN保留。

父实现提交`67397ad`、文档提交`fb391f92788df622cb7b1f1e56a94e82d39da3a8`；E203仍`0f852a35741881400a7e10b4760bdb8f300245ae`。后续父仓库Git bundle及根代理独立迁移收据在此目录另行交付，不改变已冻结复现包。
