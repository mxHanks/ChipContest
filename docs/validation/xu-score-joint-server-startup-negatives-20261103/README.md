# xu 联合活动实际服务器启动负例

这里保留 actual micro23 和 prepare31 失败原件；两者均未进入完整 VCS 活动采集，不能作为活动或功耗验收。

- micro23 在真实服务器的 GCC 严格编译阶段失败。实际 VCS `vpi_user.h` 第1132行旧式 `vlog_startup_routines` 声明触发 `-Werror=strict-prototypes`；未执行 VCS build 或 simulation。实际头文件只记录hash和诊断，未复制其内容。后续独立 micro34 将第三方目录分类为 system header，保留自身严格警告及system依赖冻结；host证明见另一目录。
- prepare31 的调用 `--netlist` 路径少了候选输出中的 `/s2c/` 部分，严格regular input guard正确拒绝。失败在实际固件/alias准备后、VPI编译之前。不是 RTL、VCS或vendor宏功能失败。后续独立 prepare36修复调用路径；其执行结果须另验。

`raw/` 是 export33 中这三组23个文件的完整字节集合。大于100KB的 alias SV仅作lossless XZ压缩，原路径/解压size/SHA保留在 `compressed-originals.json`。源export完整manifest作为元数据保留，未把其中其它未归档组宣称为本证据的一部分。`evidence-tools/` 固定实际micro23 helper和相关C/SV，SHA需匹配实际state声明。原始日志空白不改。

离线复核：

```sh
python3 docs/validation/xu-score-joint-server-startup-negatives-20261103/evidence-tools/recheck.py
```
