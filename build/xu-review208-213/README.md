# xu213：统一登记208最终原包独立审查

结论：`68bc389`对应208本地审查通过，可由根线程安装并向原153登记。审查没有远程操作、原生EDA、第二controller或生产代码修改。原8项检查独立重跑通过，另8项集成/竞争检查通过。

最终gzip包266,728字节，SHA `19a29eea919fcd64f4f71482cae8a96477f1129676b6b527408f912e4444441f`，29payload。逐member检查类型/路径/唯一性，并与manifest和本地每份runtime正文逐字节匹配；包不包含模型/库/RTL/PDF正文。job207为4d5e913e...，worker a449b06d...，manifest65b5057e...；209使用已独审aa37599版本，入口e4fbb8dd...。两个native=true独立out/result/process namespace，依赖严格为191 terminal→207 terminal→209。

ancestry198来自实际199返回的26,092字节完整回执，SHA92ec0c8f...。本次审查指出草稿仅对old191作登记前SHA检查、未纳入after。根线程已修正：从固定actual198中选exactpath唯一old191 row，固定a4d97e89...及bytes并比当前identity，直接将这个原始固定row加入before/after records；不将新观察身份重绑定。旧2669包仅上传、未安装/登记，最终19a包保持独立。

完整main集成fixture使用真实153的identity、check_records、register和进程身份逻辑，只在临时目录构造状态与两job最小输入；用当前测试进程模拟已认证controller身份，没有启动controller或EDA。固定原177/191登记正文仍来自真实返回包；其它fixture状态和路径显式为host模拟，不能冒充服务器输入重hash。正例及逐字节idempotent通过；验证后job竞争、register复制期间job变化、祖先198/旧191在register中改变、重复191祖先、controller不活均拒绝。register中失败已出现的登记原件保留，未伪造最终成功回执。

原8项还验证installer实际安装/idempotent、冲突目的地在其它写入前拒绝、目录软链接拒绝、错误归档在写前拒绝、guard改动和现有冲突登记拒绝。installer在任何文件写入前完成整包SHA、所有payload SHA和全部已有目的地核验，不覆盖不同字节。

第一次213自有fixture误从final191选自身191登记；该包selector未包含自身登记，因此在setup失败。改用实际199原件后全部通过，失败日志原样保留；未改208源码。没有把fixture检查作为服务器已运行证据。

复现：

```sh
cd /home/mxhanks/Projects/ChipContest-xu-score-opt
python3 -B build/xu-native-query-control208/test208.py
python3 -B build/xu-review208-213/review213.py
```

实际服务器部署、两job状态和最终209原包仍须由根线程取回独立核验。所有诊断和回执保留NOT_QUALIFIED。
