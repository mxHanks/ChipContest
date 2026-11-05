# xu196：独立审查192统一追加登记

结论：**192最终本地实现及实际四个冻结job审查通过，无剩余阻断发现**。原192的8项检查和独立12项检查全部通过。本审查未连接服务器、未登记远程job、未启动EDA。

绑定字节：

- register192.py：`095b1f6f268161662642a02d99655badef7cc8bade3aa27c07ef8d3f72108c78`
- runtime192.tar.gz：110827 bytes，`a08459ff2b43c94cb1dc8f06ede235b0e36e23ef304fe2d04e2da71503ce1ea2`
- install192.py：`56734c6f49db3204a789851dfaaf5f8ee0257850bcb4ab126168f9975c6ac991`
- frozen-jobs192.json：`f707de618b6158917411551e6b2f8bc691b11c7c9ef692cafb92124f7093f363`

检查确认固定顺序为186→190预检→190完整12项→191。186依赖177终态和166预检成功；190预检依赖186终态，190完整依赖自身预检成功；191等待177/186/190完整终态，因此上游失败也可进入最终诊断归档。四个job均native=true、direct前台、唯一output_root/process_contains，沿用冻结原153的单资源槽，不新增controller。

实际四份guard输入的SHA、所有tar成员集/类型/大小/SHA与本机冻结源完全核对；tar不包含库或RTL正文。隔离复制完整构建输入后重建runtime、installer、guard、manifest、transport，全部逐字节相同。原8项测试已验证installer首次部署、重复同字节、冲突目标在任何写入前拒绝、symlink拒绝和archive变化拒绝。安装与登记分开，installer不运行任务。

独立测试还执行了register192.main全数据流：使用逐字节原153 API与临时控制目录，当前测试进程的pid/uid/start_ticks/argv仅作为可控身份fixture；这验证比较逻辑，**不证明服务器153当前存活**。禁止subprocess.Popen和os.kill仍能成功完成登记；四份registration与输入字节完全一致，未创建候选output，receipt明确direct launch/signal/restart均为0。第二次登记保持原receipt字节不变。

反例包括：改动guard job字节、validate后job变化、重复输出根、依赖/native变动、冻结记录冲突、复用PID birth不符、controller字节变化、scope扩大、未登记但已存在的output/悬空symlink、不同旧registration；均拒绝。原记录和输出没有删除或覆盖。

审查期间提出的冻结缺口已在最终实现解决：job expected身份严格来自一次读取的guard，而不是之后重新观察到的字节；登记前、落盘后、全程after都核对；worker、register自身、guard、scope163、182回执、原177 registration及job元数据全进入前后SHA。重复路径要求同SHA、双方带长度时长度相同，合并保留更强长度信息；4个输出根额外检查相互唯一。纯register可在中途失败后留下已登记的原字节，保留供原总控观察，不回滚或启动第二套任务。

保留两份早期review draft日志：首轮测试fixture误用了共享dict对象且重复out负例未同步argv；第二轮仍匹配改名前的冲突错误文本。均为独立fixture修正，不是最终实现失败。最终日志为review196.log；本审查没有改动192实现。

复现（仓库根目录，Python3标准库，无远程访问）：

```sh
python3 -B build/xu-two-candidate-control192/test192.py
python3 -B build/xu-review192-196/review196.py
```

`review196.json`保存完整被审文件身份，`manifest196.json`绑定本审查文件。该结论为本地软件守卫验证，实际部署/登记和后续native实验结果需要各自服务器原件与独立验包，不赋予比赛资格。
