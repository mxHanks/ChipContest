
#!/usr/bin/env bash
set -euo pipefail

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 从 tools/scripts 向上返回两层，定位 ChipContest
WORKSPACE="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 工程与工艺库路径
PROJECT="$WORKSPACE"
LIB="$WORKSPACE/assets/libs/nangate45/NangateOpenCellLibrary_typical.lib"

# 默认综合 LinearComputeCore，也可以通过参数选择其他顶层
TOP="${1:-LinearComputeCore}"

RTL_DIR="$PROJECT/generated/$TOP"
REPORT_DIR="$PROJECT/reports"

# 检查文件
if [[ ! -f "$LIB" ]]; then
    echo "找不到 Nangate45 Liberty 文件：$LIB"
    exit 1
fi

if [[ ! -d "$RTL_DIR" ]]; then
    echo "找不到 RTL 目录：$RTL_DIR"
    echo "请先使用 GenerateRTL 生成 SystemVerilog"
    exit 1
fi

mkdir -p "$REPORT_DIR"

cd "$PROJECT"

echo "=================================="
echo " Top:     $TOP"
echo " Library: $LIB"
echo "=================================="

yosys -l "$REPORT_DIR/${TOP}_nangate45.log" -p "
    read_verilog -sv generated/${TOP}/*.sv
    hierarchy -check -top ${TOP}

    synth -top ${TOP} -noabc -flatten

    dfflibmap -liberty ${LIB}
    abc -liberty ${LIB}

    clean
    stat -liberty ${LIB}
"

echo
echo "面积综合完成！"
echo "报告：$REPORT_DIR/${TOP}_nangate45.log"

