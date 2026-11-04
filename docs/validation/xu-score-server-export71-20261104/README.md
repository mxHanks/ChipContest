# 实际71：条件reset诊断、第三轮清理和Q敏感性

131份原件共27,670,693字节；383840字节原始tar.xz SHA256 `feeb2584f1f3a9fff126cb38355f9b1a9f7f301c55135574c8bb32e6159a36b4`。原件路径、大小及SHA在[original-manifest.json](original-manifest.json)，完整原包无损保存。**均不能解释为完整150MHz或能量资格通过。**

- reset67只读PT诊断：保留全部5个reset sink×recovery/removal共10份报告。两个PMU recovery确实没有constrained path，记UNKNOWN；对应removal slack为+0.132751/+0.136416ns，其余3个recovery约30516.77ns、removal约+0.227102ns。一级D为原生propagated constant0，二级D动态，CK来自lfextclk；两项库`when=!D`/`sdf_cond=ENABLE_NOT_D===1'b1`的design arc未被user disable。未改lib/SDC、未添加case或豁免。实际lib_timing_arc属性名分三行折行，原parser未读到该属性表；from/to集合写成内部_sel handle，后续须补可读名字和库数值，不能据此推断根因已解决。
- cleanup73：只删除已在63实际报告中逐项锁定的53个组合单元；每单元全部输出、跨层leaf接收端、唯一owner和native非顺序属性再次检查。新网表SHA `fdf52301282ad5cd9854b1f28aa23073c4818ff1d72b6cb8f854ce44e8117ff3`，DC/PT实际完整执行；min-cap53→33，max-cap0，原5项removal仍存在。该网表是50→63→73分支，未包含reset61延迟修改，不能拼接两个分支的结果。
- Q sweep65：原61三case因self-script路径多一个`]`在读库前失败；65每份Tcl只删除该一个字节。baseline/SP0-TR0/SP1-TR0三fresh PT进程return0、唯一完成marker、22冻结输入before/after相同，保留原606查询、67pin×2和32 Q请求。原单宏baseline报告精确total=0.0006777278031222522W，两个假设Q状态相同为0.000634127005469054W。这验证绝对Q活动设置会影响功耗消费，不证明实际Q=0/1、条件弧已全部正确或全SoC能量合格。

工具手册正文未打包；实际installed help/man仅保留路径/字节/SHA，属性索引及所有实际诊断输出保留。reset61网表/SVF身份JSON与前包一致；没有修改原61失败状态。

```bash
python3 docs/validation/xu-score-server-export71-20261104/check-evidence.py
# 尚不存在的新目录，解出全部原件：
python3 docs/validation/xu-score-server-export71-20261104/check-evidence.py \
  --extract /absolute/path/new-actual71-directory
```

服务器实际命令均使用新目录，重现前须改独立输出名：

```bash
python3 "$HOME/Desktop/launch_reset_condition67.py"
python3 "$HOME/Desktop/launch_min_cell_cleanup73.py"
python3 "$HOME/Desktop/launch_xu_q_sweep65.py" start
```

此处PASS只表示全部原件一致；后续资格/评分不得把不同分支网表或假设Q状态混用。
