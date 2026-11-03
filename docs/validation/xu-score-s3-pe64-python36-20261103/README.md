# xu PE64 服务器 Python3.6 接口修复

仅将新增 contract 测试和部署 producer 的 `subprocess.check_output(text=True)` 改为 Python3.6 支持的 `universal_newlines=True`。bootstrap 的新目录改为 `ChipContest-s3-pe64-02`、`s3-pe64-accept-02` 和 `s3-pe64-deploy-20261103-02`，原 01 目录及其失败证据保留。完整 VCS launcher 的八步验收与四项完整 12 层控制不变；本提交没有改 Chisel、RTL、数值、向量、固件或旧 generated 文件。

`contract-replay.log` 是本地兼容接口复查，**没有在本机运行 Python3.6**。相同 subprocess 关键字拒绝 guard 对原 6f47746 的四项 contract 测试准确复现一项 `text` TypeError；修复后四项均 PASS。另检查 server 实际执行的三份新增测试与三份 PE64 producer，未发现 `text`、`capture_output`、`missing_ok`、`dirs_exist_ok` 这些不兼容关键字。它不能替代服务器新 main 的真实 Python3.6 / VCS 验收。旧 local raw snapshot 中的 producer 保持原字节，不按本次修复回写。

受影响测试可直接复现：

```bash
python3 -m unittest discover -s tests/e203 -p test_pe64_contract.py -v
python3 tools/scripts/xu_prepare_pe64_deployment.py --out /absolute/new/xu-pe64-deployment-02
python3 /absolute/new/xu-pe64-deployment-02/launch.py --prepare-only \
  --previous-source /absolute/ChipContest-xu-s3-pe32 \
  --source /absolute/new/ChipContest-s3-pe64-02 --out /absolute/new/s3-pe64-prepare-only-02
```

正式服务器必须使用新包 receipt 的 main commit、SHA256 和字节数；不得把 01 状态改成通过或复用其 source/output。新 bootstrap 保持精确七文件白名单、哈希检查、全新目录及独立 PID/log。新结果仍需真实 VCS direct / boundary、host68、numeric42、legacy5、synthetic1/2、real12 和四项 real12 控制，尚未形成新的吞吐、面积或能量结论。
