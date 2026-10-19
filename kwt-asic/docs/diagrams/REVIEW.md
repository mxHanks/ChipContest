# 工程图册交付检查

日期：2026-10-15，Asia/Shanghai。检查对象为五页工程图册及其PDF、PNG、SVG、draw.io和图元JSON。本文的PASS只表示图册质量、技术表述及文件一致性通过，**不增加RTL、真实数据精度、SoC或PPA的验收结论**。

## 技术表述检查：PASS

- 首页以需求确认和基线登记起步，C数值、B硬件、A系统三路并行，经功能/数值、E203完整任务和指定工艺分析汇合；资格检查之后才进行公平对照，优化改动需重新实现、验证和选择。
- 三人交接明确版本、命令、数据哈希和日志，接收者复现后才完成；D12未合格停止新增优化，D16未验候选不提交，D17冻结。
- 已验证范围限于迁移首版、`kwt_linear_engine.sv`默认8路、位精确模型及所列静音回放。正式数据精度、官方E203、指定SRAM和工艺仍待验收。图册状态快照中的单行流水优化文件仅lint，双行2×8架构仍为未实现候选，两者均未纳入本图册的已验收基线；后续优化验证不自动改变本图册的状态快照。
- 12层是12项独立前馈任务，各层X来自对应Attention、残差和LN1之后；未将上一项Y直接串接为下一项X。Golden只有检查路径，硬件实际接收X/W/b并计算结果。
- 系统图区分主机离线、官方E203平台和计算加速器，未假定DMA或额外DDR。补全平台适配到写回流控的ACK，系统DONE在全部写事务确认后产生，区别于核心done。
- 双行候选包含共享W、奇偶行X、16个MAC、结果快照和行重排双缓冲；缓冲图标明选择空闲组写入、选择就绪组排出。99行的尾组关闭无效第二路，只产生最后256项，保持总输出0..25343的行优先顺序。
- 49.5%明确为内部W读字数推导，6KiB明确为两组结果缓冲逻辑容量，均不是工艺实测结论。
- 原始整数码用于位一致，解码值用于浮点误差。README补齐逐层跨样本汇总NRMSE、各性能任务误差、有限输出、增量面积和同窗口全系统功耗口径。

## 版面与格式检查：PASS

| 项目 | 实际检查结果 |
|---|---|
| PDF | 5页，960×540pt，每页16:9；无加密、无JavaScript |
| 字体 | 实际中英文字体Droid Sans Fallback、DejaVu Sans及粗体均嵌入；PDF列出的基础Helvetica为空白默认资源 |
| PDF文本 | 351条图元文字全部可提取，逐条与JSON核对通过 |
| PNG | 5张，均为2560×1440；从最终PDF渲染 |
| SVG | 5个XML解析通过，viewBox均为1920×1080，文字与JSON逐条一致 |
| draw.io | 5页XML解析通过，页ID、图元数量与JSON一致；框、文字及线段保留可编辑对象 |
| 几何边界 | 351条文字及全部矩形均在页面内，卡片文字宽度通过生成器约束 |
| 目视检查 | 全5页检查文字、边框、箭头和页码；首页最终改名后再次渲染复查，无遮挡、截断或乱码 |
| 技术审阅 | 对照需求、方案、三人计划、数值契约说明及baseline RTL，已完成上述修订 |
| 封包 | manifest逐文件SHA-256与zip中解压字节一致；zip CRC检查及外部SHA256SUMS核对通过 |

本轮未启动新RTL功能仿真、SoC或工艺工具。Draw.io按XML对象结构核验，未声称在每种第三方编辑器、操作系统和字体环境中测试；跨系统展示优先使用嵌入字体的PDF或PNG。

## 复核入口

```bash
python3 scripts/docs/render_engineering_diagrams.py
pdftoppm -scale-to 2560 -png output/pdf/kwt-engineering-atlas.pdf docs/diagrams/atlas
pdfinfo output/pdf/kwt-engineering-atlas.pdf
pdffonts output/pdf/kwt-engineering-atlas.pdf
cd docs/diagrams
sha256sum -c SHA256SUMS
```

本次生成和结构检查使用Codex自带Python/ReportLab/pypdf/Pillow；渲染及PDF检查使用系统Poppler。对应生成脚本、依据快照和交付文件SHA记录在`manifest.json`。`source_documents`核对`sources/`中的生成时快照，不锁定工程的后续进度更新。图册打包文件不作为可运行RTL迁移包使用。
