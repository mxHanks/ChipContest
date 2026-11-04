# xu S2e activity104 本地工具原件

测试工具HEAD为 `ab241e356360a4ec1ab8764a89732eef34fe6707`，生产候选仍是main `5bf123bfead8f2a37f97f3234d4e40ce8201aae9` / child `a0767db69628ef30e53de2d1e93dd0360c0ccf76`。该工具只新增独立producer、observer和测试；旧S2c活动工具及common文件不变，没有Chisel修改。

最终本地11项unittest全部通过，用时149.554s，原始日志为包内 `activity-tests-v3.log`。包括：实际S2e wrapper的99行/3,168组完整signed16/40/48算术、25,344个LO及12,672个packed-HI响应退休、全部50,688逻辑字与POP覆盖；10个实际数据/协议破坏拒绝；真实20级reset链及8个故障；336个宏/22,512个直接alias路径elaboration；alias完整未知dwell保留与缺失/错误profile拒绝；实际GCC14.2 paired固件和原33,697清空wrapper编译；main/child隐藏tracked字节篡改拒绝；10,000个LF绝对相位边沿；receipt相等时仍重哈希磁盘原件。

全SoCelaboration使用明确只有端口/存储几何的open stand-in，未运行任务，不是vendor行为、VCS活动、映射等价、时序或能量证据。实际99行算术probe使用候选真实wrapper/计算RTL，但不含E203 SoC/vendor SRAM。GCC工具SHA与构建元数据保留；另一次相同SHA编译器的version输出明确标作recheck。原始本地v1/v2检查仍保留在build，不冒充最终11项范围。

交接增量bundle及installer已经在独立本地服务器布局中真实重建checkout，并通过完整源/工具guard，终态为 `TOOLS_READY_ACTIVITY_NOT_RUN`。它们只创建新的工具树，不启动任务。原89实际FM失败必须保留，104的own mapped/full-FM gate不放行；`--prepare-only`同样拒绝。修复后的实际own证明仍待另行完成，不能借用S2c网表或编写假网表。

包内60个原件，共484,842字节。`payload.tar.xz`为104,192字节，SHA256：

`feca29a14669007bbe41f4deb93041a96afd423dfd949586a7251b6566684669`

独立检查原件完整性：

```bash
python3 docs/validation/xu-s2e-activity-local-20261104/verify.py
```

每个原件SHA/字节数见 `manifest.json`；checker验证全体tar唯一普通文件、安全路径、成员精确集合及每个原始byte，不改变日志空白。包中 `handoff/`包含：

| 文件 | 字节数 | SHA256 |
|---|---:|---|
| xu-s2e-activity-tools104.bundle | 41,331 | `4a126e833a2253b217979235b4cd1177d51b9fb020bdde5e5c401ecd0d443dd8` |
| install_s2e_activity104.py | 3,817 | `a4964ad621830a26f59b9978a0052c848cc45bf04e0340e1063f28c3b16957f2` |

部署时两文件放到服务器 `$HOME/Desktop/xu-score-optimization-20261102/`，installer以原89工具HEAD `554267f0d34de30289ddd43babeb450da0d1dfc9`为prerequisite，在独立 `ChipContest-s2e-activity-tools-104` checkout部署。installer不读凭据、不操作网络、不修改生产源、不运行VCS。正式采集和复现命令见 [独立采集说明](../../xu-s2e-task-activity.md)，先task00，再依实际证明和同一上下文决定12项。当前没有服务器104活动或S2e正式全SoC能量结果。
