# Postflow 便携证据包

最终归档：`s3-y32-postflow-evidence.tar.gz`，19,754,180 bytes（约19.75 MB）。
SHA256：`ab4a84301dd8c2a797ce48c199b7b7daf47780e4875f627ca90f236962fa1138`。

包含17个完整campaign、两次最终12层、unit/真实wrapper/背压/错误/复位、
原始失败fixture日志、源码patch/review/完整SHA pairs、strict comparisons、
首请求等待7拍receipt、最终报告和计划。每个campaign保留source、vectors、
ELF、加载图像、soc_sim、构建/版本/raw日志和plan/result。

已在独立路径 `verify-relocated/s3-y32-postflow-evidence` 解包并通过：

- 4,794个文件、逐文件SHA与原始provenance/权限、17个campaign的source/image/log/vector等核验。
- 6份严格比较重新执行通过，含选中方案12层 `payload+clear` 差值 **−282,744 cycles**。
- 搬迁后旧命令打印通过；只打印，没有再次运行仿真。
- 包内最终报告、计划及工作树原件均与父仓提交 `29081f1` 字节相同。

```
sha256sum -c archive.sha256
mkdir unpacked
tar -xpzf s3-y32-postflow-evidence.tar.gz -C unpacked
python3.12 -E -B unpacked/s3-y32-postflow-evidence/verify_evidence.py
python3.12 -E -B unpacked/s3-y32-postflow-evidence/revalidate_comparisons.py
```

使用 `-p` 保留原文件权限。Python `data` 解包过滤器会主动删除组写权限，
不适合核验原mode精确相等。

完整收据：`archive-verification.json`、`relocated-verification.json`、
`relocated-comparisons.json` 及对应 `.log`。
首版打包helper把native_layer误当campaign目录导致校验失败，已修复，
旧helper、精确一行差分、首归档SHA与失败只读复现位于 `packaging-diagnostics/`。
该失败仅属于打包helper，原始campaign、生产源码、报告与计划从未被修改。
硬件fixture初始失败仍按原日志保存在包内，不能记为通过。

这是二态Verilator开发证据；没有新增综合、PPA或官方验收结论。
独立Git bundles与最终外层交付说明由主任务生成，不嵌入自引用归档。
