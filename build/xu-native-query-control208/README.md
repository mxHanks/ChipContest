# xu208：兼容查询与归档的统一登记

只向原153控制器追加native_query207和two_candidate_finalpack209；不直接启动EDA，不发signal，不重启旧worker，不新建controller。
前者依赖191终态，后者依赖207终态，均native=true沿原本用户单槽。207内部三native PT顺序运行；任一case失败保留后仍查询其余case；成功也不解除资格。

208在198已独立审查的登记守卫基础上使用两个固定job、唯一out、exact frozen source-byte身份、scope163与182/198原件祖先。
实际198 receipt逐字节由已安全验包199固定；登记前后检查所有runtime/job/guard/controller/祖先原件，job在验证后修改不能重新绑定新hash。
同ID只能逐字节幂等；未注册而已有output时拒绝，不自动adopt/retry。旧177/186/192失败、198/171/191结果全保留。

build208.py生成确定性运输包，207 runtime逐文件由manifest207原SHA导入，保留nested路径但拒绝absolute/traversal。
安装器先核整包/完整成员及每文件SHA/所有目标已有字节/symlink，再写入不存在的文件；不覆盖已有源。
实际部署必须先通过review210/211及208独立审查，再上传运输包与对应安装器，安装后capture核对；只执行register208，绝不手动运行207。

```sh
python3 -B build/xu-native-query-control208/build208.py
python3 -B build/xu-native-query-control208/test208.py
```

服务器回执B/two-candidate-followup-registration-20261105-208.json；日常唯一入口仍~/Desktop/xu-campaign-batch154/campaign154.py status。
后继原包B/xu-server-two-candidate-final-20261105-209.tar.xz。此README存在不表示已在服务器执行。
