# 独立只读审查 receipt

审查对象：主树最终 8 PE + direct stream + bias pipeline，和独立
`postflow_compare.py` 的 source/artifact pins、profile 归一化与 clear C 比较。
未修改生产代码、比较器或测量输入，未运行额外 EDA。未发现可确认的生产缺陷。

- NICE `0x23`：33位目的范围加法、组数/行偏移检查、每组轮询预算重新载入、
  首次错误停止、每组第八次写响应后再推进、末组最后响应后才完成；旧 `0x20`
  路径和返回码1..8保留，新描述符错误使用9。
- Bias SRAM：连续issue与单拍rvalid一一对应；epoch失效取消未返回项，
  接受的需求重试；word23返回后才发布完整组，host mask与768word物理clear保留。
- Observer：真实LSU端点、单在途、逐lane数值、bundle/POP所有权、OITF/rd、
  held command/completion、每组与整指令watchdog、最终响应和完整请求时间窗均保留。
- 比较器：完整外部source pins及固定改动白名单；direct→batch/stream、8→16
  单向profile；只移除精确声明的新macro/selector；新固件需精确accel.c源差异；
  ELF加载段与ITCM图像逐字节核验；generated clear C仅归一化唯一精确include路径，
  其余字节必须一致。相同transport的固件加载图像必须不变。
- Goal范围：两项原型及独立/组合筛选有实测；双缓冲、两行布局、DMA与41位累加
  有明确证据与暂缓边界，分析未冒充RTL或PPA收益。最终完整12层/提交/封包由root验收。

这是代码和证据边界审查记录，不代替正式 VCS、综合、STA 或官方验收。
