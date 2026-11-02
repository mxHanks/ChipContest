# xu S0 综合前后功能回放

本轮新增独立回放器 [xu_gate_verify.py](../../../tools/scripts/xu_gate_verify.py) 和仅从ICB端口观察的 [tb_xu_gate_wrapper.sv](../../../tests/host/tb_xu_gate_wrapper.sv)，不改现有RTL、固件、数值格式或旧TB。它对同一份测试分别运行RTL和综合后网表，比较完整请求/响应事务trace的原始字节；每个结果先与测试中的signed整数参考值比较，再比较新旧结果别名。

本地真正执行Yosys综合及Icarus门级回放，属于通用门开发验证。服务器DC综合网表需要显式提供标准单元和SRAM功能模型，使用同一runner的外部网表模式。两者都不冒称Formality证明、SDF时序仿真、完整SoC综合后功能验收或正式PPA。

## 验证范围

原缓存/窗口测试覆盖256列全写、masked写、两任务刷新、legacy路径、固定结果窗口与旧RESULT_INDEX交错、复位默认、背压和同拍旧响应退休/新命令接受。新增数值工作为两任务×两行×四组（0/15/16/31）×legacy/cached两模式；X/W使用signed16极值正负交替，bias使用signed40极值及任务变化，检查非零64拍MAC与跨SRAM边界。两任务间不复位。

完整测试包含39次START，检查312个48位数值结果；每个结果通过窗口和旧索引两种别名读取，共1,248个结果读字。原TB中 `dut.cache_read_data` 的内部层级探针不能用于综合网表，新TB改用端口读回验证pipeline写和受阻响应稳定；不依赖保留内部网名。所有转移保留确定随机间隙和响应背压。

本地Yosys流将 `mem_1024x16` 显式视作黑盒边界，门级仿真连接原行为RAM模型，其余wrapper、cache和8路计算核展开为通用门。该边界不证明工艺SRAM模型语义；服务器用厂家RAMSP1024X16功能模型另行验证。Yosys对memory与gate输出的说明见[官方memory文档](https://yosyshq.readthedocs.io/projects/yosys/en/stable/using_yosys/synthesis/memory.html)。

## 本地实际结果

**本地真实综合与门级回放PASS**：RTL和generic门级各接受/退休17,151次，完整事务trace逐字节相同，SHA256均为 `16a76077e775b8d6dfc920f35e61d480a27d3f02393f39ce098411a80aa73d34`。trace排除复位前2笔访问，共17,149条；测试本身另校验39次START和312个数值结果。

综合网表8,364,326字节，SHA256 `43efa08fbeb0d0d44447dd5fc96ebdc9c92fb3f4d882fc53a7b2292382b81098`，97,064个generic逻辑/存储边界实例；仅16个行为SRAM保留为边界，其余电路真正综合。原始[generic-gate-result.json](generic-gate-result.json)、[全命令/日志/trace/网表归档](xu-generic-gate-evidence.tar.xz)和[成员SHA](archive-manifest.json)随交付。

归档大小3118084字节、SHA256 `bd6c95320e2c525511128f0fdf33ff73feccb7ed7b92eb4019e83b36e38d95c2`，包含失败第一轮及完成的第二轮。未发布Icarus编译字节码，真实源网表和编译命令足以复现。

回放器同时拒绝PASS缺失/重复、FATAL/错误、请求响应不等、trace未知X/Z、顺序缺失、trace计数不符和两路原始trace不一致。Host证据反例测试原4/4通过；新增VCS显式零延时选项检查后为5/5通过，覆盖未知响应、重复PASS/未退休/FATAL、漏转移及缺失模型include。

实际generic运行的工具原文另存[run-source/xu_gate_verify.py](run-source/xu_gate_verify.py)，SHA与原result一致。后续现行工具只增加VCS `+nospecify/+notimingcheck` 明确零延时和子进程DEVNULL隔离；这两项没有改变已有Icarus实际结果，不把后改工具的哈希替换到历史收据。

第一轮综合后的严格cell类型检查遇到40个Yosys `$scopeinfo` 层级元数据而停止，未执行该轮门级仿真；这不是数值失败。第二轮在写网表前删除仅用于层级记录的元数据，重新完整综合。失败result/log与原版runner快照保留，最终不掩盖此尝试。

```bash
cd /home/mxhanks/Projects/ChipContest-xu-score-opt
python3 tools/scripts/xu_gate_verify.py --sim iverilog \
  --out build/xu-score-s0-gate-reproduce-01
python3 -m unittest discover -s tests/host -p 'test_xu_gate_verify.py' -v
```

输出目录必须不存在。`result.json`记录全部输入字节SHA、工具可执行文件SHA/版本、真实编译/运行命令、工作目录、返回码、耗时、网表SHA与通用cell数、两路trace与全部日志SHA。通用网表由真实RTL经 `synth -top accel_icb_slave -flatten` 生成，不将RTL改名当作网表。

## 服务器现有DC网表回放

已知硬件候选综合网表位于：

`/storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/candidate-ss-02/mapped.v`

其原始SHA256为 `6f90b1ce3ea180eeb59c2438ddad74aea7ac0d87690608814b2fba7384dd5971`。本机没有该网表或厂家cell功能模型，服务器操作由root负责。本机脚本支持Python3.6、Icarus和VCS，不需要将6.6MB网表取回。

运行前需要完整模型集合：综合网表实际引用的标准单元功能Verilog（含UDP/必要include）和厂家 `RAMSP1024X16` 功能模型。已知服务器SRAM模型路径为 `/storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v`，大小90,818字节；另有3,233字节rtl模型。选择何者以及FUNCTIONAL等宏必须按实际模型检查后记录，不凭文件名代替功能语义验证。

外部模式CLI如下；标准单元模型和输出根用root确认的真实路径替换。所有 `--cell-model` 文件参与编译，`--include`支持模型include目录，嵌套quoted include也记录SHA；额外未编译模型附件可用 `--model-support` 记录。只有确认模型实际支持的宏才使用 `--define`。

```bash
python3 tools/scripts/xu_gate_verify.py --sim vcs \
  --netlist /storage2/2026contest/server4/s4_23usr/Desktop/xu-hw-optimization-20261102/ppa/candidate-ss-02/mapped.v \
  --netlist-sha256 6f90b1ce3ea180eeb59c2438ddad74aea7ac0d87690608814b2fba7384dd5971 \
  --cell-model "$xu_standard_cell_functional_verilog" \
  --cell-model /storage1/admin_public_dir/SRAM_Lib_2025/RAMSP1024X16/verilog/RAMSP1024X16.v \
  --out "$xu_new_gate_output"
```

该命令只在功能模型/网表确认后才有实际执行意义；此处不声明服务器门级回放已通过。外部模式缺少模型、网表SHA不符或输入运行中变化会失败。它比较公共接口，不依赖DC重命名后的内部路径。

服务器另有Formality `/eda/synopsys/fm/fm_2020.09-SP5/bin/fm_shell`。root可用reference RTL+同一SRAM adapter、标准单元/SRAM DB与DC mapped netlist做形式证明，明确两侧同RAMSP黑盒。此形式范围不包括被黑盒化存储的行为；需与厂商功能模型仿真证据分别报告。

本轮完整SoC门级回放仍待后续接入；wrapper层级PASS不会自动给出其结论。没有使用无效约束隐藏时序问题，零延时功能回放也不替代150MHz setup/hold检查。
