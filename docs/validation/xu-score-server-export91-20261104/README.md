# xu 实际91：清理79、复位86及原生报告抽取88

本目录返回**83项实际原字节**共22,295,520字节，派生tar.xz为295708字节，SHA256 `92a994c6d401d582f94653a68f709fb9a4f41658286860997016db18d4fa8bd8`。上游完整91在本地经112项SHA核验，tar.xz SHA为`dea1f6b6a63b2e73ec63d877a991797e30da2d622935d17ba8b84ec6b5a46df0`；其中29项已安装工具手册正文仅在本目录保留名称/大小/SHA，详见[source-omissions.json](source-omissions.json)。本目录不自称已返回112项正文。所保留日志、状态、Tcl和报告不改写；[source-manifest.json](source-manifest.json)与[payload-manifest.json](payload-manifest.json)给出包含/省略的完整划分。

- **清理79**：在实际73网表上，逐个核对33个native `is_sequential=false`、完整输出集合仅自身相连且父design唯一的叶单元，全部preflight完成后才删除。DC/PT各return0、唯一marker、errors=[]。新mapped SHA `5a1e30ca4c9f14a8eabb349575a9f3069038c15ec38577edeacf0c9613cfa048`；min-cap从33降到20，0 max-cap。新上游66项中20项source-only，恰与20个min-cap pin相同。五项reset removal、两项PMU recovery unknown及27124项untested仍在。这个分支仍是50→63→73→79，**不含reset61的40个反相器**，未取得最终完整链Formality；不能合并两分支数据宣称通过。
- **只读复位86**：网表/两SS库/SDC/proposal before-after身份相同。16项显式起点查询确认：外部HF reset到全部5个reset端点的recovery均无路径；其removal有路径。LF watchdog到3个AON reset端点的recovery均有路径（30516.769531ns）。实际diagnosis仍有两条SEL-005；其他两次文档查询无错误，原件完整保留。现有结果支持继续调查HF→LF边沿展开，但并未证明PTE-052就是根因，也未发现可直接采用的documented horizon变量。缺路径仍是UNKNOWN。
- **原生属性抽取88**：实际失败`required native attributes missing: relative_toggle_rate`，没有完成任何task。工具按检查条件停止，不将属性缺失替代为0。此失败原样保留；首次失败block将在新的只读92定位，后续修复必须用新输出，不覆盖88。
- **模型提取90**：此91快照时，明确核对进程130967仍存活且状态RUNNING。它只选择原始S40压缩包中4个RVT Verilog成员到独立私有目录，正文不返回。此快照不能证明提取完成或任何mapped仿真通过。

本项没有修改Chisel或生产RTL，也没有完整150MHz/能量/评分资格结论。工具入口与实际执行Tcl均保留；复现需为脚本换全新输出编号，禁止覆盖历史：

```bash
python3 "$HOME/Desktop/launch_min_cell_cleanup79.py"
python3 "$HOME/Desktop/launch_reset_clock_expansion86.py"
python3 "$HOME/Desktop/launch_pin_stream88.py"
```

离线验证及原样提取（目标必须不存在）：

```bash
python3 docs/validation/xu-score-server-export91-20261104/check-evidence.py
python3 docs/validation/xu-score-server-export91-20261104/check-evidence.py \
  --extract /absolute/path/new-xu-raw91-subset
```
