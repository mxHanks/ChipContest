# xu188：原 S2e SRAM 四态边际分类

这是只读本地分析，不启动 VCS/PT，不修改 Chisel、RTL、SDC、模型、向量或初始化。结果全部为 **NOT_QUALIFIED**。最终结果位于 `actual188-final/`。

12 个独立任务每项均验证 336 宏、22,512 个真实 pin bit 与原120规范 SAIF 的逐项统计完全相同；每项输出 5,376 个 Q bit。全任务结果如下，每行是**每项任务**的 bit 数，不是将12项当作同一时间轴：

| 组 | 宏数 | 全窗 TX | 部分窗 TX | TX=0 | CEN 全窗1宏数 | CLK TC=0宏数 |
|---|---:|---:|---:|---:|---:|---:|
| shared | 256 | 3296 | 768 | 32 | 108 | 0 |
| DTCM | 32 | 512 | 0 | 0 | 32 | 32 |
| ITCM | 32 | 448 | 0 | 64 | 28 | 0 |
| accelerator weights | 16 | 0 | 256 | 0 | 0 | 0 |
| 合计 | 336 | 4256 | 1024 | 96 | 168 | 32 |

每项共 **5280 Q bit 有 TX、4256 全窗 TX**，12项均一致。每项所有已捕获输入 bit 的 TX/TZ/TB 合计为0；这只描述已捕获宏输入的边际。Q 的 TZ/TB 为0，TX=0只代表该输出记录的0/1 dwell，不证明物理阵列存储全部已知。

CEN=1 与 Q-unknown 同时存在的**恒定控制推论**覆盖每项2656 Q bit（shared1696、DTCM512、ITCM448），但不能证明被关断期间功耗为零。冻结的原库 arc ledger 存在 `CLK` 的 `internal_power when RET1N & CEN`；即使输出不翻转，也不能豁免该内部条件、泄漏或下游标准单元能耗。DTCM 的 CLK TC=0也不等同于零功耗。

真实控制 pin 是 `CLK/CEN/GWEN/RET1N/WEN[15:0]/EMA[2:0]/EMAW[1:0]`；没有以 NCS、WEB、NAP、CE 推断别名。`controls.csv.gz`完整保存其T0/T1/TX/TZ/TB/TC/IG，缺省的TZ/TB仅在CSV中补显示为0，未修改原文件。

SAIF 只给各信号的边际，不包含全任务联合时间轨迹。`q-bits.csv.gz`给出 Q-TX 与 CEN=1 的精确边际交集上下界 `max(0,TX+T1-duration)` 至 `min(TX,T1)`，未假设独立、未重建概率。CEN全窗为1时上下界相等，可证明状态共存；无法凭此恢复每个时钟边沿上其他控制的联合条件。禁止 X→0、X→0.5、用 native getter `x_probability=0`或TC=0证明已知物理Q，也未豁免下游mux或标准单元。

数据边界：原120活动对应原89映射（0cfac…）与原130功耗记录。输入哈希与原164逐层 before/after 回执核对；返回的164服务器回执不是本机读取约20GB原始 pin report。旧89连线不能作为新155连线或门级功能证据。同一120捕获可用于指出155缺少哪些证据，但不据此认定155资格通过。

`analysis188.json`列出40个本机选定输入的分类前后SHA/长度、来源archive/manifest身份、8类代表macro、每层类别与待补的被动联合观测方案。代表仅供初步定位，不能代替336宏全部覆盖。最小后续证据是原120四态控制/A/D/Q的逐事件联合捕获，保留边沿前后与同时变化的采样来源，并与原SAIF边际核对；以及**同155** Q扇出、mux选择/所有权条件和Q未知期间下游观测。未执行该新实验。

产物：`groups.csv`48行、`q-bits.csv.gz`64,512行、`macros.csv.gz`4,032行、`controls.csv.gz`100,800行、`native-getter-difference.csv`144行。`groups_all12`是12项macro观测的数值求和，不是独立物理宏数。

两次失败 `actual188-attempt01/02`保持原样，分别为解析器的DURATION字符串比较、组间CSV列不一致；`actual188/`保留修复后首次完整成功结果。`actual188-final/`增补分类前后本机SHA守卫，并明确使用tx_zero字段；最终producer SHA、输出逐文件SHA在其`output-manifest188.json`及本目录manifest内。没有删除失败或改写原EDA证据。

复现（仓库根目录，本地 Python 3.9+ 标准库）：

```sh
python3 -B build/xu-s2e-unknown188/verify188.py
python3 -B build/xu-s2e-unknown188/test188.py
python3 -B build/xu-s2e-unknown188/analyze188.py --out /tmp/xu188-fresh-result
```

输出目录必须全新；失败写入FAILED188.json后保留。默认输入目录是已验包的`progress135`、`activity125`、`progress174`；可以用对应同名CLI参数指向相同原件。`sources188.json`被冻结，需同时保有其引用的三份原archive和逐文件manifest。成功复现后逐文件比对`actual188-final/output-manifest188.json`即可验证结果一致；日志不在其结果manifest内。
