# 独立复核：acc41 saved comparator 与 pair NICE

审阅范围为 `verification/compare_acc41.py`、DMA 原型 `xu_nice_drain8.v`、`tb_nice_pair_errors.sv`、`rowpair_direct_bridge.v`、`tb_rowpair_nice_real.sv`；本审不修改候选源代码。审阅开始时 pair 单元测试608 cases已通过，real composition仍在另一agent运行，不能据此宣称真实SoC验收。

## 41位比较器

初稿已 pin baseline result、171项source map、唯一 MacPE SHA pair、inherited loader；保留清零recipe原样重建、原始log数值marker、全输出/事务/固件PT_LOAD验证，ELF只规范化一个非加载FILE symbol的六字符GCC随机后缀；未发现将有意义固件字节或测试条件抹除的比较放松。

发现初稿仅汇总后要求所有timing/work totals相等：两个层相反的变化可抵消，`response_end_cycle` 和绝对窗口也不在汇总值内。已向root要求每层 `V.totals([b])==V.totals([a])`，并对 `window`、完整clear marker字典要求相等；root已确认采纳，最终结果须以加严版重新比较为准。本文件不替代最终receipt。

## 两行 NICE 地址与ABI

`0x25` 使用独立描述符：起始group[4:0]、count-1[9:5]、second[10]、非零ready-limit[31:11]。原指令格式没有复用为不同含义。

- rs1必须32字节对齐，处于Y区域，行内offset等于group×32。
- group+count≤32，两个row的相同group按row0/row1交替串行输出；只有两row均写完末lane响应后才递增group。
- request_end为33位的rs1+count×32+second×1024，检查不超过Y_END；无32位地址回绕。
- 独立精确整数枚举210944组边界组合：row=-2..100，全部32个group、32种count、两种second标志，RTL接收谓词与行/组oracle完全相同。见 `dma-range-enumeration.json`。这属于表达式复核，不冒称RTL测试。
- bit30前置要求pair模式存在；bit11在live READY和captured DIRECT两个位置校验row identity；异常分别在snapshot/POP前终止。先snapshot，下一edge commit，之后8个32位串行LSU写，最后响应后才继续；错误completion保持稳定。

发现初稿在bit30=1的pair producer上仍接受旧0x20/0x23/0x24，旧0x24可能消费row0后在row1同group报错，发生了部分副作用。已向DMA agent说明，并要求其明确双向兼容语义；该agent决定对pair专用producer前置拒绝旧opcode，并新增无副作用测试。正式旧wrapper不发布bit30，所以保持旧ABI行为且拒绝新opcode。最终审核应确认这项修正及测试完成。

## fixture与限制

unit已有64种count/tail组合（含row97/98边界）、全部512个写错误位置、live/captured row identity错误、commit错误、cap丢失、两row的6阶段reset，以及snapshot/commit/command/response/completion停顿检查。单元payload为受控接口fixture，不等于真实MAC数值验证。

real bridge通过public head/result接口连接真实两行compute，8周期RNE，metadata保存bit11/bit30，commit再次验证active/head/group/row，next-edge POP。没有MMIO/CPU route/host capability配置或软件生命周期，所以仅可将它视为组合原型。real fixture以独立幅值RNE oracle校验快照和每笔写，检查25344写/响应和3168 snapshots/POPs及行98单尾；不能将其固定周期共享总线fixture外推为E203 SoC加速。

未发现剩余确认的地址/row-bit算术缺陷；旧ABI修正与real组合测试完成状态由DMA agent/root最终receipt记录。
