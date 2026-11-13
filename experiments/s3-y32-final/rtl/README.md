# DMA4 与 21 颗结果宏的最终源合并

安装源位于子仓 `third-party/e203_hbirdv2/rtl/e203/perips/`。基础是子提交 `5470c5650f2d11d16e7c52cc96626d21030a3973` 的 ingress owner4/DMA4；存储来源为已密封 `docs/validation/s3-y32-compliant32-storage-20261113/wide-candidate-r2/`，manifest SHA256 `9461237a61158e94544cd98d0db491db72cbed6530a98c48da9d78a8289a2f73`。没有用旧 DMA 单在途整文件覆盖新 DMA。

三项生产 define 必须同时存在：`XU_MATRIX_DMA_SYSBUS32`、`XU_MATRIX_X_SRAM`、`XU_MATRIX_STORAGE_SRAM`。生产 `TEST_LOADER=0`（N2/PW1）；CPU、LSU、BIU、原 fabric 及其队列参数未修改。另七种 define 组合，DMA 与 core 的预处理 token 均与5470基础一致；`freeze.py` 实际重新比较并生成 `manifest.json`，不是关闭旧门禁。

合并只改动三个 RTL 文件：

- `LinearTileDmaCore.sv` 加入冻结 storage21/bias 无预取 slot 核心。相对冻结21版只增加组合 issue 列选择端口：`io_outIssueColumn[2:0]`、`io_outIssueResult[47:0]`；旧 `io_outColumn`/`io_outResult_0` 仍表示响应退休列。去除这三处组合接口增量后源码逐字节等于冻结21版，64个 `MacPE_Acc41` 算术源码不变。
- `xu_matrix_dma_sysbus32.sv` 保留4槽有序 `request_kind[4]`/`request_index[4]` 和指针/占用计数。`y_issue[3:0]` 在命令接受时推进0..8，核心 `outColumn[2:0]` 在响应成功退休时推进0..7。宏Q直接组合选择发出Y32，无 `y_payload256`、整行快照或结果FIFO。只有列7退休才复位issue、换宏行；slot/ACC所有权沿用冻结21版。首错后仍排空全部已接受请求及已经锁定的VALID命令。
- `mem_1024x16.sv` 使用冻结真实 `RAMSP1024X16` adapter。generic RAMSP 功能模型仅从 `tools/ppa/generic_ramsp_non_ppa.sv` 提供仿真，不进入生产综合源。

内部 W16+bias1+X16+result21=54颗；含既有CPU64/shared256预期374颗，必须再由整机/映射实际枚举。每任务实际物理零写为55040个16bit字；DMA MMIO计数54272只含W/X/result，bias768由宏端口观察器另列。bias地址768..1023未使用、不计已清零。

保留并逐项登记的必要数据状态见manifest：DMA的W低32bit、bias低32bit、一次bias主机40bit、一个锁定ICB单词32bit；core的一次bias物理写40bit与同步读低片32bit；算术ACC仍为64×41bit。这些具有单笔装配/操作数用途，无可复用参数slot或结果存储副本。

复现源身份与功能回归（编译最多1核）：

```sh
python3 experiments/s3-y32-final/rtl/freeze.py
python3 experiments/s3-y32-final/rtl/run_dma.py --vectors /absolute/path/to/vectors --out build/NEW/final-dma --jobs 1
python3 experiments/s3-y32-final/rtl/bind_regression.py --run build/NEW/final-dma --out build/NEW/final-dma-binding.json
```

回归复用已密封数值oracle，覆盖完整12、单行模式、读写错误、响应背压、末Y响应保持97拍、3种共同复位及随后新参数完整任务、W/bias两半/X/首末Y共7处地址定向错误及新任务恢复。独立C++台账核对4槽接受/退休占用；真实54内部宏逐地址零写/64ACC归零；新增只读断言证明整行336bit宏Q及slot/row在末Y响应前保持、issue与retire列相符。最终生产CPU/GPIO完整12由 `../validation/` 的独立流程给出，模块周期不冒充完整任务吞吐。

冻结21版60组合raw48/RNE证明可复用其不变算术与状态机部分；新增组合issue选择和DMA4合并以本轮完整数值及多在途协议回归验证。没有把旧21版CPU通过或1064.35开发吞吐移植给新整合源，也不据RTL通过宣称150MHz STA、面积或功耗通过。
