# E203 集成入口（BLOCKED）

等待组委会 E203 平台工程、SDK、共享SRAM地址图与 System Bus/NICE 接入协议。用户提供后置于不随归档发布的 `soc/platform/`，记录版本与SHA。

检查总线数据宽度、握手/错误/中断、访问顺序、RISC-V ISA/ABI、启动/链接脚本和装载仿真接口，再确定MMIO映射与驱动。现有C fixture是host fake-MMIO，不能当E203驱动。当前不虚构地址、NICE指令编码或SoC测试通过。
