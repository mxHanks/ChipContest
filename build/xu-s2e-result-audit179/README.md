# xu179：S2e166返回原件独立本地审计

只读工具，不运行EDA、不读取凭据、不修改166runtime，不解除资格。仅服务用户保留的S2e/S2c。
Python标准库；不导入166/130运行时代码。`safe171.py`逐字节冻结171安全校验器，原包先验证完整成员集、路径、SHA与长度，再核本地已解包正文和source snapshot。

178实际回包审计结果是`AUDITED_TASK0_FULL12_INCOMPLETE_NOT_QUALIFIED`。task0原生PT实际完成，
原报告全SoC `0.0341 W`，原测量窗 `5788953333333 fs`（868343cycles），独立Decimal相乘为
`0.0001974033086666553 J`。同一155图加速器面积`0.3003096339 mm²`，低于`2.25 mm²`。
未知Q仍有5280bit，4256bit整窗TX；不能作为合格能耗或评分。178取样时full12仍`PREPARING166_NOT_QUALIFIED`，
12层能量保持null，不由单层外推。

新155使用原SDC+冻结forwarded-clock scope，历史S2c/130使用all-clock propagated方法。
JSON明确`analysis_method_mismatch=true`、`CONTROLLED_COMPARISON_PENDING`，新图相对历史图不计算节能百分比或支配关系。
原165共同方法的历史比较保留原map/area/energy身份；不将155面积拼接旧130能量。

复现实际178审计（主线程已核原包1313588B、110payload41417609B）：

```sh
python3 -B build/xu-s2e-result-audit179/audit179.py \
  --evidence-root build/xu-score-resume-20261103/preflight178 \
  --archive build/xu-score-resume-20261103/xu-server-two-candidate-preflight-20261105-178.tar.xz \
  --sha256 da981b5ed9d5c07524ece0b454fa7273f61e222917db9037d4155407e0a7ee1a \
  --out /absolute/fresh-audit179
```

后续full12终态使用同一CLI传新171schema包及其安全解包目录，不修改审计器。完整12层必须逐层成功、与task0同capture/target、
有真实成功task0先验、原生marker/version/rc、完整report receipt及同输入before/after记录。
输出`audit179.json`、task0/full12 CSV；只有完整12层才输出12层comparison CSV。不存在的阶段保持missing，不报告complete。
失败输出目录保留，拒绝覆盖；实际178前三个本地parser版本分别因role-vs-bytes、clock-check插入、超限source报告假设而拒绝，
`actual178-attempt01..03`保留这些本地审计失败，未把它们改称远程实验失败。

审查界限：

- `references179.json`冻结来自159原包的155 state/area/FM/verify/sta正文和165全部输入，完整参考索引SHA由审计器固定。
  155三SVF顺序、42338点完整FM、capture120/own89与155 target分列；正文可复核的原155小报告重新哈希。
- native336宏、22512pin的TSV/JSON逐行重建，精确67pin/宏、真实库ref、全pin唯一及方向一致。
  逐层bridge回执与旧130同capture统计/宏名双射连续；没有返回的SAIF、网表、SVF、库正文不声称本地重新读取。
- 原input前后守卫明确是**服务器记录回执**，不是本地外部输入全文rehash。
- task0共27份报告，21份返回正文重新扫描，6份只核稳定server boundedSHA与execution receipt：
  两份pin、source-no_switching_activity-before、source-propagated-after及unannotated-before/after大报告。
  不会把有界服务器哈希称作本地20GB重放。
- native power.rpt明确xu_soc_ppa_top、W单位，独立重算每层`P×duration_fs×1e-15`及总和，保留native报告舍入精度。

本地检查：

```sh
python3 -B build/xu-s2e-result-audit179/test_audit179.py
python3 -B build/xu-s2e-result-audit179/test_actual179.py \
  --evidence-root build/xu-score-resume-20261103/preflight178 \
  --archive build/xu-score-resume-20261103/xu-server-two-candidate-preflight-20261105-178.tar.xz \
  --sha256 da981b5ed9d5c07524ece0b454fa7273f61e222917db9037d4155407e0a7ee1a \
  --out /absolute/fresh-negative-check179.json
python3 -B build/xu-s2e-result-audit179/verify_manifest179.py
```

13项单元检查和15项真实178基础上的正/负检查涵盖无效单位、负功耗、重复值、FM范围/marker错误、
缺失full12、task0冒充full12、输入变化、原图/面积混用、SVF乱序、unknown清零、错producer、native非零返回、
诊断功耗篡改、server boundedSHA/metadata变化以及跨clock方法节能百分比抑制。
负例仅在审计器内存中修改副本，不修改原包、实验或服务器文件，不是新的EDA证据。
