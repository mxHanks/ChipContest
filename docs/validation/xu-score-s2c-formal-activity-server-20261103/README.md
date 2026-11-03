# xu S2c 实际正式任务窗口单任务采集

真实服务器 task00 已通过成熟内部复位、完整清空、首源 REQUEST 到最终Y响应RETIRE的被动检查。正式elapsed **990656周期**，inclusive **990657周期**，实际SAIF窗口 **6604373333334fs**。本目录是一个任务的采集与重放证据，不是完整12任务能量或参赛资格。

冻结硬件/固件源主仓d276b55ffecbe8d620f9a361bf5d0859299ba7b5、子仓49a9436e01ea8ceeead94242e4a99c16e31a0865；工具为独立5e75581319f926642ee7dc214ad825f3564a8e39。SiFive GCC10.2/VCS Q-2020.03-SP2-6、signed16/40/48、原固定向量；HF150MHz、LF32768Hz、绝对相位1fs。默认没有INITIALIZE_MEMORY，没有force或驱动DUT。

本轮固定SoC长startup先保留原始未知状态；实际ACCEL.clk观察4594个asserted内部reset采样，first-ready cycle1201650，首次释放立即检查FIFO空/提交已知。CPU随后在cycle1201701开始33697个零写，在1403894最后一个零写，1403985发首源REQUEST并同拍接受。任务窗口包括之后的cursor/cache设置、完整16384个W、256个40-bit bias、6336个X、99行、3168组、3168个POP响应退休、50688个返回字和所有Y写响应。原99行/完整golden逐bit检查在被动observer内执行，没有从MMIO配对数推断实际两拍提交。

task00原TASK/PERF/AUTO诊断保持：25344输出、50688共享写、23232共享读；初始stall为0，正式elapsed是末RETIRE与首REQUEST的差，不额外加一个inclusive周期。这个带物理clear/nominal150/首REQUEST的新窗口不能与旧开发TB的986850周期直接当作架构回归比较。

实际归一化回执声明336宏/22512bit双射、原X/Z等统计保留，窗口时长相同。raw与normalized大型SAIF没有本地取回；`verification.json`保存其服务器SHA和归一化回执，不冒充本地重新读取/比较两份SAIF。未增加joint observer，本批无法据此解释全部Liberty条件功耗。实际S2c目标mapped SHA9c16d5ec6665cbfd2c0752c96e98d969d988e963d6ed2f729d81e6989efa7892及analysis SDC404c7de9…只是目标身份输入，本工具不由此证明该网表的STA或能量合格。

19个原始文件来自807588字节export22，SHA a6dd89390d2ba93c10f5d207e3111833d62bbab96772dee9787d6a7987401d7d；先验证全部142个原payload，再严格选择此终态task目录。大文件XZ无损保存，展开字节与原manifest相同，首轮失败在前一reset-host证据中保留。

离线检查用实际冻结5e工具重新执行其checked_log，重验本地完整d276/49a源blob/mode和工具共同SHA，逐字段复算window/reset/clear/TASK/PERF/AUTO并匹配原result。命令中的工具工作树须为原5e clean版本；后续root新增PPA profile不能代替该冻结共同工具。

```sh
python3 docs/validation/xu-score-s2c-formal-activity-server-20261103/check-evidence.py \
  --tool-root /home/mxhanks/Projects/ChipContest-xu-candidate-activity \
  --source-root /home/mxhanks/Projects/ChipContest-xu-s2c-autogroup
```

同服务器用5e工具的xu_candidate_task_activity.py、同源/vendor model/目标网表/SDC及同cross-prefix，在新out运行`--task-ids 0`。完整argv与输入SHA在raw/result.json，命令模板见相邻reset-host证据。完整12任务已另起新输出，每任务独立新进程；其未完成结果不纳入本目录。
