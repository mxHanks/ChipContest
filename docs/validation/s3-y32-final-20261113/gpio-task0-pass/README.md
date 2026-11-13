# 最终生产 GPIO 单任务通过（完整12仍在运行）

`gpio-task0-r2` 已通过：N2/PW1、DMA4、374实际宏，159个生产编译源和6个defines
与最终sealed PPA输入逐项一致，无测试loader。完整warmup和正式task0均完成真实
55040次16位清零、15040个GPIO输入→CPU/SystemBus写入、25344个Y32写及CPU读回。
独立四槽响应台账验证40384笔请求/响应、峰值在途3和末Y响应退休先于DONE。

正式task0：GPIO装载1315983拍，DMA工作100625拍，clear1027拍。
首GPIO输入到末Y响应1416697拍，含clear1417788拍；按假定150MHz换算分别
105.8801和105.7986 task/s。这只是单任务局部测量，不能当作最终完整12成绩，
也不能继续沿用开发三源loader版的1064.35数字。

原始日志、完整PASS收据、源manifest和单核affinity调整记录均固定在本目录。
模拟本身未改RTL或固件；新activity只读arm增加ready条件，避免背压时提前开窗，
仍待独立trace编译/实际采集。完整12及两个wait31由campaign-r3继续运行，完成后
再封新的CPU12 PPA输入。150MHz STA、面积、映射等价与功耗尚未通过。
