# xu198：两候选后续统一登记

只向已运行的原153总控追加186、190单层/12层、191尾包四项；不启动第二控制器、不直接启动EDA，不发signal，不重启旧worker。
仅保留S2e/S2c。单槽、内存/磁盘与许可保守策略均沿用已冻结153。

前置检查原153身份真实alive、scope163的两候选收敛回执和182真实177注册。
精确冻结四个job、顺序、依赖、唯一out和全部输入；登记前后绑定guard中的job原SHA，原runtime/controller/注册脚本/guard/旧回执也全程前后核对。
同ID已有注册只能逐字节相同；输出已存在而注册不存在时拒绝，不自动重试或adopt。
原失败、状态、日志和注册全部保留。成功只表示登记完成，所有资格继续NOT_QUALIFIED。

`build198.py`从186/190/191最终冻结文件生成确定性tar、逐文件manifest、固定四job guard和安装脚本。
安装先验证整包SHA、完整成员集、每文件SHA、所有目标已有字节与symlink，再无覆盖写入；安装本身不登记/不运行EDA。
上传`transport198.json`里的tar名与`install198.py`后，通过服务器VNC依次运行安装、登记脚本，capture确认真实回执。
实际登记回执：`B/two-candidate-followup-registration-20261105-198.json`。
后续日常单入口仍`python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" status`。

本地检查（不访问凭据/服务器）：

```sh
python3 -B build/xu-two-candidate-control198/build198.py
python3 -B build/xu-two-candidate-control198/test198.py
```

等待原作者以外审查通过后才部署；本目录存在不代表已经在服务器登记。

修正背景：192原包已安装但在第一项register前，因可变candidate-formality汇总state SHA变化而拒绝。192原包/脚本/失败保持。
新198包将190 runtime部署到隔离xu-s2c-common-power198，包含原09 FM state完整字节dadd3…，继续核原S2c native日志/SVF/RTL/601输入；不放松SHA、不替换历史、不改变map。
186/191运行字节保持相同，原190已上传版本保留，不覆盖。
