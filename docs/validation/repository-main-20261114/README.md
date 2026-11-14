# 1064 修复候选：仓库交付验收

当前交付基于修复完成的 `be67e5d745cd7123e0def870f26be9a84263d759`，集成整理提交为 `b275f05d9dd5d6981432bd800f2e2a4d98d72633`，生产 RTL 固定为 `5470c5650f2d11d16e7c52cc96626d21030a3973`。本目录是仓库组织与复现入口的验收记录；时序与面积原件仍位于[最终 catch3](../s3-y32-ingress-perf-native-20261114/catch3/)。

## 实际验收

- 统一入口的 9 项标准库测试通过，涵盖证据/RTL 身份、错误选择拒绝、安全解包、拒绝覆盖、固定 CPU 参数，以及性能/面积元数据和原件漂移拒绝。
- 新增/更新导航的 12 份 Markdown 本地链接检查通过，`git diff --check` 通过。
- 独立从 GitHub HTTPS 克隆 main（无本地对象复用），父仓为 shallow main，子模块为完整克隆；父/子工作区均干净。
- 新克隆内顺序执行 `verify --submodule`、`ingress`、`vectors`、`check-vectors`、`unpack-mapped`，全部 RC0。入口探针接收/退休跨度为 1997/2002 cycles；12 task / 304128 输出的独立整数 MAC/RNE 校验通过。
- 最终提取网表 SHA256 为 `d83acb49caec51aabc66d8ad61b8784294bebe26c5458aa0b095f9d12a2ae0d1`。

本轮整理未修改生产 RTL、固件或冻结原件，没有重新执行 EDA/CPU12；既有性能收据和完整仿真日志由新入口按 SHA 绑定并重新检查。仍保留 4 unknown 与完整签核缺口。

## 收据

| 文件 | 内容 |
|---|---|
| [clean-clone-result.json](clean-clone-result.json) | 实际提交、命令、时间及退出码 |
| [clean-clone-validation.log](clean-clone-validation.log) | GitHub 克隆及五项验收完整输出 |
| [branch-cleanup-result.json](branch-cleanup-result.json) | 分支清理与未提交内容保持核对 |
| [历史分支归档](../../history/branch-archive-20261114.md) | 61 个原 tip 与恢复标签 |

`SHA256SUMS` 绑定本目录收据文件；收尾文档提交在集成提交之后补充本记录，不改变候选实现。
