# xu own130 原生 pin 流式独立审计164

164修复156在真实task00/before上的失败，不修改156、原130报告、SAIF、网表或任一历史回执。仅接受S2e own130精确终态：`prepared.json` SHA `99b5f66b5388395a6d5b70c3ad0c6482fd346d148b6715596c4c9499f205ed5c`；`execution.json` SHA `f9ae8ff27792632f857004b971fb1d206002f510ca97e41d9b66ddb9f142bc66`；12层每层5788953333333fs、868343 elapsed cycles，554个冻结输入。此包不接受S2c回执，也不套用S2c窗口。

156把`title is not None`和stat/SHA/bytes混在同一错误门。真实`source-propagated-before.rpt`是6204字节原生报告，以`No nets found with activity info from propagated\n1`结束，无`List of nets ...`标题。156因此报`complete source-report streaming identity differs`；该错误文字不证明源SHA或长度确有差异。原生file/default报告有标题及footer，各有49759/1100行；local archived报告与own130 execution中的SHA和长度一致。

164对源报告有两条独立门：

1. 每字节逐行SHA、完整长度、前后stat和原回执完全匹配；随后再完整重哈希验证before/after身份。头尾都参与，不截取正文后再求SHA。
2. 精确绑定请求source与native标签：file→file、default→Default、propagated→propagated、no_switching_activity→UNINITIALIZED。有列表时核对所有行和原footer计数；无列表时必须有唯一明确`No nets found ...`声明，不能用缺标题或缺列表推断空。重复/冲突声明、缺footer、错计数、错source及原生错误均失败。

只有保存的driver-pin列参与匹配。不存在load/input匹配不能证明没注释。结果保存原native声明/位置、footer/完整行数、完整流式字节数/SHA及before/after身份。

`frozen156/`保存原156完整bundle，逐文件保留原字节。`fixtures/source-propagated-before.rpt`是上述6204B原件，SHA `ee0cabb0db67061edc197cc1e69241e591f888154bf272ba1093c309f9c54efd`；来源与回执见`provenance164.json`。测试包含最小fixture在冻结156上精确复现同一异常，而164证明明确空列表；也验证真实file/default完整报告，以及完整流式SHA包含头尾。

原156逐行native pin提取和另一套raw-block完整重读原样继承（仅Python模块命名改164）：全部24份原native pin报告、540288个block、selected属性类型/文本/位置、diagnostics、测量TX/TZ/TB/IG、source membership及统计均对照。原始报告从不整份read_text/read_bytes，独立重读逐block限2MiB并检查无未表示尾字节。12层开始/结束都重哈希554输入、inventory、两份own130回执及自身runtime。

所有输出始终`NOT_QUALIFIED`。native `x_probability=0`不证明物理Q已知；本脚本不调用EDA、不修改未知活动、不修正能耗，不解除STA/RDC、综合后私有功能、精度或SRAM when/internal_power等资格门。

## 运行与总控接口

部署`manifest164.json`及其中`runtime_files`列出的六个文件；可同时部署整个bundle用于本地原件回归。入口执行前后都校验runtime/manifest SHA。

```sh
python3 -B /SERVER/Desktop/xu-s2e-streamaudit164/audit164.py \
  --campaign /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s2e-full-soc-power12-20261105-130 \
  --out /storage2/2026contest/server4/s4_23usr/Desktop/xu-score-optimization-20261102/s2e-native-pin-streamaudit-20261105-164
```

`--out`必须全新、在immutable campaign之外；不覆盖156输出，不在同一输出下自动重启。失败保留`state.json`和`failure.txt`。总控注册`result_state=out/state.json`，`process_contains`使用该唯一output_root。成功`STREAM_AUDITED_24_ORIGINAL_REPORTS_NOT_QUALIFIED`；失败`FAIL_DIAGNOSTIC_NOT_QUALIFIED`。只有服务器全新输出原state及全部原报告重读才证明真实完成；本地19项hostchecks不代表真实24份原报告通过。

```sh
python3 -B -m unittest discover -s build/xu-s2e-streamaudit164 -p 'test_*.py' -v
python3 -B build/xu-s2e-streamaudit164/check_bundle164.py
```
