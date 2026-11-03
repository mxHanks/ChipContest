# xu S3：单权重阵列32列并行独立实验

基点：主 `d276b55ffecbe8d620f9a361bf5d0859299ba7b5` / 子 `49a9436e01ea8ceeead94242e4a99c16e31a0865`，独立分支 `codex/xu-s3-pe32`。固定CPU、互连、共享512KiB SRAM、signed16 X/W、signed40 bias、signed48结果与任务向量；不预报4倍整体加速或得分。

生产Chisel为 `src/main/scala/GenerateRTL.scala` 和新增 `src/main/scala/linear/XuParallelCore.scala`（32/64可配置几何及W bank、compute、bias、scheduler/FIFO）。本实验只生成/验收32PE，64PE仍待后续独立实验。复用原MacController/MacPE/XRowBuffer/Sram1024x16。原13个生成SV（含S2c top）及原accel_icb_slave.v字节保持；新增四个XuParallel*32.sv及手写xu_pe32_icb_slave.v。固定perips仅在原加速器实例处以XU_ACCEL_PE32选择新wrapper，默认不开define保持旧实现。

32PE、8groups、每bank512×16逻辑W，总16384元素/32KiB。每bank用一只1024×16 1RW宏接口，共32只W宏（旧16只），物理64KiB，2倍padding；高地址位接0，不能用padding增加参数容量。全SoC预期352宏（固定320+W32），需真实映射核验。指定128深宏可以每bank四只、总128宏精确容量，但其外围代价需另实验；此处未实现。bias仍256×40寄存器，FIFO为两槽×32×48bit，只有一套W阵列，未复制四套旧core。

旧load b=bank、a=oldgroup*64+k映射column=(a>>6)*8+b，新bank=column%32、新addr=(column/32)*64+k；遍历旧地址恰覆盖32×512。共享row-major packed/stream顺序不变。旧manual g选widegroup=g>>2，仅enable/read(g%4)*8..+7八lane；cached及手工bias都映射该子块，不丢弃24路无用MAC。结果selector于capture锁存，修改下一GROUP不改变先前结果。旧auto仍32groups、8lane/组，经同一32bank核心计算。

新PE_CAP@07c=58332001；wide STARTROW/STATUS/POP@0d0/0d4/0d8；32lane结果窗口200..2fc。旧CAP/auto/window保持，窗口或POP与行模式不符报错。START锁存模式，active至最后成功POP响应退休拥有operand，FIFO满禁止launch；读取response快照在背压下稳定，POP只退休放行，旧错误响应不污染新行metadata。

`--accel-variant pe32`独立于firmware schedule，进入实际编译宏、cache key和result身份。新schedule `bias-hw-pe32-autogroup-window`：每行8group/POP，每任务792 starts/dones、50688 MAC beats、13121 MMIO写；shared读23232、写50688、输出25344保持。旧8lane调度仍202752 beats。TB逐拍观察32个实际MacPE.io_enable并popcount，验证每任务1622016个enabled-lane MAC，交叉核对core活动输出；不能将旧mac_fire固定乘32。

本地先跑Chisel core及新wrapper的宽/兼容direct，再用同GCC14.2.0/Verilator5.032完整真实layer0比较。开发TB为4ns HF/66ns LF，窗口首shared读接受到final-Y响应退休；ITCM/共享预载在窗外，每任务W/bias仍重新上传。本实验不替代正式clear/首请求窗口、150MHz STA/映射一致性、服务器真实12层VCS或全SoC能耗。面积/功耗不能由PE数或padding推算。

```bash
scala-cli run . --server=false --jvm system -M GenerateRTL -- XuParallelAutoGroupCore32
scala-cli test . --server=false --jvm system --test-only linear.XuParallelAutoGroupCoreTest
python3 -m unittest discover -s tests/e203 -p test_pe32_wrapper.py -v
python3 tools/scripts/e203_soc.py --mode real --tasks 1 --sim verilator \
  --accel-variant pe32 --firmware-schedule bias-hw-pe32-autogroup-window \
  --firmware-opt=-O2 --firmware-experiment both-unroll-no-masks --out /absolute/new/xu-pe32-real1
```

同物理PE32对照改schedule为bias-hw-autogroup-window；物理PE8基线再改variant为pe8。输出目录须全新。server_accept.py新增同一variant，baseline五个原始assembly通过make宏选择实际新wrapper；VCS host强制PE32两个direct，缺工具失败而非skip。默认旧命令和旧ABI语义保持。原始实验日志、源身份和实际周期随后单独冻结归档。
