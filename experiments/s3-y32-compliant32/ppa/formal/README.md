# 最终374宏 RTL→mapped 一致性验证准备

本目录仅做离线身份审查，`review.py` **没有 `--run`，不会执行 EDA、访问库或服务器**。目前没有当前353／最终374的原生 Formality 通过结果。

## 已找到的可复用证据

仓库保留两份实际原生日志：

- `docs/handoff-evidence/s2c-fm.log`：R-2020.09-SP5、唯一实际 `Verification SUCCEEDED` 和 `XU_FULL_SOC_FORMALITY_PASS`，42,338 passing compare points，970秒。日志 SHA256 `c4214d589302ef3e7a147304b5de86dffc13c03d6e60ccb7c1cf241abfebf76c`，对应 `s2c-fm-state.json` 有 source／map／SVF／库身份和 returncode0。
- `docs/handoff-evidence/s2e155-fm.log`：同版本，唯一实际成功及 marker，42,338点，984秒。SHA256 `d88c3a5e3e8842d501efb13d70a1eb33aa9547d35eb1cecca9434dce68a2b0e4`，`s2e155-state.json` 保存原综合→hold→final三个 SVF 的顺序和实际执行身份。

旧生成器可以只读从 git 恢复：`554267f0d34de30289ddd43babeb450da0d1dfc9:tools/ppa/xu_s2e_ppa_server.py` 的 `formal_script/run_formal`；旧严格审查器在 `2c791bcd46499ca6dee4db26ae46ffc6a9e67c32:tools/ppa/xu_s2e_formality_audit.py`。当前 `tools/repro/server/s2e166/power166.py:native_fm` 也保存了如何区分 Tcl echo 与实际 terminal marker 的判据。

这些只能复用调用经验／身份和结果审查思路。旧 top 是 `xu_soc_ppa_top`、旧S2/336宏、旧数值与搬运结构，**不能作为当前S3的功能证明**。旧 proof 还允许 `hdlin_unresolved_modules black_box`、开启 auto_setup，有17个 unmatched reference DFF／511个 unread DFF；日志显示 reference 与 implementation 的 blackbox 数也有差异。它们的既有例外和42,338点数字不能照抄到本轮。

已回收353版 `default.svf`：1,015,808字节，SHA256 `cc997c786edebe19314aac77778153564ab16708e12c7081e01f04b22d267c5b`，与原DC receipt直接绑定。它只属于 mapped.v SHA `a7ec03579236948ea73fb72351490625e99661a87fe61e8af8aca05922d072dd`。最终374必须有自己的 mapped.v、DC完成收据和 own default.svf；不能借353的SVF跨过新增result21 SRAM与bias结构变化。

## 最小输入清单

1. **Reference**：最终374的密封PPA输入目录，`package-files.json`、`source-manifest.json`、159项 `rtl.f` 及所有 include 源文件；top `xu_soc_sysbus32_ppa_top`。define与综合完全相同：`SYNTHESIS DISABLE_SV_ASSERTION=1 XU_MATRIX_DMA XU_MATRIX_DMA_SYSBUS32 XU_MATRIX_X_SRAM XU_MATRIX_STORAGE_SRAM`。不读取TB／generic RAM模型／旧child当前HEAD替代密封副本。
2. **Implementation**：同一package产生且DC receipt SHA绑定的最终 mapped.v；mapped.ddc保留作额外身份／重放材料。严禁选择353或旧S2映射文件。
3. **Guidance**：本次实际 default.svf；若后续采用mapped ECO，则保留本次compile SVF→每次DC ECO SVF的完整顺序，及每个SVF对应输入／输出map身份。SVF仅是mapping guidance，本身不等于一次验证。
4. **Library**：现同库 standard_cell DB `f69c08a0...1a64723`、SRAM DB `c2cce1cf...886bf0f` 的真实服务器文件和完整SHA（见package/toolchain.json）。不发布库、不使用alib缓存替代库身份。
5. **Tool/setup**：实际FM入口 `/eda/synopsys/fm/fm_2020.09-SP5/bin/fm_shell` 的重新确认路径／SHA／原生版本、最多2核的**已证API**、本次独立目录、脚本和所有setup属性。旧日志证明常用read/match/verify语法在旧运行有效，未证明新脚本／resource API已经可用。
6. **Acceptance context**：同一final package的CPU12收据和源码集合身份，用于关联交付配置；固件、音频、Y32向量不参与Formality的reference逻辑读取，也不能拿CPU数值通过代替mapping一致性。

Reference和Implementation均应对应实际CPU64＋shared256＋W16＋bias1＋X16＋result21＝374宏。SRAM可采用同名同接口的opaque macro边界，必须核验所有对应D/WEN/A/CLK/CEN/GWEN/RET1N/Q等端口及所有实例，不能黑盒整个DMA/core/fabric。若FM自身优化合并/消去未使用宏或points，应列出原生前后清单并审查每个差异，不能仅用一个“374”常数掩盖内部未比较范围。宏边界proof也不证明SRAM单元内部电路或模拟时序。

## 最小执行顺序及输出

先在空闲、已协调资源上确认原生API／两核限制，然后生成一个新封包，重新hash source、map、own SVF、两库、FM入口和脚本。之后的流程是：设置明确记录的HDL解释策略→加载本次SVF链→加载两库→以密封顺序和defines读取reference SystemVerilog→设置新reference top→读本次mapped implementation→设置同名implementation top→原生核对未解析模块／macro边界→match→保存全部unmatched→verify→保存结果及所有未比较原因。**本目录没有把这段顺序伪装成已执行的新Tcl。**

最少交付 native stdout/log、执行returncode、前后输入SHA、工具／库身份、match统计、pass/fail/aborted/unverified/未匹配/未读/dont_verify点清单、全部blackbox及端口清单、guidance接受／拒绝摘要、HDL mismatch、constants、auto_setup与undriven等实际假设。如果verify失败、中止或超时，保持原失败，不把局部点通过包装成整机一致。

成功判据至少包含唯一实际行 `Verification SUCCEEDED`、唯一实际本轮marker、零failing/aborted/unverified点、完整同top/同freeze、没有未审查的cut/blackbox/ignore假设及未比较点；**不能**只搜索log里的“PASS”字样（Tcl echo会同时含PASS和FAIL）、不能固定要求旧42,338点，也不能用buffer-contraction连通性证明替代RTL→mapping证明。

映射后一致性不证明150MHz STA、面积单位、macro价格、NRMSE或功耗；这些仍独立验收。

## 原生API待采集

本地有实际旧FM日志，没有足够的新资源／blackbox／报告API man原件。`native-api-requests.txt` 列出主线程可在空闲EDA时采集的help/man。未知命令必须保留“不支持”和原生错误，不能用空文件或0统计当通过。特别需确认2核限制及严格列举blackbox／dont_verify／aborted/unverified点的方法，之后才生成可运行本轮脚本。

离线审查示例：

```sh
python3 -B experiments/s3-y32-compliant32/ppa/formal/review.py \
  --package build/compliant32-20261113/ppa-storage374-r3 \
  --out build/NEW-formal-input-review.json
```

可加 `--native 实际同包374的DC输出目录` 检查own map/SVF绑定；若误传353，工具必须拒绝。没有新native时返回 `OFFLINE_INPUT_IDENTITIES_REVIEWED_NOT_FORMALITY_EXECUTED`，并明确缺项。r3的area policy旧33文字缺陷也会显示，不替它补写“合规”。新package应由原owner修复后重封；本工具不修改封包。
