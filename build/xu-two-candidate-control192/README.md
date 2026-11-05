# xu192：两候选后续统一登记

只向已运行的原153总控追加186、190单层/12层、191尾包四项；不启动第二控制器、不直接启动EDA，不发signal，不重启旧worker。
仅保留S2e/S2c。单槽、内存/磁盘与许可保守策略均沿用已冻结153。

前置检查原153身份真实alive、scope163的两候选收敛回执和182真实177注册。
精确冻结四个job、顺序、依赖、唯一out和全部输入；登记前后绑定guard中的job原SHA，原runtime/controller/注册脚本/guard/旧回执也全程前后核对。
同ID已有注册只能逐字节相同；输出已存在而注册不存在时拒绝，不自动重试或adopt。
原失败、状态、日志和注册全部保留。成功只表示登记完成，所有资格继续NOT_QUALIFIED。

`build192.py`从186/190/191最终冻结文件生成确定性tar、逐文件manifest、固定四job guard和安装脚本。
安装先验证整包SHA、完整成员集、每文件SHA、所有目标已有字节与symlink，再无覆盖写入；安装本身不登记/不运行EDA。
上传`transport192.json`里的tar名与`install192.py`后，通过服务器VNC依次运行安装、登记脚本，capture确认真实回执。
实际登记回执：`B/two-candidate-followup-registration-20261105-192.json`。
后续日常单入口仍`python3 -B "$HOME/Desktop/xu-campaign-batch154/campaign154.py" status`。

本地检查（不访问凭据/服务器）：

```sh
python3 -B build/xu-two-candidate-control192/build192.py
python3 -B build/xu-two-candidate-control192/test192.py
```

等待原作者以外审查通过后才部署；本目录存在不代表已经在服务器登记。
