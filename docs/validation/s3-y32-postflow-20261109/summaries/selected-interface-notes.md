# 选中候选接口与兼容性

选中8PE、原256bit direct通道、原8lane snapshot，叠加bias group SRAM连续读取及新的stream指令。没有把batch16（0x22）负实验并入生产，0x23与它独立。

## 新NICE指令

custom3 opcode0x7b / funct3=7 / funct7=0x23。rs1为32B对齐Y32目的地，rs2 group[4:0]/count_minus1[9:5]/poll_limit[31:10]，每组实际已退休状态响应计数。count可1..32，必须完整落在同一行，目的地行内offset等于group×32，整个span在[a0020000,a0038c00)。新group/span组合错误为9，旧错误1..8保留。

只在DIRECT_ENABLE且direct mode已启用时接受0x23；不向旧read-pop路径静默回退。cap寄存器保持原值，旧DIRECT_CAP不单独识别新ISA，固件/子模块必须用父gitlink配套部署（版本锁定）。新的firmware宏XU_NICE_DRAINN依赖XU_NICE_DRAIN8与XU_NICE_DIRECT，poll_limit上限变为22bit。旧macro关闭时原binary逐字相同。

每组通过真实LSU读取ROW_STATUS，原子接收8lane，下一拍commit恰一次POP，再串行8次32bitY写，每个等待响应退休后才能发下一笔；group末响应之后才进入下一组，最后group末响应之后才completion。每组重新装载poll budget。firsterror立即中止整个instruction/task，已POP或部分写不能retry。仍保fence/memoryclobber/非零立即return；不将nice_err当陷阱。

CPU每行count32一次，99request/99completion/OITF，3168snap/POP，25344Y写。旧0x20 drain8编码、group/poll字段、范围检查与错误码1..8不变。共享总线32bit、LSU/BIU/仲裁/在途配置、CPU透传、directwrapper都没有变化。

## 偏置模块

groupFill仅从交替issue/capture改为groupStream：24次连续16bit读，第25个streamedge完成尾返回才置slotValid。host读写/byte masks/RMW/响应保持/physicalclear不改。invalidate/epoch变化撤销当拍新issue与在途return且不发布残缺slot，已接受demand重试。groupTake仅针对完整当前epoch槽。保持同一1024×16 1RW SRAM、2个8bias槽，新增流水控制原始寄存约6bit；没有映射面积/能耗结论。
