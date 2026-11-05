# xu原子批量注册152

`enroll152.py`将完整、冻结、已审阅的任务批次注册到现有总控；不启动EDA、不重新init，
也不重试或覆盖任何候选输出。日常入口由`campaign154.py`统一调用它。
先检查整批依赖无缺项/无环、输出/结果/进程身份唯一、原注册不变和全部冻结输入的实际字节；
随后在register.lock下通过隐藏非JSON临时文件+fsync+原子rename逐项发布。
运行中的controller只能看见完整JSON，不会读到半写注册。

已有ID只接受逐字节相同任务，允许同一批安全续登记。完整注册前的每项输入核验全部通过后才发布第一项。
批次中途若外部I/O故障，已发布项保持原样，后继只能等待缺失依赖；原件保留，重试同批不会替换它们。
SHA显式绑定调用的已审阅controller及现有state.worker，支持冻结150或迁移后的153。

```sh
python3 -B enroll152.py --controller /absolute/control153/xu_experiments.py \
  --expected-controller-sha ACTUAL_REVIEWED_SHA --out /existing/controller-output \
  --jobs-root /frozen/jobs-only-directory --receipt /fresh/enrollment.json
```

该目录只能包含job JSON，不能混入plan JSON。6项本地检查覆盖整批/同字节重试、缺失依赖、环、
共享进程身份、不同JSON字节拒绝，以及持续读取时只能观察到完整2MB注册。
没有将机制检查当作EDA或比赛资格。
