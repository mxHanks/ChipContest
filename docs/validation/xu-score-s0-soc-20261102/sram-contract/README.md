# xu S0：指定SRAM模型四态接口验证

此证据检查PPA存储映射的功能契约，不代表STA、门级全SoC、面积或功耗合格。固定平台RTL与原TB均未改动。测试使用实际厂商RAMSP1024X16 Verilog模型的`ARM_UD_MODEL`分支，四态Icarus运行，不使用开源替代模型；该分支关闭时序检查。厂商模型只保存在未跟踪的私有build目录，仓库仅记录身份。

实际模型SHA256：`81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51`。对照为E203固定提交f49a5fc914971426bd4530db39e270a84b41139f中的原`sirv_sim_ram.v`，仅将模块名改为`xu_reference_sirv_sim_ram`以便同台比较；原始及生成后SHA见result.json。

两组测试全部PASS：

| 检查 | DW×DP | 四态比较周期 |
|---|---:|---:|
| 每地址、每字节及随机交互 | 32×2048 | 21480 |
| 每地址、每字节及随机交互 | 64×2048 | 29672 |
| ITCM全部bank边界 | 64×8192 | 2560 |
| DTCM全部bank边界 | 32×16384 | 2304 |
| 512KiB共享RAM全部128个bank边界 | 32×131072 | 7680 |
| 原debug小RAM寄存器分支 | 32×7 | 1560 |
| 未初始化X转零 | 32×1024 | 1584 |
| 非整字节宽度及X转零 | 13×7 | 1300 |

覆盖同步读延迟、读地址/输出保持、禁用写、零写掩码、逐字节写、同址写后保持读值的更新、跨bank写不破坏当前读值，以及未初始化X。大容量测试遍历全部bank的首尾地址，并执行128组可复现的随机交互；它不宣称穷举全部内存状态。

`sirv_sim_ram`的大容量分支将每个bank/16位lane映射到真实宏，并转发合并字节以保留原行为RAM的同址写后读值；7字debug RAM继续用原寄存器语义，不能错误地映射到不匹配的宏。权重RAM使用另一个独立适配器，本测试不替代其门级/SoC检查。EMA=010、EMAW=00的功能运行不能替代其PVT时序资格核实。

复现（输出目录必须不存在）：

```sh
python3 tools/ppa/xu_sram_contract_verify.py \
  --vendor-model /absolute/private/RAMSP1024X16.v \
  --vendor-sha256 81b55d87d5e6821d44037d6f0290ec89c9edb9582eb1932957f181aefc300d51 \
  --out build/xu-score-s0/adapter-functional-replay
```

完整命令、所有源码及日志SHA、二进制SHA见result.json；原始编译/仿真日志和工具版本随附。文件清单排除自身，历史运行目录未覆写。
