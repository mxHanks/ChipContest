# xu S2b packed2×16 串行装载候选

本独立父分支 `codex/xu-s2b-packed` 基于 S2a 主仓 `3c13930c1f36d6516577d33d8587d89a86b49563`，独立同名 E203 子分支基于 `faaa3e3d8b7832012fe48a8e27f684e5b5706306`。没有改动原 S2a 工作树、Chisel、PE、SRAM 宏/端口/容量、数值夹具或共享存储格式。候选使用原有 8 PE、signed16 X/W、signed40 bias、signed48 Y；不声称 S0 资格、正式服务器周期、PPA、保留或得分。

## 加法 ABI 与兼容性

全部旧寄存器、`CAPABILITY@050=58550003`、S2a 寄存器及 `STREAM_CAPABILITY@070=58530003` 原样保留。S2a 固件实际使用完整常量相等检查，故不能在该字增加 bits 而继续支持冻结 ELF。本实现将提案中的新 feature bits 放到独立 `PACKED_CAPABILITY@074=58500003`：高 16 位签名 `5850`，bit0=W_PACK32、bit1=X_PACK32。新固件按签名和所需 bits 包含关系检查 packed CAP，先检查原 CAP/STREAM_CAP；缺 packed 接口返回 -6。旧和 S2a 固件装载循环与探测保持原样。

| 偏移 | 新寄存器 | 语义 |
| --- | --- | --- |
| `05c` | W_PACK32 | WO，低/高 16 位分别写 W_CURSOR 和 W_CURSOR+1；读 0 |
| `068` | X_PACK32 | WO，低/高 16 位分别写 X_CURSOR 和 X_CURSOR+1；读 0 |
| `074` | PACKED_CAPABILITY | RO，签名与功能 bits 如上 |

复用 S2a `W_CURSOR@054`、`X_CURSOR@060`、`STREAM_STATUS@06c`，但不改旧/标量语义。W 的逻辑元素总数为 **16,384**（64×256），不是 65,536；每元素仍占现有共享内存 32 位槽。W 游标 `s=k*256+c` 映射为 `bank=s[2:0]`、`addr={s[7:3],s[13:8]}`，即 `bank[c%8][(c/8)*64+k]`。packed 要求偶数游标，故两元素处于同 addr 的相邻 bank 0/1、2/3、4/5、6/7；内部仍分两拍使用唯一标量写口。X 为当前行相邻两个元素。

packed 写要求全字 mask=1111、busy=0、偶数游标且有两元素空间。终点 16384/64 不回卷；非法 mask/奇数/越界/耗尽/忙时写报 rsp_err=1 并置 sticky error，不写存储、不推进游标。游标仍允许 S2a 的任意合法值，包括奇数与终点；对奇数可用标量写。所有新 data 读返回 0，cursor/status/CAP 读无副作用，busy 时同样可读。状态 error 的原 mask[0] W1C 保持。复位清游标、pending、error；不声称清除 SRAM。

接受时捕获完整 32 位数据、原游标、bank/addr 与两元素标志；第一内部时钟边沿只提交低半字，第二边沿提交高半字，之后游标一次加 2、rsp_valid=1。pending 期间不接受命令，START 等最后提交和前响应可退休后才可接受。被阻塞响应的数据/错误/有效保持，不重复写入或自增；保持原 valid 也不重收。标量仍只需一个内部提交边沿。旧指针与最近数据寄存器独立。

## 可选固件与精确契约

新 schedule `bias-hw-pack32-window`，仅该模式增加 `XU_HARDWARE_PACK32=1`。原六 schedule 的 define 列表和源码分支保持原装载行为。源共享 W/X 槽仍各读取一次；使用 `(uint32_t)(uint16_t)low | ((uint32_t)(uint16_t)high << 16)` 打包，即使选 `no-masks` 也显式截断，不能让源槽高半污染另一元素。首次 W 两次共享读先于 W_CURSOR 初始化，所有上传、内部提交、每行 X_CURSOR、轮询和 Y 写回仍处于原计时窗口；无预打包、跨任务复用或格式变化。

| 窗口内每任务工作 | 旧 H1+H2 | S2a | S2b |
| --- | ---: | ---: | ---: |
| W MMIO 写 | 32774 | 16385 | 8193 |
| X MMIO 写 | 12672 | 6435 | 3267 |
| bias 模式/上传 MMIO 写 | 770 | 770 | 770 |
| GROUP/W1C/START 写 | 9504 | 9504 | 9504 |
| MMIO 总写 | 55720 | 33094 | **21734** |
| 共享读 / Y 写 | 23232 / 50688 | 相同 | 相同 |
| START / done / MAC 有效拍 | 3168 / 3168 / 202752 | 相同 | 相同 |

结果 MMIO 读仍为 50688（轮询另计），精确输出 25344。旧 W 的首 BANK/ADDR 两写在首共享读前，完整旧 W 函数为 32776 写，不能把完整函数写数混进窗口契约。TB 按最终 packed 命令的最终响应退休结束装载阶段，包含两拍内部提交和背压。完整六阶段和仍须等于窗口周期。

## 验证

新增 packed 直接 TB 使用实际 core/SRAM，在下游采样边沿检查全 16384 W/64 X，独立 row/column 映射及全部 32 group 的 signed48 输出，覆盖符号极值、bank 对、255→下一 k、最后 pair、标量/packed/旧地址混用和指针独立、非法 mask/奇数/越界/耗尽/busy 写、读无副作用、W1C、捕获后毒化 live 输入、两个不同提交边沿、held valid、稳定响应背压与最后 packed 写后的 START。原 scalar/cached-wrapper TB 保留。host 检查器仍严格验收精确事务、六阶段及工作量，不为候选放宽。

```bash
python3 -m unittest discover -s tests/e203 -p 'test_*.py' -v
python3 -m unittest discover -s tests/numeric -v
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --firmware-schedule bias-hw-pack32-window --firmware-opt=-O2 \
  --firmware-experiment both-unroll-no-masks --out build/xu-s2b-packed-real1-repro
```

输出目录必须尚不存在。旧 ABI、S2a、S2b 应用同一版本 GCC/Verilator、本候选 RTL、固定 layer_00 向量、相同 O2/实验设置进行本地比较，不能拼接别的 S1 的面积/能量。

本地实际比较与哈希证据已保存在 [`validation/xu-s2b-packed-20261103/README.md`](validation/xu-s2b-packed-20261103/README.md)。同一候选 RTL 下，旧 ABI / S2a / S2b 的完整窗口分别为 **1,387,720 / 1,286,374 / 1,250,899 周期**；S2b 相对前两者减少 **9.859410% / 2.757752%**。三组固定 layer_00 的 25,344 个输出全部精确通过，host 54 项、numeric 42 项、三种直接 wrapper TB、5 个旧用例和 12 组旧固件装载字节兼容检查通过。实际改动的 Chisel 文件：**无**。这些是本地筛查结果，不构成 S0、服务器周期或 PPA 结论。
