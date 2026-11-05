# 两候选服务器复现材料

这些文件是实际运行155/166/190所用的冻结脚本和命令副本，保留字节及原manifest。当前状态与结果以根目录 [HANDOFF.md](../../../HANDOFF.md) 为准。内嵌历史README中的“待运行”、旧本地build目录和八候选描述是当时快照，不能作为当前启动指令。

| 目录 | 用途 | 外部前提 |
|---|---|---|
| `s2e155/` | 原134失败后新155修补、独立有序SVF/FM链 | 原89/109映射与工具树、原134五个已完成阶段、工艺库 |
| `s2e166/` | 同155最终图的task0和完整12层全SoC诊断能量 | 原120捕获、89/109来源、155图与FM/面积、原工艺库 |
| `s2c190/` | S2c own9c16共同clock方法的task0及12层诊断能量 | 原57捕获、own FM/PPA证据、原109工具树及工艺库 |
| `commands/` | 四个实际功耗命令JSON，含准确argv和入口SHA | 原服务器路径 |

不包含第三方库、SAIF、超大pin报告或网表正文；这些仍在服务器原根目录。普通新克隆可以核验包体与运行本地RTL功能；完整PPA重跑还需这些外部冻结输入。**不要将当前main当作原109 `--tool-root`**，冻结guard会拒绝该替代。`frozen130.py`从原109工具树动态导入activity/context/power模块；这是一项明确的服务器依赖。

原运行入口：

```text
~/Desktop/xu-campaign-batch154/timing155/resume155.py
~/Desktop/xu-s2e-final-power166/power166.py
~/Desktop/xu-s2c-common-power198/power190.py
```

只读检查现有队列：

```bash
python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" status
```

实际复现以 `commands/*.json` 中 `argv` 为准，前置 `python3 -B`。原输出目录已存在，脚本会拒绝覆盖。重跑必须选择新的输出目录并按同一总控登记；full12严格依赖成功task0，禁止同时直接启动和让总控启动同一实验。155脚本固定特定原失败与目录名，属于链路复核工具，不是通用重新综合入口。

本地只检查冻结字节，不运行EDA：

```bash
(cd tools/repro/server && sha256sum -c SHA256SUMS)
```

文件夹内历史manifest的SHA也保持不变。根目录的便携核验器无需任何被删除工作树：

```bash
python3 -B tools/scripts/xu_verify_handoff.py
```

`tools/ppa/xu_soc_implementation.py`是更早baseline-only工具，固定E203 f49身份；它会拒绝S2e a076。不要删掉guard或把该工具的旧面积算成当前S2e结果。新自动化如需通用S2e重新综合，应在新编号实验中绑定当前源、库、约束、独立FM与活动后再报告。
