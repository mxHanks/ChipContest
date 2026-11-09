# S3-Y32 PACK32真实清零优化 goal

2026-11-09。用户要求继续。固定父基线`51a021c8bfc9649e2be4be1292735181f7a551e8`、E203`0f852a35741881400a7e10b4760bdb8f300245ae`，父分支`codex/s3-y32-packed-clear`。基线READY/stream/bias完整12层7,487,304拍，每层payload425,539、scalar clear198,403、gap102。

本轮用现有公共MMIO PACK32接口减少清零选择／地址调度。收益单列为任务前真实清零开销变化，payload按原窗口单独报告。官方清零计分政策仍REVIEW_PENDING，FIFO payload physical zero仍UNPROVEN。

## 方案边界

- 不改任何RTL／CPU／LSU／BIU／仲裁／在途配置，固定Y32/48bit/RNE、payload固件main/accel/header/contract/parser、原payload TB、输入/golden与工具时钟复位。
- 原`tools/ppa/s3_task_clear_protocol.py`逐字保留。新增可选helper和`--clear-profile packed16-mmio`；默认scalar仍执行原配方。
- 新初始6个ID／STATUS／capability读精确验证；CACHE_CTRL=0，W_CURSOR=0后8192次W_PACK32=0；保留原bias SRAM768物理word/staging640bit及legacy8×40bit路径；X_CURSOR=0后32次X_PACK32=0。
- fence后先检查STREAM_STATUS=0，最后STATUS=0响应作为clear completion proof。SRAM模式写8252、读8、命令／响应8260。减少的是MMIO事务，实际物理W仍16384字、X64字、bias768字、legacy8值。
- W逻辑cursor到bank/address是原硬件映射，不能假设顺序物理地址。每个真实core写edge与16个W SRAM宏RW0写edge分别核验；packed命令不能直接补2次coverage。
- clear后cursor末值与旧地址选择寄存器可不同，冻结payload源码必须明确重新初始化cursor；所有pending／实际写／响应必须在首source VALID前排空。NICE必须真实idle。

## 完成标准

1. 新helper／实际物理observer及真实wrapper probe：仅公共MMIO先把所有W/X/bias/legacy填为非零，再arm清零；检查前态非零、每个真实零写边沿／唯一地址与完整后态。禁止force、层次写内存或依赖fresh零值。
2. 错误cap/mask/bounds、漏写／重复／非零高半、早proof／早source、背压、复位等有意义负例；未完成或失败保留原件，不计PASS。
3. 可选campaign集成、默认scalar兼容测试；冻结源码后同条件单层筛选，实际报告payload/clear/gap。generated clear改变ITCM布局可能影响payload周期，测量不做padding调相位。
4. 有真实payload＋clear收益后集成并新编译完整12层，逐位304,128输出，保持物理工作与所有原payload／LSU／OITF／末响应／窗口检查。
5. 独立严格对照固定baseline170源，候选仅campaign.py改变及新增helper171源；generated C/TB分别由已pin helper精确重生成验证，明确策略差异，不能假称clear C相同。两边ELF/image独立核验，物理工作/输入/工具/时钟/复位一致。
6. 独立审查、失败原件、限定回归、本地提交、紧凑和便携证据、回退收据。

全程不综合、不推送，主工作区和既往封存证据不改写。仍按11月13日交付、11月11日冻结安排。

## 完成结果

- [x] 可选PACK32 helper／真实物理observer及非零前态probe。
- [x] 22实际wrapper场景和3个隔离RTL漏写fault mutant；失败／中间版本原件保留。
- [x] 默认scalar兼容与23项campaign测试，原RTL／payload代码不变。
- [x] 最终集成完整12层304,128输出通过，171源精确匹配。
- [x] 独立严格12对12、13项损坏证据负例、生成C／TB与ELF／image核验。
- [x] 本地提交／紧凑与便携证据／回退材料，最终封包与Git身份由外层handoff收据锁定。

每层425,540＋66,802，full12 7,487,304→5,908,104，净减1,579,200拍／21.0917040%；收益来自真实清零调度减少，payload合计多12拍。正式clear计分政策仍待审查。见[完整报告](s3-y32-packed-clear-results.md)。
