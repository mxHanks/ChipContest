# S3-Y32 内部就绪等待优化 goal

日期2026-11-09。用户要求继续上一轮优化，沿用goal执行。父基线`d6bea15b641cbe9b29c440f261636ab50a934ca2`，E203`5907a769c76e0e938a9deb7d85143d9a66cf4bc1`；新分支`codex/s3-y32-ready`。上一轮已封存材料不改写。

基线为8PE＋逐行stream NICE＋偏置连续读取，完整12层304,128输出PASS。每层payload429,697、真实clear198,403、gap102；full12 payload＋clear7,537,200。本轮先单层筛选，有含clear的真实收益才集成并跑full12。无收益仍保留独立负实验和明确结论。

## 待验证的问题

每层仍有4,752次ROW_STATUS总线查询；计算结果和元数据已在同域内部通道可用。检验能否在现有status线路提供明确live-cap协议，使新的可选NICE指令等待真实内部就绪，消除这些总线读。当前逐字写回应答后立即准备下一字，没有可删除的SEND/NEXT空泡；不引入响应到命令组合旁路、不改变单在途或fabric。

## 协议边界

- 新独立funct7=0x24；0x20/0x23原编码、错误及poll响应计数语义保留。
- 0x24沿用0x23的group[4:0]、count_minus1[9:5]及22bit limit[31:10]；仍仅同一行1..32组、32B对齐、完整Y地址范围校验。
- wrapper在claim低且DIRECT_ENABLE／direct_enabled时，以status[31]=1宣告live协议，低31位来自真实row状态；claim高时仍提供原锁存metadata。无新增CPU/总线端口。旧wrapper不能冒充支持新指令。
- 新READY_WAIT时claim低，接受时及每个等待edge检查cap；cap丢失返回1。valid0继续等待，即使active尚未置位，避免STARTROW延迟竞争；valid1才查active/group，错误仍7/6。预算只限定每组READY_WAIT驻留edge，最后允许edge就绪优先于timeout5，每组重装。
- 就绪后仍真实snapshot8lane，下一edge才能commit POP，然后8次32bit写各等响应；末组最后响应之后才completion。任意首次错误终止整个指令／任务；已POP／部分写不得retry。fence、memory clobber及软件返回检查保留。

## 工作和完成标准

1. 独立sandbox原型：NICE/wrapper＋新单元＋真实MAC wrapper；错误、预算边界、组间重装、启动、cap消失、背压、复位、最终响应和旧ABI回归。
2. 可选固件／新schedule及被动observer，证明99请求/响应/OITF、3168snapshot/POP、25344Y写、ROW_STATUS查询0；既有数值、工作量、清空、窗口和退休检查全部保留。
3. 同条件单层筛选；仅推进真实payload＋clear优于628,100的候选。通过后集成final source再full12，每层fresh process与真实物理clear。
4. 独立严格证据比较固定baseline完整170-source SHA；显式审查candidate源pair、macro/selector/schedule差异，两侧ELF与加载图像、向量、工具/时钟/复位/clear C和原raw marker。单层projection明确注明12→1原层0，全12最终必须12→12。
5. 审查、限定回归、本地父子提交、紧凑证据和便携复现/回退收据。开发仿真不冒充PPA或官方资格。

全程不综合、不推送、不改Y32数值与清空配方、不改E203 LSU/BIU/仲裁/在途配置与CPU控制；主工作区不动。面积/时序/能耗保持未验证。仍以11月13日交付、11月11日冻结为约束。

## 完成结果

- [x] 独立RTL／固件原型、418单元场景、真实MAC及旧ABI回归。
- [x] 明确启动排序问题，保留原FAIL；READY专用前fence修正，未放宽退休检查。
- [x] 单层正收益筛选与最终集成完整12层304,128输出通过。
- [x] 独立source／ELF-image／clear／条件／窗口严格比较、损坏证据负例及代码审查。
- [x] 本地提交、证据／回退材料；最终提交与封包校验状态由外层handoff收据锁定。

最终每层425,539＋198,403，full12 7,537,200→7,487,304，净减49,896拍／0.6619965%。上一轮原件不改写，未综合／未推送。见[完整报告](s3-y32-ready-results.md)与`build/ready-20261109/handoff/README.md`。
