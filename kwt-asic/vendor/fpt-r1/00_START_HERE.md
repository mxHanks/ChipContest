# 声算 FPT：本科组复用起步包

作品暂名：**声算 FPT——面向端侧语音识别的 RISC-V 前馈线性加速器**。

本包用于在独立工作区开始比赛开发。它保存 FPT 的可借鉴源码、数值模型、局部测试和来源清单；尚未实现 KWT-1 前馈层、E203 集成或比赛综合。原始文件按字节复制，候选选择见 `metadata/source_manifest.json`，无需访问原 FPT 目录即可查看与校验。

## 搬到新工作区

1. 将 ZIP 解压到一个独立目录，并把解压后的本目录作为新工作区根目录。不要覆盖原 FPT 工程。
2. 先运行 `python3 tools/verify_bundle.py`，确认全部文件哈希及参考文件集正确。
3. 阅读 `01_REUSE_MAP.md`、`03_COMPETITION_SCOPE.md` 和 `04_DEPENDENCIES_AND_STATUS.md`。
4. 把 `02_NEW_WORKSPACE_PROMPT_CN.md` 的内容粘贴给新会话。
5. 可运行 `python3 tools/run_host_checks.py --output /tmp/fpt-kwt1-host-check-r1`。输出目录必须不存在；此命令只运行 Python 数值辅助检查和 GCC 的 C 快照读取测试。

Windows 可将命令中的 `python3` 换成已安装的 Python；GCC 检查需要可用的 C 编译器。校验器仅依赖 Python 标准库。源码未压入旧虚拟环境、工具安装目录、服务器路径或符号链接。

## 目录

- `reference/fpt/`：保留字节的 FPT 参考源码、TB、数值工具、C 接口与接口文档。
- `reference/competition/guide.pdf`：用户提供的原始赛题指南。
- `filesets/`：各局部 TB 的相对路径文件集；仿真模型与 AMD 包装器分开。
- `metadata/`：复制来源、SHA-256、Git 基础状态、依赖与验证边界。
- `tools/`：可搬迁的完整性校验和主机检查入口。
- `AGENTS.md` / `PROGRESS.md` / `DECISIONS.md`：仅适用于新比赛工作区的起始约定和待办。

建议新开发的实现放入新建 `src/`、`model/`、`sim/`、`soc/`、`constraints/`，保留 `reference/` 作为对照。不要对整个 `reference/` 执行递归 HDL 编译：其中有同名仿真模型和厂商包装器，必须按文件集选择。

来源声明与设计边界见 `01_REUSE_MAP.md`。这是复用材料交接，不是原 FPT 活动任务的恢复包；原服务器任务的状态未在本次打包中重新观测。
