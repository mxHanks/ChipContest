# xu198补充独立审查

审查绑定`afa493a`的统一登记/安装包与`0ef03c6`的S2c归档FM输入修正。结论：**通过，无剩余阻断发现**。原8项测试及独立15项测试均通过；没有远程操作，没有改动198或190实现。

最终绑定：

- runtime198.tar.gz：158795 bytes，`745bb90101f26e968d75f4f1a77bba8cb0e789750d0856df8fe90a4458c01407`
- register198.py：`89822c5d8b8b0bc255fc660f46c40d427ea55a5370384f642f872aaa70d3ec0c`
- install198.py：`915cec3e21bea761789518d6548b377659922645da9e93b971889cfe0bcee81b`
- frozen-jobs198.json：`61627fef35b2c1d324515ba8e8e4673443185ccc6b5ee3873e7a1922b2bd960e`

register198与已审register192逐字节对比，仅全局192→198命名替换。固定4项、顺序与依赖、唯一out、同153单槽、guard身份、登记前后SHA、scope163/182祖先、幂等和fresh output拒绝规则全部保留；没有第二controller、signal、restart或直接启动EDA。独立main数据流仍禁止Popen/kill，使用临时PID身份fixture，并不证明服务器此刻真实存活。

build198新增的实际映射仅为：本机`xu-s2c-common-power190`源码包→远程`xu-s2c-common-power198`。186与191原job字节完全相同，190两个job的新SHA分别为edcaf69f…和9b158428…。190运行时8个文件加manifest共9个都进入新namespace，包括`frozen-fm190.json`；总tar24个payload、另1个顶层manifest。每个成员类型、路径、大小、SHA与本机冻结源核对通过。隔离复制构建输入后重建tar、installer、guard、manifest、transport，全部逐字节一致。

附加覆盖安装兼容性：在独立临时Desktop先写入**原192 tar所有payload**及旧失败receipt，再执行真实install198。旧192所有文件/receipt原字节全部保持；186/191相同字节可复用；新的190只写入remote198 namespace。198默认单独安装、幂等安装、symlink/冲突目标/整包变化拒绝由原8项测试重新验证。没有用覆盖旧192 runtime的方法回避严格输入守卫。

FM snapshot349702 bytes与actual09原`candidate-formality-campaign-20261103-01/state.json`逐字节相同，SHA为`dadd3bb693a3ae17bf92682d9586fa1ba07e6ead468465e07b67fa91eabea5dd`，同时核对原09 manifest的长度/SHA。新job不将可变全局aggregate state路径列为冻结输入；新snapshot路径位于remote198，原路径保留为历史来源。原57的367项prepared输入中没有任何state.json，因此不会经这367项重新引入同一可变aggregate。修正保留完整原09 JSON，而非裁剪或重新签造单个候选状态；190仍独立重哈希同S2c native log、SVF、mapped/source等证据。更深的190功能审查由其独立review194负责。

所有状态继续NOT_QUALIFIED。换用归档原状态不代表新的FM执行或解除原S2c mapped VCS fatal、未知Q、完整150MHz与功耗资格问题。旧192实际严格输入拒绝及原日志由既有归档保存，本补充没有改写它们。

保留review198-attempt01.log：首次安装保留性测试错误复用了注册fixture的198合成job文件，真实installer正确拒绝冲突；改为独立全新安装fixture后15项通过，没有改实现。原196审查文件与manifest保持原样，本补充由自身manifest单独绑定。

复现（仓库根目录、Python3标准库，无服务器/凭据）：

```sh
python3 -B build/xu-two-candidate-control198/test198.py
python3 -B build/xu-review192-196/review198/review198.py
```
