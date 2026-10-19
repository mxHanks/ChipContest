# SRAM Adapter 原语与bank契约入口

此入口把已存在的 `BACKEND=3` 逻辑Wrapper接到分阶段材料清单，不推测官方宏引脚，不改计算RTL、Golden、原回归或根Make。它只验证所提供模型的原语/bank逻辑契约；核心、ICB、CPU及指定工艺PPA仍是后续独立门槛。

## 运行

在根目录执行：

```bash
source env/activate.sh
python3 -B scripts/verify/run_official_sram_contract.py
```

默认读取 `configs/official-sram-package.json`，消费 [材料预检](OFFICIAL_SRAM_INPUT_READINESS.md) 的simulation源计划。当前缺包应退出2/BLOCKED，HDL命令数为0；不会退回行为模型或FF。真实材料到位后用 `--manifest 项目内清单.json` 指定新清单；先核官方来源/许可/手册，再编写实际Adapter。文件SHA正确不是官方来源真实性证明。

每次创建独立 `artifacts/runs/*-official-contract-*/`，保存运行前源码/工具/配置身份、工具版本、每条原生命令/日志/退出码、编译产物SHA、各案例结果和最终来源复核。单命令默认30秒，可用 `--timeout 1..120` 有界调整；串行编译。完整标记 `KWT_OFFICIAL_SRAM_CONTRACT_COMPLETE` 表示报告写完，还须读取status和原生结果。

## 固定覆盖范围

| 对象 | 形状 | 检查 |
|---|---|---|
| 原语 | 16×128、16×1024、16×4096 | 显式装载、首末/连续/重复读取、写读切换、一拍valid、Q保持、复位保留 |
| 现有bank | 16×3136、16×3200、16×2048、40×32、41×512 | 全地址正逆读取、深度片边界、宽度各位0/1、Q保持和复位保留 |
| Wrapper非法请求 | 7类原语、8类bank | 同拍读写、未装载读取、未知使能/地址/写数据、逻辑越界 |

正常8场景共23,177次数据检查。15个非法请求必须以Icarus原生exit1及准确FATAL原因结束；崩溃、超时、其他ERROR/FAIL或仅出现预期报错文字均不能算预期拒绝。原语的2次幂深度不使用截断后变成0的越界激励，逻辑越界由3200深度bank检测。

当前只需1RW，禁止同bank同拍读写，不认定供应商未规定的碰撞行为。Wrapper负责rd_valid和复位时请求屏蔽，Adapter逻辑口没有复位脚。不能从此推定官方宏的复位或使能极性。

本入口不要求物理SRAM支持HEX初始化；通过接口装载全部测试数据。原行为/FF的INIT_FILE测试仍由旧 `make test-memory` 负责。若真实宏延迟/Q保持与当前一拍接口不同，先适配或提出控制器修改，再重新验证；不能只推迟valid。

## 开发资格化与官方结果隔离

```bash
python3 -B scripts/verify/run_official_sram_contract.py --development-qualification good
python3 -B scripts/verify/run_official_sram_contract.py --development-qualification bad-data
python3 -B scripts/verify/run_official_sram_contract.py --development-qualification missing-adapter
python3 -B scripts/verify/run_official_sram_contract.py --development-qualification duplicate-adapter
```

这些显式选项使用 `sim/fixtures/kwt_logical_adapter_qualification.sv`，内部复用当前真实读写数组，仅用于验证BACKEND=3接线、bank拼接及检查器。它是开发夹具，非官方宏/引脚模型，遇SYNTHESIS立即拒绝；不在默认源集或综合源集中。正常资格化应exit0，其余三个故障应exit1：错误读数据在首个核对失败、缺模块/重复模块在真实编译阶段失败。不能把这三个FAIL当作设计PASS。

夹具路径或标记出现在普通清单模式中会拒绝，避免误把本仓库夹具当官方文件使用。资格化报告始终 `official_validation=NOT_RUN`、`official_ppa=BLOCKED`，不运行核心/ICB/SoC或综合。普通清单成功也仅为 `PRIMITIVE_BANK_ONLY`，不等于完整官方功能或PPA验收。

## 当前支持限制

此版本没有辅助include、初始化数据、SDF或DPI依赖清单。普通清单源含相应消费标记时保守拒绝，即使标记出现在注释中；这是支持范围检查，不是正则表达式证明HDL不存在任何外部依赖。真实包需要这些文件时，先扩展显式辅助输入清单、哈希及实际消费记录，再放开，不能仅删掉门槛或删改官方模型。二进制及项目Icarus运行目录文件已绑定，仍不宣称完整操作系统依赖镜像。

现有这8个正常场景尚未覆盖“同地址改写为不同值”和“reset期间使能持续高”的专门激励；23,177检查是上表所测场景，不能称完整SRAM模型验收。真实模型接入时应补这些边界及手册规定的其他合法行为；非法碰撞继续禁止。

真实官方接入仍须：原语/bank通过→行为/FF/官方核心逐位对照→完整12层/恢复/协议→E203 CPU及正式平台→同源综合、指定PVT全路径时序和全部宏面积/功耗。当前参考库/ECO的历史PASS不自动继承到官方模式。

## 本轮可核验证据

[来源索引](runs/official-sram-contract-20261018.json)复核830个唯一文件，旧644文件来源不变；[独立审查](reviews/20261018-official-sram-contract-review.md)核对原生日志、source_id和计数。8个CLI资格化、238主机检查通过，所测8正常场景与15预期拒绝的范围如上。官方功能NOT_RUN，PPA BLOCKED。首版收集器失败保留，最终接受final-v2；不把早期不同源码epoch的试跑当作当前来源验收。


## 后续覆盖增量

上文8场景本身未改。另新增[不同值覆写与reset门控定向回归](SRAM_UPDATE_RESET_VALIDATION.md)，已在8形状/3开发后端实际通过24场景/1080分组检查及三类故障检出。它补上所述开发覆盖缺口，不把开发夹具升级为官方模型；真实包到位后需同时重跑本入口和补测，再继续核心/CPU及指定工艺验收。


后续新增[Adapter核心/ICB功能入口](SRAM_ADAPTER_SYSTEM.md)，消费simulation源计划并重核同输入原语报告后才运行BACKEND3；开发夹具的14核心任务和四态ICB已资格化。旧CLI保持原字节；真实宏/CPU/正式SoC和指定PPA仍需实际文件及新验证，不能把文件核验或开发PASS当作官方通过。
