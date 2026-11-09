# S3-Y32 next-bias demand 提前调度 goal

2026-11-09；用户要求继续。父基线 `f8c5c9ee631a9c3cbf62015dff98bad6939400f4`，E203 `0f852a35741881400a7e10b4760bdb8f300245ae`。当前8PE＋READY＋PACK32真实清零：每层payload 425,540、clear 66,802，合计492,342；完整12层5,908,104。

## 选择与边界

现有计数 fifo_full_wait=0、READY_WAIT=23,859，busy=3,168×68、MAC=3,168×64。并行RNE虽然可缩短capture，大部分收益可能被生产等待遮蔽。本轮先选择不新增数据存储或RNE路径的调度实验：当前组INIT取走bias后，在running期间提交下一组demand。

只改LinearAutoGroupCore的demand有效条件/标签和必要断言，并由同一Chisel生成RTL；当前core.group、INIT采样后take、结果FIFO、NICE snapshot后拍POP、8lane/256bit内部结果与32bit串行共享写均保持。组31禁越界；manual/cache关闭/register-cache消融保持。BiasSramPrefetch、MAC、CPU/LSU/BIU/仲裁/在途配置、固件/fences/错误检查、payload TB/模型/向量/golden不变。

全程不综合、不推送、不PR、不外发、不用官方EDA/VNC，主工作区和既往封存证据不改写。沿用11月11日冻结、13日定稿、15日假定截止安排。

## 完成条件

1. 新隔离sandbox与源码/工具pins。先核查INIT所有权、cache两槽、tag31和manual，真实RTL验证所有tag/跨行/FIFO背压/reset；原ready/数值/旧MMIO/物理清零相关回归。
2. 固件/工具/时钟/复位/输入/golden同条件单层；被动观察组间start/done及bias request/take。payload、clear、gap、busy/MAC/总线/NICE/READY各计数分开比较。不得将局部删除空拍直接当任务收益。
3. 仅对正收益候选完整12层304,128个Y32输出逐位核验。独立严格验证原始证据、source SHA pairs、ELF/image、完整工作量、clear、窗口；损坏证据负例必须拒绝。
4. 精确集成实测源码、独立审查、报告、紧凑/可复现证据与本地提交。若没有收益，保留负结果，当前最佳版本不变。

DEVELOPMENT_PASS_POLICY_PENDING、clear REVIEW_PENDING、FIFO payload physical zero UNPROVEN继续保留。两态Verilator与150MHz刺激均不构成四态/门级/STA/面积/能耗或官方验收。

## 完成结果

- [x] 隔离next-bias demand实现及同源Chisel生成；仅一项测量RTL变化。
- [x] 双侧各7行224组、INIT/tag、FIFO背压、3reset、manual、末组及768字真实clear后新行通过；69→68拍。
- [x] 既有autogroup/cached/READY/bias SRAM及双variant capability通过；失败诊断原件保留。
- [x] 正收益单层筛选后精确集成重编full12，304,128输出精确通过，171源无漂移。
- [x] 独立完整12对12、pilot/full12各20腐败负例、ELF/image及同条件工作量检查通过。
- [x] 独立源码/集成审查，报告与可复现证据准备；Git与封包最终身份由handoff外层收据锁定。

每层payload425,540→422,768，clear66,802不变。full12总5,908,104→5,874,840，省33,264／0.5630233%；payload减少0.6514076%。无综合/推送/PPA或正式资格结论。见[报告](s3-y32-bias-demand-results.md)。
