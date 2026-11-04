# xu实际118/119：完整12任务原生pin报告独立重放

服务器actual112已完成12个任务、24份compact与原生PT报告的独立重放。**本归档证明原件身份、统计交集和重放范围；不证明物理Q已经已知，也未使全SoC能量或比赛资格合格。**

| 原始导出 | 压缩字节数 | 载荷项数 | 载荷字节数 | SHA-256 |
| --- | ---: | ---: | ---: | --- |
| `payload.tar.xz`（118） | 146,208 | 42 | 6,608,026 | `5575e63f83f67ada7dda6d5b1a571d8a54c274df0d95f0fb4c7f9423d97b94f0` |
| `supplement119.tar.xz`（119） | 872,692 | 59 | 46,164,286 | `ec9657776616f72bc98bb7c876acf71a77bdc9614ab31b9581f4c780c3acb934` |

两个包原样保存，内部/外部manifest一致，原始文本空白未改写。118的扩展名白名单遗漏了8份`.compact.jsonl`样本；119将它们补齐，且112已返回的其它输出逐字未变。现在112的30项output-manifest载荷及output-manifest本身全部在119中。两个包还附带104/115输出，本目录仅核验这些伴随文件的字节身份，其功能、活动或诊断结论由相应专门归档负责。

## 在服务器完成的重放范围

112终态为`REPLAYED_24_COMPACTS_AND_ORIGINAL_REPORTS_NOT_QUALIFIED`。原生产工具为30,407字节，SHA `b878d55ca38fb13a87853a46e69d5d221bb23d1af3a14b10020ec3eb7bbfa6ae`。它不调用EDA工具，逐行交叉检查93的compact记录、原PT57报告正文及输入SAIF，而不是重新估算或修正能量。

- 完整12任务×2阶段×22,512 pins：**540,288条原生pin记录**。
- 逐字重放原生报告：**19,326,860,762字节**；每个block与完整报告SHA均核对。
- 重新核对24份compact：**131,728,568压缩字节**。
- 每任务完整映射SAIF含137,439条signal记录；22,512个选定宏pin与measured输入逐项对应，共**270,144个选定SAIF pin记录**。
- 每阶段统计都与原93摘要一致。12个task-complete及唯一终态标记存在；118导出时原launcher PID2501已不存在。

本地校验重新核对12份任务摘要、24阶段统计、全部交叉计数及原PT57/93身份，另对已返回的8份原报告块与8份compact行执行独立逐字/属性/范围检查。**完整19.3GB报告、131.7MB compact及全部原映射SAIF没有全部返回本机；本地PASS不能描述成在本机重新重放全部540,288行。**

`references/`保存原PT57 execution及93终态JSON的无损XZ副本，其解压字节分别绑定原SHA：

```text
PT57 execution.json  45acb972f44b2a3009dca012836db6f2bde0a95d1de538d085fa27f882c6a3b9
93 state.json        1751f3d28c8a67ea5fc3d3ffe78d9f3b905f33a9d9011e9e4f0ba3726bd72abb
```

这些既有原件身份把每份original/compact/measured/SAIF/source-driver报告的收据逐项相连，不以新摘要代替旧原件。原PT57 prepared的SHA为`cb363beafeac51329aab8f04843999021c17cf05dd22a1d1f3ee505ceb70a103`，原93抽取器SHA为`784841b104370b5cf15d7b4f7ed72cce56d498214bbb4ef511e59e39ad868347`。

## 输入SAIF与原生属性的实际交集

12任务的每个阶段均有17,136个SRAM输入pin、5,376个Q输出pin。输入SAIF中5,280个Q的TX>0，其中4,256个Q的TX覆盖整个窗口；其它pin的TX为0。与此同时，原生getter报告的`x_probability=0`覆盖全部22,512个pin。

下表为**一个任务的一个阶段**；每一行在24个阶段均成立，总数为该列乘24。

| pin类别 | 输入SAIF TX | 原生SP类别 | 原生TR类别 | pin数 |
| --- | --- | --- | --- | ---: |
| 输入 | 0 | 0<SP<1 | 正 | 12,168 |
| 输入 | 0 | SP=1 | 0 | 1,864 |
| 输入 | 0 | SP=0 | 0 | 3,104 |
| Q | 部分窗口 | 0<SP<1 | 正 | 656 |
| Q | 部分窗口 | SP=0 | 0 | 368 |
| Q | 整个窗口 | SP=0.5 | 0 | 4,256 |
| Q | 0 | 0<SP<1 | 正 | 64 |
| Q | 0 | SP=1 | 0 | 1 |
| Q | 0 | SP=0 | 0 | 31 |

这里SP/TR是原生`static_probability`/`toggle_rate`属性，不是由SAIF的TX反推出的物理状态。全窗口TX的4,256个Q明确记录为输入`T0=T1=TC=0, TX=6604373333334`，同时原生值是`x_probability=float:0.000000`、`static_probability=float:0.500000`、`toggle_rate=double:0`。两个阶段各返回了一份此类原生样本及其compact行；选定source报告的确切driver列也记录其属于file列表。

**这证明两种记录之间确有上述交集，不证明物理X变成了0或1，也未证明PT为什么得到这些值。** 是否传播、归一化、默认或忽略TX，仍需独立证据；不能把原生x=0直接用作活动完整或能量合格的依据。source列表的检查限于保存的driver列：输入/load pin没有命中该列，不能被解释为没有file注入。

## 保存的其它边界

每任务`before`报告都保留3条lazy engine诊断，包括switching propagation、averaged power analysis和power calculation。所谓before/after仅指**显式`update_power`调用之前/之后**，不是两个同步的物理状态快照。选定20类属性的type/value在前后22,512个pin上逐项相同，不能因此推断全部设计状态相同。

每阶段`relative_toggle_rate`有2,272个原件缺省项、12,888个正值及7,352个零值。8份本地样本包含2份该属性不存在的原块；校验保留`ABSENT_FROM_ORIGINAL_REPORT`，没有把缺省转换为0。`activity_checker_status`是原生字符串，不是file/default/propagated来源字段。

完整映射活动、物理Q状态解释、150MHz资格与正式全SoC能量仍未因本审计闭合。本目录没有修改活动、RTL、工艺模型或原PT运行。

## 复核与复现

```bash
python3 docs/validation/xu-score-native-audit118-20261105/check-evidence.py
python3 docs/validation/xu-score-native-audit118-20261105/check-evidence.py \
  --extract /absolute/path/new-xu-native118
```

第二条要求目标目录不存在，并分别解包至`actual118`、`actual119`。校验器验证两包101项载荷身份（含重复原件），重算24阶段交叉统计，检查30项112输出完整性，并独立解析8对原生样本。PASS始终伴随`NOT_QUALIFIED`，范围仅为上述证据检查。

`tools-manifest.json`绑定4份公开生产/导出脚本。原112启动命令为：

```bash
python3 "$HOME/Desktop/launch_native_pin_audit112.py"
```

该启动器调用实际记录在driver/state内的以下参数：

```bash
python3 -u "$HOME/Desktop/xu_native_pin_audit112.py" \
  --campaign "$HOME/Desktop/xu-score-optimization-20261102/s2c-full-soc-power12-20261104-57" \
  --native-root "$HOME/Desktop/xu-score-optimization-20261102/s2c-native-pin-stream-20261104-93" \
  --output "$HOME/Desktop/xu-score-optimization-20261102/s2c-native-pin-audit-20261104-112"
```

输出已存在会拒绝覆盖。复现需使用相同SHA的服务器原始输入，在干净快照或新编号目录执行并保存新身份；不能删除或覆盖112原证据重跑。118/119分别由`tools/export118.py`、`tools/export119.py`导出，原压缩包与输出目录均不可覆盖。
