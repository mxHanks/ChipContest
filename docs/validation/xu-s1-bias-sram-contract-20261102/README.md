# xu S1 bias SRAM adapter 四态契约（2026-11-02）

`tools/ppa/xu_bias_sram_adapter.sv` 用三片实际 `RAMSP128X16` 替换一份生成的 `mem_32x40`，逻辑端口保持 `RW0_addr[4:0]`、`RW0_en`、`RW0_clk`、`RW0_wmode`、`RW0_wdata[39:0]`、`RW0_wmask[4:0]`、`RW0_rdata[39:0]`。每份逻辑 bank 占三片宏，八份 bank 对应二十四片宏；这是映射数量，不能作为面积收益结论。

每片宏的地址为 `{2'b0,RW0_addr}`；`CEN=~RW0_en`、`GWEN=~RW0_wmode`。逻辑 byte mask 逐 bit 取反接到低有效 `WEN`；第三片的高八位 `WEN=8'hff`、`D=8'h00`，始终不写入。默认 `EMA=3'b010`、`EMAW=2'b00`、`RET1N=1'b1`。寄存的 enabled-read 标志保证禁止/写周期之后输出为 `40'bx`，不暴露宏保留的 Q。

实际 Icarus Verilog 12.0 / `vvp` 运行 **PASS**。编译启用 `ARM_UD_MODEL`，直接使用外部私有 ARM `RAMSP128X16.v`，SHA256 为 `f9d6d881746681dacd4f3851467561e441ee7190776ab566b1f0a729aa3ddb4d`。没有复制厂商模型，也没有以行为宏替身替代它。参考为实际生成并复制到 E203 子仓的 `rtl/e203/perips/mem_32x40.sv`，SHA256 为 `e3df7fba6056a85473c88f85271d2e0a6d6634d343d4d71aeae857df0bf9c247`；runner 只重命名参考模块，原有读写逻辑保持原字节。

[原始结果](result.json)保留输入、runner、仿真二进制和日志 SHA256 以及实际命令。[仿真日志](simulation.log)记录 5,377 个检查周期：32 个地址各覆盖全部 32 种 mask，共 1,024 次穷举 masked writes；160 次逐 byte 未知数据写入；2,612 次 read 检查和 2,765 次 disabled/write 输出未知检查。还覆盖未初始化地址、连续读、边沿前地址改变、disabled writes、固定种子的随机序列。每个正边沿独立检查三片宏的地址、控制、数据、掩码及 margin/retention 引脚；每次读检查第三片未使用的高八位仍为未知。[编译日志](compile.log)为空，实际编译成功。[工具版本日志](tool-versions.log)保留原输出。

本结果只建立已知 address/control/mask 输入下的四态功能接口契约，包含未知数据与未初始化单元。未知控制或 mask 的语义不在检查范围。未启用 `INITIALIZE_MEMORY` 或随机初始化。没有 SDF、timing checks、full-SoC 等价、工艺角 EMA/EMAW 资格、面积、功耗或评分结论。

在有许可的相同模型环境内，从仓库根目录复现；输出目录必须尚不存在：

```bash
xu_vendor_model=/licensed/path/RAMSP128X16.v
python3 tools/ppa/xu_bias_sram_contract_verify.py \
  --vendor-model "$xu_vendor_model" \
  --vendor-sha256 f9d6d881746681dacd4f3851467561e441ee7190776ab566b1f0a729aa3ddb4d \
  --reference-rtl third-party/e203_hbirdv2/rtl/e203/perips/mem_32x40.sv \
  --out build/xu-bias-sram-contract-new
```

`evidence-sha256.json` 绑定本目录其他文件的原始字节；厂商模型和 VVP 二进制不提交。
