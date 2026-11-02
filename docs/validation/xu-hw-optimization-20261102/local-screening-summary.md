# xu 本地硬件筛选与独立证据核验

冻结运行源码为 `97b35421dfbbfa8f4d495b6927a7c66610ff8206`，E203 子模块为 `f49a5fc914971426bd4530db39e270a84b41139f`。本页只记录本机 GCC 14.2.0 / Verilator 5.032 / Icarus 12.0 的筛选证据；服务器 VCS 的 12 层保留结论由主报告另行给出。这些本地数值不能与服务器 SiFive GCC 10.2.0 的周期直接混用。

原始串行脚本完成 7 次 SoC 仿真、10 个任务，全部 PASS。所有配置均使用 `-O2 / both-unroll-no-masks`：

| 实验 | schedule | 向量 / task 数 | 各 task 总周期 | ITCM 字节 | BSS 字节 |
| --- | --- | --- | ---: | ---: | ---: |
| B0-real1 | `bias-dtcm` | real / 1 | 2,083,525 | 1064 | 2048 |
| H1-synthetic2 | `bias-hw` | synthetic / 2 | 1,549,641, 1,549,642 | 848 | 0 |
| H1-real1 | `bias-hw` | real / 1 | 1,549,641 | 848 | 0 |
| H2-synthetic2 | `bias-dtcm-window` | synthetic / 2 | 1,928,522, 1,928,524 | 1074 | 2048 |
| H2-real1 | `bias-dtcm-window` | real / 1 | 1,928,522 | 1074 | 2048 |
| H1H2-synthetic2 | `bias-hw-window` | synthetic / 2 | 1,387,720, 1,387,720 | 932 | 0 |
| H1H2-real1 | `bias-hw-window` | real / 1 | 1,387,720 | 932 | 0 |

B0 是新增硬件 RTL 的 legacy 模式，固件 image SHA 与此前单独构建的本机软件基线 `1e038157321ac5891329762064d7da77125fbf0134dfe29600e94105b5acefd8` 一致。H1 是全层 bias cache，H2 是只读结果窗口，H1H2 同时启用。固件的静态函数栈帧、ELF/image SHA、逐阶段周期与全部事务计数保留在 `local-verification.json`；静态栈帧不表示实测栈水位。

独立核验脚本不导入运行 driver、共享 contract、实验 campaign 或保留决策函数。它直接解析原始 `TASK_PASS / PERF_TASK / SOC_PASS`，校验严格事件顺序与字段、每任务 25,344 个结果 / 50,688 次写回、3,168 次 start/done、202,752 次 MAC fire、215,424 个 busy 周期、phase 总和以及独立推导的 MMIO/shared 事务数。它还校验全部 214 个冻结运行源文件及文件集合、151 个实测 RTL/TB 来源、runner/contract 哈希、全部原始日志 SHA、固件配置命令、ELF/image/SU 身份；ELF 的 allocated section 字节与实际装载 image 逐字节比对。

真实向量按仓库内固定归档及 48 个成员 SHA 引用，合成向量由核验脚本使用 Python 整数独立重算并比对 8 个成员 SHA。本包不重复存放向量、仿真可执行文件或编译缓存。7 次仿真的原始 JSON、全部 .log、firmware.dump、固件 ELF/image 与 .su 均归档，原始 stdout、原始本地调度脚本和 host/numeric 日志也在包内。

Host 测试原始输出为 49/49 PASS，numeric 为 34/34 PASS。独立核验的三个反例检查也通过：修改原 PERF 的 MMIO 写次数、重复 TASK 事件、追加归档字节均被拒绝，见 `local-verifier-negative-controls.json`。

Chisel 测试先前工具 stdout 观察到 10 个 suites / 13 个测试全部通过、汇总耗时 75 秒；原始汇总 stdout 当时没有重定向保存，因此只作为观察收据，不能作为归档原始 stdout。39 个逐测试编译 / 协议执行脚本 / 仿真 console 文件保留原始字节；空 console 文件也保留。详细覆盖范围及工具版本见 `xu-local-evidence-summary.md`、`xu-local-evidence-summary.json` 和 `xu-chisel-observation-receipt.json`。

另两次 Icarus wrapper 检查有原始输出：基础 directed wrapper 接受 / 退休均 4,909 次；补充接口包接受 / 退休均 4,967 次。补充包验证 16 个结果窗口的写入均被忽略，以及 busy 时 CACHE_CTRL/CACHE_ADDR 可以写入和读回；后者属于违反固件参数稳定约束的操作，该次计算数值明确不作校验，随后立即复位。

三份归档均带严格 `SHA256SUMS`，覆盖全部普通文件（清单自身除外）；外层清单为 `local-artifacts/archives-sha256.json`：

| 归档 | 字节 | 普通文件数（含清单） | SHA256 |
| --- | ---: | ---: | --- |
| `xu-hw-local-evidence.tar.xz` | 1204980 | 48 | `baa54cb77e0b038d824a51c97f3f7227b56281a77445a9d8ad08209807e458ab` |
| `xu-hw-extra-interface.tar.xz` | 8048 | 10 | `a14d84c035d33b6e9d07afbae2e9ce3917544994583d9785c1d2814291490522` |
| `xu-hw-local-screening.tar.xz` | 44780 | 134 | `a4ff5236891bc3a8b51aa4223e23a34d90b9fe08c2df21b777373b211fabf4bb` |

独立复核现有证据（不重新跑仿真）：

```bash
xu_repo=/home/mxhanks/Projects/ChipContest-xu-optimize-hw
xu_evidence="$xu_repo/docs/validation/xu-hw-optimization-20261102"
python3 "$xu_evidence/evidence-tools/xu_hw_local_check.py" --repo "$xu_repo" --out /tmp/xu-local-unused --check-sources-only
python3 "$xu_evidence/evidence-tools/xu_verify_local_evidence.py" --repo "$xu_repo" --evidence "$xu_evidence" --out /tmp/xu-local-verification.json
python3 "$xu_evidence/evidence-tools/xu_local_evidence_negative_controls.py" --repo "$xu_repo" --evidence "$xu_evidence" --out /tmp/xu-local-negative-controls.json
```

重新运行本地串行筛选时，输出目录必须为新目录；此操作会真实重编译并运行 7 次仿真。复现脚本以冻结运行源字节与文件集合守卫，后续仅文档/证据提交造成的 HEAD 变化可以接受：

```bash
python3 "$xu_evidence/evidence-tools/xu_hw_local_check.py" --repo "$xu_repo" --out "$xu_repo/build/xu-hw-local-reproduce-01"
cd "$xu_repo"
python3 -m unittest discover -s tests/e203 -p "test_*.py" -v
python3 -m unittest discover -s tests/numeric -p "test_*.py" -v
scala-cli test . --server=false
```

补充接口包包含冻结基础 TB、最小 patch、独立 runner 与原始 Icarus 日志。展开归档后按其 `README.md` 使用 `run.py --repo ... --sim iverilog|vcs --out ...` 重现；runner 会先核对 13 个 RTL 文件 SHA。该包内 Icarus PASS 不代表 VCS 已执行。

本地证据校验只证明所保留原始产物与已记录事件、计数和源身份一致，不是第二次独立 RTL 仿真，也不单独证明服务器 real12 性能、物理面积、功耗、时序收敛或准确率。
