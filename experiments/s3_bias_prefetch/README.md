# P3 单宏 bias 缓存与双组预取原型

此目录只用于取得同步存储协议的红绿反馈。主线 `src/`、生成 RTL、MMIO wrapper 与完整12任务输入均未修改。尚无 RTL 运行结果、面积或时序结论；最终交付仍须实现并验证真实 Chisel 模块。

## 与真实设计的对应

已核对：

- `src/main/scala/linear/BiasBankCache.scala`：256 个 raw signed40；5位 byte mask；组合式单值回读和8lane组输出。
- `src/main/scala/memory/Sram1024x16.scala`：单端口、同步 readWrite，Chisel `rvalid=RegNext(en && !isWrite)`。
- `third-party/e203_hbirdv2/rtl/e203/perips/Sram1024x16.sv`：现有生成 wrapper；因现有调用方未使用 rvalid，其端口中没有 rvalid。原型直接实例化这个文件，随后实例化的也是现有 `mem_1024x16.sv`，没有另写理想化 RAM。
- `LinearAutoGroupCore.scala`：目前 `launch=active && !running && produced<32 && count<2`，biasCache 用 selectedGroup 组合供数。
- `LinearComputeCore.scala`：bias 必须保持到 INIT 采样周期。`group_take` 代表该采样已完成的所有权释放，不能未经核对直接连 launch；后续 Chisel scheduler 必须在所需组 ready 后 launch，并保持该组到 INIT 采样。
- 真实 `accel_icb_slave.v` 的 CACHE_LO 形成 `{8'b0,wdata}`、mask `{1'b0,wmask}`；CACHE_HI 形成 `{wdata[7:0],32'b0}`、mask `{wmask[0],4'b0}`。新 adapter 的40位/5位命令能原样表达这两种访问。

## 接口与明确规则

`cmd_valid/ready` 接受一个锁存的 descriptor：8位 bias index、read、40位 raw data 与5位字节 mask。响应有独立单槽，valid/data/err 保持到 ready。最多一个 host 命令在途；旧响应同拍退休时可接受下一条。命令输入在接收后可以改变。

每个 bias 使用 SRAM 的 `3*index+{0,1,2}`：低16、中16、高8；第三字上8位写零。仅部分16位字节选择才执行 RMW；完整字写直接提交；mask为0跳过该字。最后一个物理字提交后才提供成功写响应。回读依次发出3次同步读，在显式 capture 拍采Q，拼出40位响应快照。总共只访问0…767，剩余256字未使用。

`compute_active` 期间的参数写被接受为持久错误响应，不访问 SRAM，不改变 epoch/暂存；读仍允许。与 `group_take` 同拍的参数写也被拒绝，防止计算启动与改参竞争。已接受的写不能撤销，集成时必须等待其完成后才允许计算侧启动。

组接口接受一个5位 tag。当前组和下一组各占一个 8×40 payload 暂存；标签、valid、epoch 另计。所需组未命中时先读24个16位字；命中后提供 group_valid/tag/epoch/data，保持到 take。若非最后一组，空闲端口自动预取 tag+1。每次完整组填充与 host 命令按轮换仲裁；host 响应背压不会阻塞独立的组填充，下一条 host 则等待响应槽可用。当前实现每组24次同步读、每次独立 issue/capture，共48拍；首组与未隐藏的等待必须在后续主线计时中保留。

每次合法参数写接受、invalidate 或 clear 接受都递增32位 epoch并清除两个slot valid。invalidate 期间禁止 group_take；在途填充检查捕获epoch，丢弃过期填充后自动重取已接受的 demand。参数写也使旧预取失效。若显式失效发生在一个已提供但未take的组上，该组valid可以撤回；消费者必须遵守失效输入与组接口属于同一控制域的约定。

clear 是独立 ready/valid 操作，仅在无计算、无已接受组 demand、存储引擎空闲时接受，连续清零全部768个物理字并在最后提交后拉高 clear_done一拍。已持有的 host 读响应仍是原接收操作的快照。reset 取消协议所有权/valid、epoch归零，不初始化 SRAM 或两个payload；复位同时屏蔽宏访问。reset 后必须先装载全部参数或执行clear，再请求计算组。reset 必须同时作用于消费者。

## 检查入口

由 root 在获授权的 Linux 环境执行，不在当前 macOS 本地运行 RTL：

```bash
bash experiments/s3_bias_prefetch/run_linux.sh /absolute/path/to/prototype-results
```

入口用 Python 生成3072个事务，运行3项参考测试，再通过 Icarus 编译/运行真实现有 SRAM wrapper＋本目录 adapter/TB。输出只在指定目录。`BIAS_PREFETCH_PASS` 是独立原型协议通过标记，不是主线 P3/SoC 通过。

自检覆盖：

- 全256个 bias 索引、全部32种mask、正负40位端点、每次写后回读、随机合法/计算期间非法写。
- 接受后修改命令输入；响应随机延迟退休；逐笔核对真实宏端口的地址/值、完整写覆盖、RMW读覆盖；物理写未完成时不能返回响应。
- 全32组/8lane、保持current时预取next、连续组命中、host/group争用、在途invalidate后重取、拒绝写不失效、合法写后丢弃旧next。
- clear计算互斥、768字清零与全256值回读；reset丢弃组所有权并保留SRAM数据。

本地只运行过 Python：3项通过。RTL结果由 root 运行后记录，当前保持待验证。

## 后续迁移

1. 用真实 `memory.Sram1024x16` 实现相同 adapter 状态机；优先把 `BiasBankCacheTest` 的mask/回读检查迁为命令与退休协议。
2. 保留旧 MMIO 偏移与LO/HI byte-mask映射；wrapper锁存descriptor，并延迟所有写/读响应直到 adapter 完成。不能继续用原来的组合 cacheReadData 返回。
3. 修改 scheduler：请求 selectedGroup、核对tag/epoch并等待group ready后才launch；保持 bias 至INIT采样后take；再启用next预取。
4. 给模式切换、任务清空、参数写与reset接入明确失效。验证旧profile、全12任务、partial write、背压、首组延迟与完整测量区间，再做同库面积/STA。

本原型未作吞吐或面积优化。24次读的两拍串行实现用于先闭合Q有效时刻与所有权；后续可用真实rvalid将同步读流水化，须保留等价检查再比较收益。
