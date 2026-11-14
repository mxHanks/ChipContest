# 2026-11-14 分支历史归档与恢复

本表记录主方案切换前的父仓库分支 tip，观测时间为 2026-11-14T09:50:35.166899+08:00。选定修复候选为 `be67e5d745cd7123e0def870f26be9a84263d759`，RTL 子仓库固定为 `5470c5650f2d11d16e7c52cc96626d21030a3973`；面向评委的整理提交沿该来源继续提交。

**归档标签已创建并推送：61 / 61。** 已通过 `git ls-remote --tags origin` 逐项核对远程标签 SHA 与下表原 tip 一致。main 已快进到整理提交 `b275f05d9dd5d6981432bd800f2e2a4d98d72633`，并完成下述分支清理。

## main 切换关系

本地与远程 main 原 tip 均为 `ddccdc95b9aa1521c3e404b9d9f95b788fdae8a5`。main 是修复候选的祖先，`main...候选` 为 0 / 64，因此可快进到候选及其后续整理提交，无需强制改写已有 main 历史。main 自身也保存历史标签，但不会删除 main。

## 恢复方式

标签分别保存本地和远程原 tip；即使分支同名，也不得用其中一边覆盖另一边。全部归档标签已推送并逐项核对远程 SHA，后续分支删除以这些已核实引用为恢复依据。

```sh
git fetch origin --tags
git switch -c restore-selected-1064 archive/20261114/remote/codex/s3-y32-ingress-perf-20261113
git submodule update --init --recursive
```

从其它历史状态恢复时，将标签替换为下面表内的精确名称。子仓库提交由父仓库 gitlink 保留；本次父仓分支清理不删除子仓库分支。

## 本地分支原 tip

| 原本地分支 | 原提交 | 归档标签 | 工作区角色 |
|---|---|---|---|
| `codex/s3-y32-4k-goal` | `d60e0e00d79051747b8adcfa39fca273a6e7e309` | `archive/20261114/local/codex/s3-y32-4k-goal` | — |
| `codex/s3-y32-area-opt-20261111` | `dafd56613e6cf084e3aa64d90e948008216da524` | `archive/20261114/local/codex/s3-y32-area-opt-20261111` | — |
| `codex/s3-y32-bias-demand` | `e984bad936855debfc5fa01f04bcbc6252d59ecc` | `archive/20261114/local/codex/s3-y32-bias-demand` | — |
| `codex/s3-y32-compliance-20261113` | `a4546569ed0b9b385173da7e4667a1b9d03046f0` | `archive/20261114/local/codex/s3-y32-compliance-20261113` | compliance-writeback |
| `codex/s3-y32-dma-day` | `1800a0767f1df5f0af483d546b24edcf84a7b857` | `archive/20261114/local/codex/s3-y32-dma-day` | — |
| `codex/s3-y32-final-20261113` | `e46c3e192f99be900876023e1a89414634e8c80d` | `archive/20261114/local/codex/s3-y32-final-20261113` | gpio-final |
| `codex/s3-y32-hw-sw-v1` | `655713b304597ca5b2810a0940ac3f1850072d63` | `archive/20261114/local/codex/s3-y32-hw-sw-v1` | — |
| `codex/s3-y32-ingress-perf-20261113` | `be67e5d745cd7123e0def870f26be9a84263d759` | `archive/20261114/local/codex/s3-y32-ingress-perf-20261113` | selected-1064 |
| `codex/s3-y32-last-two` | `79d883300c7dfca7d129ff8e25daf34cf100250c` | `archive/20261114/local/codex/s3-y32-last-two` | — |
| `codex/s3-y32-last-two-synth` | `79d883300c7dfca7d129ff8e25daf34cf100250c` | `archive/20261114/local/codex/s3-y32-last-two-synth` | — |
| `codex/s3-y32-packed-clear` | `f8c5c9ee631a9c3cbf62015dff98bad6939400f4` | `archive/20261114/local/codex/s3-y32-packed-clear` | — |
| `codex/s3-y32-postflow` | `d6bea15b641cbe9b29c440f261636ab50a934ca2` | `archive/20261114/local/codex/s3-y32-postflow` | — |
| `codex/s3-y32-ready` | `51a021c8bfc9649e2be4be1292735181f7a551e8` | `archive/20261114/local/codex/s3-y32-ready` | — |
| `codex/s3-y32-timing-opt` | `1800a0767f1df5f0af483d546b24edcf84a7b857` | `archive/20261114/local/codex/s3-y32-timing-opt` | — |
| `codex/s3-y32-writeback` | `562a8c91a42ba96c584c78c475fb972e6ac11d49` | `archive/20261114/local/codex/s3-y32-writeback` | — |
| `codex/s3-y32-writeback-v2` | `83817c837726e60bf1e59c8a199d6062d4125448` | `archive/20261114/local/codex/s3-y32-writeback-v2` | — |
| `codex/xu-activity-deploy12` | `1664ef9145e4275f7bbc9755ea11e9086771b91c` | `archive/20261114/local/codex/xu-activity-deploy12` | — |
| `codex/xu-activity-deploy15` | `5e75581319f926642ee7dc214ad825f3564a8e39` | `archive/20261114/local/codex/xu-activity-deploy15` | — |
| `codex/xu-bank128-ppa` | `24567100fd02a7b7350ba877b7bb0ba7ebf36be0` | `archive/20261114/local/codex/xu-bank128-ppa` | — |
| `codex/xu-candidate-activity` | `5e75581319f926642ee7dc214ad825f3564a8e39` | `archive/20261114/local/codex/xu-candidate-activity` | — |
| `codex/xu-handoff-20261105` | `ccb321fd4c4106ca7feaa3f0b8904fa7c2fee239` | `archive/20261114/local/codex/xu-handoff-20261105` | — |
| `codex/xu-joint-deploy30` | `5bf2a531070bb13551175f6d1b84184c1f250107` | `archive/20261114/local/codex/xu-joint-deploy30` | — |
| `codex/xu-joint-deploy36` | `61f74dc2741764be79194b73aff064589d9c3d6a` | `archive/20261114/local/codex/xu-joint-deploy36` | — |
| `codex/xu-joint-numeric62` | `0cd69025e9ceb91020ac3d6f08cb2fcbd0cb4b13` | `archive/20261114/local/codex/xu-joint-numeric62` | — |
| `codex/xu-joint-review56` | `e53720e21417be0bb9858bde3555273b37d420ab` | `archive/20261114/local/codex/xu-joint-review56` | — |
| `codex/xu-optimize-fw` | `499ba54bd57db81c058ab5efe25def226ec6dd15` | `archive/20261114/local/codex/xu-optimize-fw` | — |
| `codex/xu-optimize-hw` | `896e90246ce8494202c1972ced0f5ad2ebb41002` | `archive/20261114/local/codex/xu-optimize-hw` | — |
| `codex/xu-pe32-bank128` | `f75880d4f06ccb7f1c16115bee501f53d9a2abb7` | `archive/20261114/local/codex/xu-pe32-bank128` | — |
| `codex/xu-pe32-ppa` | `42960121cdd25ed91b7e64223cbe47b18a82486b` | `archive/20261114/local/codex/xu-pe32-ppa` | — |
| `codex/xu-pe64-ppa` | `a6359724629916f2925cd58151e187fd5620b7ad` | `archive/20261114/local/codex/xu-pe64-ppa` | — |
| `codex/xu-platform-eval` | `c08cac39a110eff9c334bb16ad9d482cb80d6174` | `archive/20261114/local/codex/xu-platform-eval` | — |
| `codex/xu-ppa-deploy26` | `e19304cb3f1f45ad2b691a9e316702ff2aeea9d1` | `archive/20261114/local/codex/xu-ppa-deploy26` | — |
| `codex/xu-s1-h2-only` | `23992eb77f2c42eaeefbe7dcbdb682aba1ef2b78` | `archive/20261114/local/codex/xu-s1-h2-only` | — |
| `codex/xu-s1-sram-bias` | `b6f5075e79eff9c14267e1ef97d90b9f8e82f23a` | `archive/20261114/local/codex/xu-s1-sram-bias` | — |
| `codex/xu-s2a-stream` | `3c13930c1f36d6516577d33d8587d89a86b49563` | `archive/20261114/local/codex/xu-s2a-stream` | — |
| `codex/xu-s2b-packed` | `a2a1f076060c43fcefb1148edaa83c89bb1d4320` | `archive/20261114/local/codex/xu-s2b-packed` | — |
| `codex/xu-s2c-autogroup` | `d276b55ffecbe8d620f9a361bf5d0859299ba7b5` | `archive/20261114/local/codex/xu-s2c-autogroup` | — |
| `codex/xu-s2d-doublebuf` | `3af4db98b893edd2103771fa132d69350b82ba96` | `archive/20261114/local/codex/xu-s2d-doublebuf` | — |
| `codex/xu-s2e-activity` | `2c791bcd46499ca6dee4db26ae46ffc6a9e67c32` | `archive/20261114/local/codex/xu-s2e-activity` | — |
| `codex/xu-s2e-paired-hi` | `5bf123bfead8f2a37f97f3234d4e40ce8201aae9` | `archive/20261114/local/codex/xu-s2e-paired-hi` | — |
| `codex/xu-s2e-ppa` | `554267f0d34de30289ddd43babeb450da0d1dfc9` | `archive/20261114/local/codex/xu-s2e-ppa` | — |
| `codex/xu-s3-pe32` | `94ce6f0f54fffdd590ff9a3ebad0197ec0fd9114` | `archive/20261114/local/codex/xu-s3-pe32` | — |
| `codex/xu-s3-pe64` | `3443fad8945577626d226b1cd53eadec89331a20` | `archive/20261114/local/codex/xu-s3-pe64` | — |
| `codex/xu-score-opt` | `565011de336e4fe8ecc8fe308638c907715ed9e2` | `archive/20261114/local/codex/xu-score-opt` | — |
| `codex/xu-sram-joint-activity` | `0cd69025e9ceb91020ac3d6f08cb2fcbd0cb4b13` | `archive/20261114/local/codex/xu-sram-joint-activity` | — |
| `codex/xu-uart-path-proof` | `f04f682ab0b15a1715201c165a21c5fb27efee51` | `archive/20261114/local/codex/xu-uart-path-proof` | — |
| `feature/e203-integration` | `c71a0eaae45efa4d5df599aa14076241854c4503` | `archive/20261114/local/feature/e203-integration` | — |
| `main` | `ddccdc95b9aa1521c3e404b9d9f95b788fdae8a5` | `archive/20261114/local/main` | primary-main |

## 远程 origin 分支原 tip

以下列表由成功的 `git ls-remote --heads origin` 核对；均与当时本地 origin 跟踪引用相符。`origin/HEAD` 是指向 main 的符号引用，不是待删分支。

| 原远程分支 | 原提交 | 归档标签 |
|---|---|---|
| `codex/s3-y32-4k-goal` | `d60e0e00d79051747b8adcfa39fca273a6e7e309` | `archive/20261114/remote/codex/s3-y32-4k-goal` |
| `codex/s3-y32-area-opt-20261111` | `dafd56613e6cf084e3aa64d90e948008216da524` | `archive/20261114/remote/codex/s3-y32-area-opt-20261111` |
| `codex/s3-y32-final-20261113` | `e46c3e192f99be900876023e1a89414634e8c80d` | `archive/20261114/remote/codex/s3-y32-final-20261113` |
| `codex/s3-y32-hw-sw-v1` | `655713b304597ca5b2810a0940ac3f1850072d63` | `archive/20261114/remote/codex/s3-y32-hw-sw-v1` |
| `codex/s3-y32-ingress-perf-20261113` | `be67e5d745cd7123e0def870f26be9a84263d759` | `archive/20261114/remote/codex/s3-y32-ingress-perf-20261113` |
| `feature/e203-integration` | `9d5f800521edf75584af6d290067c5f03356ecdd` | `archive/20261114/remote/feature/e203-integration` |
| `feature/e203-xu-integration` | `420e3997d55ef879bf27b2e56ecafb563ef434ad` | `archive/20261114/remote/feature/e203-xu-integration` |
| `feature/e203-xu-server-prep` | `ddcf6cc5ea9119b3dd162249be8c4521eef45da2` | `archive/20261114/remote/feature/e203-xu-server-prep` |
| `feature/kwt-sram-handoff-20261019` | `c2e58fd9de4c653c4d7822ee5e79e4f06761edb1` | `archive/20261114/remote/feature/kwt-sram-handoff-20261019` |
| `feature/xu-b41-handoff-20261112` | `7b4adb3c5a5e07240b34de702d9bcbc2d2c4cad6` | `archive/20261114/remote/feature/xu-b41-handoff-20261112` |
| `main` | `ddccdc95b9aa1521c3e404b9d9f95b788fdae8a5` | `archive/20261114/remote/main` |
| `revert-1-feature/kwt-sram-handoff-20261019` | `6b3ab7ea80dda504d11781ce31f9de871732c2bb` | `archive/20261114/remote/revert-1-feature/kwt-sram-handoff-20261019` |
| `s3-y32-development` | `680be463b8c5f7140884d40ae16891c6ccc94d7a` | `archive/20261114/remote/s3-y32-development` |

## 同名不同提交

`feature/e203-integration` 的本地与远程 tip 不同，必须分别归档：

| 范围 | 提交 |
|---|---|
| local `feature/e203-integration` | `c71a0eaae45efa4d5df599aa14076241854c4503` |
| remote `feature/e203-integration` | `9d5f800521edf75584af6d290067c5f03356ecdd` |

## 工作区未提交内容

仅记录仓库内相对路径，工作区以角色名称标识。标签只保存已提交 tip，不包含这些未提交文件。不得用清理分支为由删除工作区或丢弃文件；已检出的分支须先安全切换或分离 HEAD，并保留所有工作内容。忽略的 build 输出不在下表中，必须继续留存。

| 工作区角色 | 原分支 | 原提交 | 状态 | 仓库内路径 |
|---|---|---|---|---|
| primary-main | `main` | `ddccdc95b9aa1521c3e404b9d9f95b788fdae8a5` | `??` | `outputs/` |
| primary-main | `main` | `ddccdc95b9aa1521c3e404b9d9f95b788fdae8a5` | `??` | `赛题指南.pdf` |
| gpio-final | `codex/s3-y32-final-20261113` | `e46c3e192f99be900876023e1a89414634e8c80d` | `??` | `experiments/s3-y32-final/validation/activity/export_activity_evidence.py` |
| compliance-writeback | `codex/s3-y32-compliance-20261113` | `a4546569ed0b9b385173da7e4667a1b9d03046f0` | ` M` | `experiments/s3-y32-compliant32/validation-gpio/package_evidence.py` |
| compliance-writeback | `codex/s3-y32-compliance-20261113` | `a4546569ed0b9b385173da7e4667a1b9d03046f0` | `??` | `docs/s3-y32-timing-opt-plan.md` |
| compliance-writeback | `codex/s3-y32-compliance-20261113` | `a4546569ed0b9b385173da7e4667a1b9d03046f0` | `??` | `experiments/s3-y32-compliant32/ppa/formal/api_collect.tcl` |
| compliance-writeback | `codex/s3-y32-compliance-20261113` | `a4546569ed0b9b385173da7e4667a1b9d03046f0` | `??` | `experiments/s3-y32-compliant32/ppa/formal/run_api.py` |
| compliance-writeback | `codex/s3-y32-compliance-20261113` | `a4546569ed0b9b385173da7e4667a1b9d03046f0` | `??` | `experiments/s3-y32-compliant32/ppa/formal/test_api_offline.py` |
| compliance-writeback | `codex/s3-y32-compliance-20261113` | `a4546569ed0b9b385173da7e4667a1b9d03046f0` | `??` | `experiments/s3-y32-compliant32/ppa/power/` |
| compliance-writeback | `codex/s3-y32-compliance-20261113` | `a4546569ed0b9b385173da7e4667a1b9d03046f0` | `??` | `experiments/s3-y32-dma-day/timing-opt/` |
| compliance-writeback | `codex/s3-y32-compliance-20261113` | `a4546569ed0b9b385173da7e4667a1b9d03046f0` | `??` | `tmp/` |

`selected-1064` 的 README／结构整理已由 `b275f05d9dd5d6981432bd800f2e2a4d98d72633` 记录并进入 main，其工作区保留在该提交的 detached HEAD。

本次清单计 48 个本地分支、13 个真实远程分支和 4 个工作区。清理范围为父仓库除 main 外的分支；历史源码、实验、证据和未提交工作不能随分支清理删除。

## 完成记录

2026-11-14 10:01（北京时间）已完成：

- 61 个归档标签均推送并逐项核对原 tip。
- origin/main 正常快进至交付整理提交；未强制改写 main 历史，远程默认 HEAD 仍为 main。
- 删除 12 个其它远程分支、47 个其它本地分支，父仓本地与 origin 均只保留 main。
- 原 4 个工作区继续留存：主目录位于 main，其它 3 个在各自提交分离 HEAD；原分支上的未提交内容未丢弃。
- 对清理前记录的 73 份未提交文件逐 SHA/长度复核一致，包括主目录 outputs 和赛题指南 PDF。忽略的本地产物未清理。
- 子模块分支未改；主目录 gitlink/实际 RTL 均为 5470c565。
- 从 GitHub HTTPS 独立克隆 main 后，证据校验、入口回归、向量恢复/整数校验和最终映射提取全部通过。收尾文档提交仅补充本记录与验收收据。

详见[仓库交付验收](../validation/repository-main-20261114/README.md)。归档标签保存的是本表观测时的已提交状态；未提交工作继续保留在原工作区，不包含在标签内。
