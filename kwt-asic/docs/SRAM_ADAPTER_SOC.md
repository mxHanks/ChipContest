# SRAM Adapter的E203 CPU功能入口

此入口把已验证的BACKEND3 Adapter接入现有开放E203开发平台。原CPU、固件、计算RTL、Golden和SoC TB保留；仅在独立run目录生成外设接线、共享模型两份副本。它不执行综合、正式工艺PPA或板卡操作。

## 执行顺序

```bash
source env/activate.sh
# 当前官方包缺失：exit2/BLOCKED，0条HDL/工具命令
python3 -B scripts/verify/run_sram_adapter_soc.py

# 开发夹具必须显式选择；前置是同Adapter的完整core+ICB报告
python3 -B scripts/verify/run_sram_adapter_soc.py \
  --development-adapter \
  --system-report artifacts/runs/20261018T054213.004858Z-adapter-system-1b958078/result.json
```

当前工作区报告不是源码包自带内容。换机器时先依次执行[原语入口](OFFICIAL_SRAM_CONTRACT_RUNNER.md)和[核心/ICB入口](SRAM_ADAPTER_SYSTEM.md)，将真实生成的报告路径传入，不能构造PASS JSON代替。CPU入口不接受只运行core或只运行ICB的前置。

实际包到位后，原语、核心/ICB及CPU三步均使用同一`--manifest configs/official-sram-package.json`，去掉开发夹具选项。还需先确认真实引脚/一拍读/Q保持/碰撞等契约，运行覆写/reset补测；材料预检FILES_VERIFIED不等于宏功能或官方来源认证。

## 身份与验收

先重新检查同源原语33条原生命令、核心/ICB9条命令及其二进制、实际向量和全部结束计数，再冻结平台、固件、工具与Adapter。平台136份源固定来自已接受开发SoC清单，不自动纳入新文件、不修改融合checkout。

唯一替换为：

- `kwt_icb_slave u_kwt_accel` → `kwt_icb_slave_sram #(.SRAM_BACKEND(3)) u_kwt_accel`。
- `kwt_shared512_model u_kwt_shared` → `kwt_shared512_checked_model u_kwt_shared`。

两份副本、复制向量、ELF/BIN/HEX和新仿真binary均在下一步消费前记录SHA，完成后重新核对。固件每次新编译；实际CPU装载BIN/补零HEX必须与已接受12层软件一致。ELF保留独立完整身份，GCC随机临时对象名引起的非装载字符串差异不作为CPU程序差异。

入口固定12层；每层必须25344结果、22976装载提交、50688输出写响应、1 ACK，严格核对配置→装载→末写响应→ACK响应→最终邮箱响应顺序。必须有soft abort、真实pending响应外部reset及重新装载恢复，原生退出0、唯一完整suite和原生`$finish`，无阻断诊断。

默认CPU仿真上限1800秒，`--timeout 1..1800`可缩短。使用项目执行记录工具保存原生日志、退出码与超时/中断；每次新run不覆盖旧报告。历史12层约661秒，编译约14秒，仅作为本机运行预算。

## 已知限制

这是开放Fork开发集成。仿真为Verilator两态，沿用旧平台`DISABLE_SV_ASSERTION=1`，不宣称全CPU四态/SVA验证。TB逐位比较及真实总线响应计数仍开启，Golden仅在TB使用，CPU不取得预计算答案。

冻结平台已有2条UNOPTFLAT：CPU BIU/LSU路径和QSPI仲裁路径；15条LATCH属于原clockgate。入口严格比较这两类的完整诊断，新增或变化即拒绝；其余告警记录分类。保留这些限制不等于证明平台无环、lint干净或正式平台可接受。未按告警文本修改CPU或放宽时序约束。

12层向量是固定真实权重/逐层输入的静音smoke，不是官方600样本或完整数据集精度。开发窗口含CPU调度、配置、装载、计算、等待及所有写回/ACK/邮箱响应，排除TB预装载和被中断epoch，不能称官方完整装载性能。150MHz仅为仿真设定，不证明ASIC时序。

官方宏、正式平台、指定PVT/完整时序、总面积及功耗继续分别NOT_RUN/BLOCKED。该入口的实际接受结果与原始证据以PROGRESS和对应来源索引为准。


## 本次开发资格化结果

2026-10-18：`artifacts/diagnostics/20261018-adapter-soc/final-v3/result.json`实际外层6条命令退出2/2/1/0/0/0；三项前置拒绝均0条HDL/工具命令，281主机检查及静态入口完成。CPU子报告`artifacts/runs/20261018T060322.777092Z-adapter-soc-494a788d/result.json`的7条原生命令全部exit0；编译14.220秒、CPU647.757秒。12层304128结果逐位一致、275712装载提交、608256输出写响应、12 ACK，soft abort及pending响应外部reset恢复通过。开发窗口21261300周期，旧行为后端为用户语音输入、新Adapter为静音输入；形状/固件相同且周期相同，但非同workload或隔离后端A/B。

两次早期失败保留：final-v1在CPU编译前拒绝ELF非装载字符串差异；final-v2在编译后因reader误包含make输出而拒绝，CPU未运行。失败producer/qualification保存原字节，旧测试在失败后按已经绑定的SHA恢复保存；这是历史字节恢复，不追补旧运行的预冻结声明。final-v3为首次完整CPU长测。

新编译告警数量为113 WIDTHEXPAND、7 WIDTHTRUNC、4 UNSIGNED、11 CASEINCOMPLETE、15 LATCH、2 UNOPTFLAT，均保持原平台/模型来源范围；仅loop/latch完整块做严格不变门槛。数值及响应通过不消除这些lint限制。独立审查和逐文件来源索引见当前PROGRESS，正式宏/平台/PPA保持未通过。
