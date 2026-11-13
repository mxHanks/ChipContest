# 最终 DMA4/storage21 模块回归

状态PASS。完整12任务304128个Y32逐位一致；每任务真实55040次16bit物理零写（W16384+bias768+X16384+result21504），实际实例310颗（shared256+internal54，不含CPU64）。完整12模块clear+DMA周期1219801，不包括生产加载或CPU，不作为完整任务吞吐。

另通过单行、读写错误、响应背压、末Y响应保持97拍、三种共同复位以及新参数完整任务76032个Y32、七地址定向错误后新任务177408个Y32恢复。独立C++台账检查4槽在途数，正常峰值3；整行宏Q与slot/row持续保持到第7列Y响应退休，新增只读断言实际开启。

`source/`保存真实仿真源快照。DMA在这个snapshot之后增加三define联合guard与5470完整fallback；`final-projection-binding.json`证明最终生产三define选中的全部token与该测试相同，另外七种组合的回退由`final-source-manifest.json`证明。生产CPU/GPIO流程独立使用最终wrapper实际字节，不能用本单元代替。

原始收据包含输入/输出身份、命令、工具返回码和耗时。compiled model/大型postreset数组保留于收据记载的本地build目录，省略项写明，不打包私有库、工具或张量。附加显式多在途错误计数位于`multi-error/`（如果已导出）。源/manifest重现方法见`experiments/s3-y32-final/rtl/README.md`。
