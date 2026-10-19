#!/usr/bin/env python3
"""Editable SVG/draw.io and a vector PDF from one diagram specification.

Requires reportlab (available in the bundled Codex Python runtime).
The diagrams describe engineering plans, not completed SoC/PPA validation.
"""
from pathlib import Path
from xml.sax.saxutils import escape
import json
import math
import xml.etree.ElementTree as ET
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/diagrams'
PDF = ROOT / 'output/pdf/kwt-engineering-atlas.pdf'
W, H = 1920, 1080
INK = '#142B43'
MUTED = '#526579'
LINE = '#C8D4DE'
BLUE, BLUE_L = '#2463A6', '#EDF4FC'
TEAL, TEAL_L = '#117E75', '#ECF7F4'
PURPLE, PURPLE_L = '#7451A8', '#F4F0FA'
AMBER, AMBER_L = '#A96A12', '#FFF5E4'
RED, RED_L = '#B34545', '#FDF0EF'
GREEN, GREEN_L = '#277B53', '#EDF8F0'
BG = '#F7F9FC'

FONT_CJK = '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'
FONT_LAT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
pdfmetrics.registerFont(TTFont('CJK', FONT_CJK))
pdfmetrics.registerFont(TTFont('Latin', FONT_LAT))
pdfmetrics.registerFont(TTFont('LatinBold', FONT_BOLD))


def runs(s, bold=False):
    out = []
    for c in s:
        f = 'CJK' if ord(c) >= 0x2E80 else ('LatinBold' if bold else 'Latin')
        if out and out[-1][0] == f:
            out[-1] = (f, out[-1][1] + c)
        else:
            out.append((f, c))
    return out


def tw(s, size, bold=False):
    return sum(pdfmetrics.stringWidth(t, f, size) for f, t in runs(s, bold))


class Page:
    def __init__(self, name, title, subtitle, num):
        self.name, self.title, self.num = name, title, num
        self.e = []
        self.rect(0, 0, W, H, '#FFFFFF', None, 0)
        self.rect(56, 47, 8, 62, BLUE, None, 0)
        self.text(88, 68, 'KWT-1  /  RISC-V E203  /  ENGINEERING ATLAS', 17, BLUE, True)
        self.text(88, 111, title, 37, INK, True)
        self.text(88, 146, subtitle, 19, MUTED)
        self.text(1856, 79, f'0{num} / 05', 21, MUTED, True, 'right')
        self.line([(56, 1027), (1864, 1027)], LINE, 1)
        self.text(56, 1057, '2026-10-15  |  migration-v0.2 基线  |  规划与实现状态分开标注', 16, MUTED)
        self.text(1864, 1057, f'KWT ENGINEERING  /  {num:02d}', 16, MUTED, False, 'right')

    def rect(self, x, y, w, h, fill='#FFFFFF', stroke=LINE, radius=12, sw=1.5, dashed=False):
        self.e.append(dict(type='rect', x=x, y=y, w=w, h=h, fill=fill, stroke=stroke,
                           radius=radius, sw=sw, dashed=dashed))

    def text(self, x, y, text, size=22, color=INK, bold=False, align='left', maxw=None):
        if maxw is not None and tw(text, size, bold) > maxw:
            raise ValueError(f'{self.name}: text exceeds width {maxw}: {text}')
        self.e.append(dict(type='text', x=x, y=y, text=text, size=size, color=color,
                           bold=bold, align=align))

    def line(self, points, color=MUTED, sw=2, arrow=False, dashed=False):
        self.e.append(dict(type='line', points=points, color=color, sw=sw,
                           arrow=arrow, dashed=dashed))

    def box(self, x, y, w, h, title, lines=(), color=BLUE, fill=BLUE_L,
            tag=None, size=24, dashed=False):
        self.rect(x, y, w, h, fill, color, 12, 1.7, dashed)
        self.rect(x+1, y+14, 5, h-28, color, None, 2)
        self.text(x+20, y+35, title, size, INK, True, maxw=w-38)
        for i, t in enumerate(lines):
            self.text(x+20, y+67+i*29, t, 20, MUTED, maxw=w-38)
        if tag:
            self.text(x+20, y+h-17, tag, 16, color, True, maxw=w-38)

    def label(self, x, y, text, color=MUTED, size=17):
        width = tw(text, size)+16
        self.rect(x-8, y-size, width, size+8, '#FFFFFF', None, 3)
        self.text(x, y, text, size, color)

    def band(self, y, title, detail, color=BLUE, fill=BLUE_L):
        self.rect(56, y, 1808, 64, fill, None, 10)
        self.text(78, y+40, title, 22, color, True)
        self.text(78+tw(title,22,True)+30, y+40, detail, 20, INK)


def engineering():
    p = Page('00-project-engineering-flow', '项目工程总流程：从需求到可复现作品',
             '主流程图  |  三人并行开发 → 汇合验证 → 指定工艺分析 → 公平优化 → 最终冻结', 1)
    p.rect(56,178,1808,93,INK,None,12)
    p.text(80,215,'需求确认与基线登记',26,'#FFFFFF',True)
    p.text(80,248,'99×64 × 64×256 + bias；12 层独立任务；官方来源 / 版本 / 接口契约 / 数值候选',22,'#D9E6F3')
    p.text(1838,215,'当前已验：8 路核心 + 静音回放',20,'#D9E6F3',False,'right')
    xs=[56,692,1328]
    for x in xs:
        p.line([(x+268,272),(x+268,307)],MUTED,2.3,True)
    p.box(56,316,536,141,'C · 模型、数值与真实数据',
          ['固定模型 / Speech Commands V2 划分','训练标定、验证评估；发布向量与 Golden'],TEAL,TEAL_L,
          '交付：数值契约、12 层误差、数据哈希',23)
    p.box(692,316,536,141,'B · 线性计算核心与指定 SRAM',
          ['微架构、MAC、流水与地址调度','指定宏端口 / 延迟适配；RTL 单元验证'],PURPLE,PURPLE_L,
          '交付：RTL、宏模型、握手与时序契约',23)
    p.box(1328,316,536,141,'A · E203 平台与系统接口',
          ['官方 SDK / 地址图 / System Bus 或 NICE','C 驱动、数据搬运、启动与写回确认'],BLUE,BLUE_L,
          '交付：平台、适配层、驱动与任务入口',23)
    for x in xs:
        p.line([(x+268,459),(x+268,490)],MUTED,2.2)
        p.rect(x+265,487,6,6,MUTED,None,3)
    p.line([(324,490),(1596,490)],MUTED,2.2)
    p.line([(324,490),(324,523)],MUTED,2.4,True)
    p.label(750,483,'交接带版本；接收方复现',MUTED,18)
    p.box(56,532,536,143,'01 · 功能与数值闭环',
          ['整数模型 ↔ RTL：全结果逐位一致','真实 12 层精度；边界 / 复位 / 连续任务'],TEAL,'#FFFFFF',
          '数值变更重新评估；Golden 只进检查器',23)
    p.box(692,532,536,143,'02 · E203 完整任务闭环',
          ['装载 X/W/b → 硬件计算 → 全部 Y 写回','换参 / 回压 / 异常；采集周期与活动波形'],BLUE,'#FFFFFF',
          '系统 DONE = 最后写事务已确认',23)
    p.box(1328,532,536,143,'03 · 指定工艺与 PPA 分析',
          ['同版 RTL / 宏 / 标准单元库 + SDC','综合与前后核对 → STA → 功耗与面积'],AMBER,AMBER_L,
          '输出：网表、时序、面积、活动覆盖报告',23)
    p.line([(594,604),(683,604)],BLUE,3,True)
    p.line([(1230,604),(1319,604)],BLUE,3,True)
    p.line([(1596,677),(1596,712),(324,712),(324,744)],AMBER,2.5,True)
    p.label(695,706,'功能 / 精度 / SoC / 工艺证据汇总',AMBER,19)
    p.box(56,753,536,140,'04 · 资格门：全部条件合格',
          ['逐位一致、NRMSE ≤ 3%、完整 SoC','150 MHz；核心 + 接口 + 内部 SRAM'],AMBER,AMBER_L,
          '增量面积 ≤ 2.25 mm²；建议预留裕量',23)
    p.box(692,753,536,140,'05 · 瓶颈分析与同条件对照',
          ['拆分装载 / 计算 / 等待 / 写回开销','比较流水、并行度、复用与缓冲代价'],PURPLE,PURPLE_L,
          '改动 → 实现与重验；只选择通过的配置',23)
    p.box(1328,753,536,140,'06 · 冻结、独立复现与答辩',
          ['D16 择优；D17 冻结 RTL / 数值 / 配置','独立复现、贡献说明、实验表与演示'],GREEN,GREEN_L,
          '交付：工程 + 模型 + 驱动 + 完整证据',23)
    p.line([(594,821),(683,821)],INK,3,True)
    p.line([(1230,821),(1319,821)],INK,3,True)
    p.line([(960,895),(960,934),(32,934),(32,605),(47,605)],RED,2.2,True,True)
    p.label(151,928,'不合格 / 优化改动 → 责任模块修复 → 功能、SoC、工艺重新验证',RED,19)
    p.rect(56,959,1808,53,BG,None,10)
    p.text(78,992,'测量从装载到最终写回；功耗覆盖 CPU / 互连 / 加速器 / SRAM。缺材料标 BLOCKED，继续无依赖工作。',21,INK)
    return p


def workflow():
    p = Page('01-engineering-workflow', '三人并行工程流程与交接门槛',
             '20 天内部排期：2026-10-15 至 11-03  |  从可运行首版走向正式 SoC、精度与工艺验收', 2)
    p.rect(56,174,1085,62,GREEN_L,None)
    p.text(76,212,'已完成基线',21,GREEN,True)
    p.text(224,212,'8 路核心 · 位精确模型 · 12 层静音回放 · 57 项自检',21,INK)
    p.rect(1161,174,703,62,AMBER_L,None)
    p.text(1181,212,'当前缺口',21,AMBER,True)
    p.text(1318,212,'真实数据精度 / 官方 E203 / 指定库与 SRAM',20,INK)

    xs = [300,612,924,1236,1548]
    stages=[('D1–3','接管与契约'),('D4–7','首个完整闭环'),('D8–12','合格基线'),('D13–16','同条件对照'),('D17–20','冻结与交付')]
    for x,(d,t) in zip(xs,stages):
        p.rect(x,260,276,63,INK,None,8)
        p.text(x+18,287,d.replace('–','-'),18,'#D5E5F5',True)
        p.text(x+18,312,t,22,'#FFFFFF',True)

    rows=[
      ('A','系统集成',BLUE,BLUE_L,350,[
       ('跑通官方平台',['E203 / SDK / 地址图','确定总线或 NICE 接入'],'交付：接口契约 v1'),
       ('首层 SoC 运行',['C 驱动与多拍打包','启动 → 计算 → 全部写回'],'交付：单任务日志'),
       ('12 层系统闭环',['换参、复位与异常恢复','固定完整计时窗口'],'交付：SoC 验收证据'),
       ('系统效率评估',['采集周期和活动信息','比较搬运、等待与写回'],'交付：端到端性能'),
       ('提交与现场演示',['冻结集成版本','复现、演示与问题缓冲'],'交付：可运行系统')]),
      ('B','硬件与工艺',PURPLE,PURPLE_L,530,[
       ('接管核心与宏',['复现现有 8 路 RTL','落实库、SRAM 和许可'],'交付：存储/时序契约'),
       ('指定 SRAM 接入',['宏端口与读延迟对齐','首轮综合和相关回归'],'交付：时序/面积初报'),
       ('补齐工艺资格',['150 MHz / 面积门槛','综合前后功能核对'],'交付：合格网表与 SDC'),
       ('比较架构候选',['V0 / V1 / V2 / V3','复用、重叠、PPA 取舍'],'交付：实测最优配置'),
       ('硬件证据归档',['网表、宏、SDC 一致','时序/面积/功耗可追溯'],'交付：硬件与 PPA 包')]),
      ('C','数值与验证',TEAL,TEAL_L,710,[
       ('真实数据入口',['登记数据划分与来源','核对 12 层正确输入位置'],'交付：数值与数据契约'),
       ('验证精度与尺度',['训练标定 / 验证评估','发布向量、尺度与 Golden'],'交付：真实精度报告'),
       ('全结果一致性',['逐位比较 + 逐层 NRMSE','独立性能任务误差检查'],'交付：功能/数值证据'),
       ('公平实验与回归',['相同数据、格式和口径','绑定版本与输入哈希'],'交付：对照结果表'),
       ('独立复现与打包',['非原作者照文档运行','命令、日志、版本与校验'],'交付：可复现工程')])]
    for code,title,col,fill,y,cards in rows:
        p.rect(56,y-13,1808,163,fill,None,12)
        p.text(80,y+40,code,42,col,True)
        p.text(80,y+79,title,25,INK,True)
        p.text(80,y+114,'主责到最终交付',17,MUTED)
        for i,(x,card) in enumerate(zip(xs,cards)):
            p.box(x,y,276,137,card[0],card[1],col,'#FFFFFF',card[2],22)
            if i<4:
                p.line([(x+280,y+65),(xs[i+1]-8,y+65)],col,2.2,True)
    gates=[('G0 契约一致','数值 / 握手 / 打包'),('G1 首层闭环','真实数据 + 全部写回'),('G2 资格齐备','未过：修复优先'),('G3 配置择优','D16 未验：不提交'),('G4 交付冻结','D17 后只修缺陷')]
    for x,(a,b) in zip(xs,gates):
        p.rect(x,889,276,64,BG,LINE,8)
        p.text(x+14,915,a,19,INK,True)
        p.text(x+14,940,b,17,MUTED)
    p.text(56,983,'C → A/B：真实向量与数值契约',20,TEAL,True)
    p.text(650,983,'B → A/C：接口、RTL 与宏模型',20,PURPLE,True)
    p.text(1244,983,'A → B/C：写回结果、周期与活动',20,BLUE,True)
    p.text(56,1011,'交接带版本、命令、输入哈希和日志，接收方复现才算完成；D3 缺材料则调整排期，D12 未合格则停止新增优化。',17,MUTED)
    return p


def system():
    p=Page('02-system-datapath','系统数据通路：主机、E203 与加速器边界',
           '实线：真实载荷 / 结果  ·  虚线：控制与状态  ·  金色框：正式待验收  ·  紫色虚框：优化候选',3)
    p.rect(56,180,390,720,TEAL_L,None,16)
    p.rect(470,180,550,720,BLUE_L,None,16)
    p.rect(1044,180,820,720,PURPLE_L,None,16)
    for x,t,c in [(80,'主机离线区 · C',TEAL),(494,'官方 E203 平台 · A',BLUE),(1068,'独立计算加速器 · B',PURPLE)]:
        p.text(x,216,t,24,c,True)
    p.box(80,250,342,115,'固定来源与真实语音',['官方 checkpoint / 固定划分','关闭训练增强；不调整测试集'],TEAL,'#FFFFFF',size=22)
    p.line([(251,368),(251,397)],TEAL,2.5,True)
    p.box(80,405,342,156,'逐层提取与格式转换',['Attention + 残差 + LN1 后','分别提取 X_l、W_l、b_l','12 层是 12 个独立任务'],TEAL,'#FFFFFF',size=22)
    p.line([(422,480),(493,480)],TEAL,3,True)
    p.label(430,466,'X/W/b',TEAL,16)
    p.box(80,637,342,150,'软件参考与核对',['位精确整数 Golden','FP32 参考 / 解码误差','参考 Y 只供检查器使用'],TEAL,'#FFFFFF',size=22)
    p.line([(125,562),(125,629)],TEAL,2,True)
    p.text(80,849,'主机预处理不计作硬件计算。',19,TEAL)
    p.text(80,878,'每层输入独立，不串接 FFN 输出。',18,TEAL)

    p.box(494,250,502,113,'E203 · C 驱动与任务调度',['配置层号、地址与任务状态','选择官方已支持的一种接入方式'],AMBER,'#FFFFFF',size=23)
    p.box(494,405,502,156,'512 KiB 共享 SRAM',['当前任务的 X / W / bias 区','完整 Y 写回区 + 软件保留区','容量、对齐和地址图必须审计'],AMBER,'#FFFFFF',size=23)
    p.box(494,637,502,150,'平台适配与数据搬运',['System Bus 或 NICE：待冻结','X/W 16 位 · bias 40 位 · Y 48 位','总线多拍打包；不假定已有 DMA'],AMBER,'#FFFFFF',size=22)
    p.line([(494,305),(460,305),(460,614),(548,614),(548,635)],BLUE,2,True,True)
    p.label(495,605,'控制/启动',BLUE,16)
    p.line([(650,562),(650,628)],BLUE,3,True)
    p.label(662,601,'装载',BLUE,17)
    p.line([(910,636),(910,569)],BLUE,3,True)
    p.label(923,602,'Y 写回',BLUE,17)

    p.box(1068,250,345,134,'装载与内部存储',['X / W / bias 分区','当前：同步推断数组','正式：指定 16 位 SRAM 宏'],AMBER,'#FFFFFF',size=22)
    p.box(1485,250,355,134,'计算核心',['已完：单行 × 8 列','候选：双行 × 8 列','64 项乘加 + bias；acc 48 位'],PURPLE,'#FFFFFF',size=22,dashed=True)
    p.line([(1415,317),(1476,317)],PURPLE,3,True)
    p.box(1485,465,355,145,'结果流 / 重排与双缓冲',['基线：顺序输出、支持回压','候选：快照 + 行重排缓冲','维持 out_index = 0..25343'],PURPLE,'#FFFFFF',size=21,dashed=True)
    p.line([(1662,386),(1662,456)],PURPLE,3,True)
    p.label(1682,428,'Y：48 位',PURPLE,17)
    p.box(1068,637,772,150,'写回完成与流控',['结果交给平台适配，等待全部写事务确认；缓冲满则回压','核心 done 与系统 DONE 分开；复位使在途数据失效','下一任务重新完整装载 X/W/b，避免跨层残留'],AMBER,'#FFFFFF',size=24)
    p.line([(1662,611),(1662,629)],PURPLE,3,True)
    p.line([(1068,747),(1005,747)],BLUE,3,True)
    p.line([(960,788),(960,812),(1225,812),(1225,788)],BLUE,2,True,True)
    p.label(1009,834,'全部写事务确认 ACK',BLUE,17)
    p.line([(996,678),(1032,678),(1032,318),(1059,318)],BLUE,3,True)
    p.label(1017,426,'装载',BLUE,16)
    p.line([(1145,637),(1145,584),(1010,584),(1010,236),(875,236),(875,249)],BLUE,2,True,True)
    p.label(1128,585,'系统 DONE：最后写回确认后',BLUE,17)
    p.line([(995,480),(1014,480),(1014,861),(438,861),(438,730),(423,730)],TEAL,2,True)
    p.label(600,861,'读回 Y → 比较器（Golden 不进入硬件计算通路）',TEAL,18)
    p.text(56,921,'Y[99,256] = X[99,64] × W[64,256] + b[256]    |    每任务 25,344 个输出    |    无 DDR',19,INK)
    p.band(930,'完整测量窗口','清任务缓存 → 开始装载 X/W/b → E203 调度 / 总线 / 计算 → 最后 Y 写回确认',BLUE,BLUE_L)
    return p


def micro():
    p=Page('03-candidate-microarchitecture','候选数据通路：双行权重复用与有序写回',
           'PROPOSED · 尚未实现  |  当前已验证基线为单行 × 8 列  |  保持 fixed16_acc48_v1 的数学语义',4)
    p.rect(56,178,1808,67,PURPLE_L,None)
    p.text(78,219,'设计问题',22,PURPLE,True)
    p.text(210,219,'一次读取 8 个权重，供两行共 16 个 MAC 使用；减少内部 W 读取，并隐藏部分写回等待。',22,INK)

    p.box(66,280,300,120,'W：8 个列 bank',['每 bank：2048 × 16 位','每拍 8 字，向两行广播'],PURPLE,'#FFFFFF',size=23)
    p.box(66,454,300,112,'X：偶数行 bank',['每拍 1 个有符号 16 位字','输入 X[r,k] 广播到 8 路'],BLUE,BLUE_L,size=22)
    p.box(66,636,300,112,'X：奇数行 bank',['每拍 1 个有符号 16 位字','输入 X[r+1,k] 广播到 8 路'],BLUE,BLUE_L,size=22)

    p.rect(440,280,690,498,BG,LINE,16)
    p.text(462,319,'两行并行阵列 · 16 × signed MAC',25,INK,True)
    p.text(462,352,'bias 40 位符号扩展；64 项精确累加到 48 位',20,MUTED)
    p.rect(468,435,634,127,BLUE_L,None,10)
    p.rect(468,617,634,127,BLUE_L,None,10)
    for yy,row in [(435,'行 r'),(617,'行 r+1')]:
        p.text(486,yy+30,row,21,BLUE,True)
        for i in range(8):
            x=487+i*75
            p.rect(x,yy+45,62,62,'#FFFFFF',BLUE,7)
            p.text(x+31,yy+71,'MAC',16,BLUE,True,'center')
            p.text(x+31,yy+94,str(i),16,MUTED,False,'center')
    p.line([(367,339),(405,339),(405,414),(780,414),(780,434)],PURPLE,3,True)
    p.line([(405,414),(420,414),(420,594),(780,594),(780,616)],PURPLE,3,True)
    p.label(574,407,'同一组 W[k,c:c+7]',PURPLE,18)
    p.label(574,588,'同一组 W 广播复用',PURPLE,18)
    p.line([(368,514),(459,514)],BLUE,3,True)
    p.line([(368,696),(459,696)],BLUE,3,True)
    p.line([(1104,514),(1151,514),(1151,552),(1185,552)],PURPLE,3,True)
    p.line([(1104,696),(1151,696),(1151,552)],PURPLE,3)

    p.box(1194,280,650,120,'bias 预取与调度控制',['预取后保持，关闭无用读；first / last 标签随数据对齐','控制地址、有效行、缓冲所有权与复位恢复'],PURPLE,'#FFFFFF',size=24)
    p.line([(1193,320),(1131,320)],PURPLE,3,True)
    p.label(1142,308,'b40',PURPLE,15)
    p.line([(1193,377),(1150,377),(1150,395),(1131,395)],PURPLE,2,True,True)
    p.label(1140,420,'控制',PURPLE,15)
    p.box(1194,460,650,122,'结果快照 · 16 × 48 位',['逻辑 96 B；当前块转存后才允许覆盖','将两行各 8 个结果写入对应行 / 列位置'],PURPLE,'#FFFFFF',size=24,dashed=True)
    p.line([(1519,583),(1519,619)],PURPLE,3,True)
    p.label(1540,607,'选择空闲组写入',PURPLE,16)
    p.box(1194,628,310,150,'行重排缓冲 A',['2 × 256 × 48 位','逻辑 3 KiB','填充 / 排出交替'],PURPLE,PURPLE_L,size=22,dashed=True)
    p.box(1534,628,310,150,'行重排缓冲 B',['2 × 256 × 48 位','逻辑 3 KiB','禁止覆盖未读结果'],PURPLE,PURPLE_L,size=22,dashed=True)
    p.line([(1519,620),(1348,620),(1348,627)],PURPLE,2.5,True)
    p.line([(1519,620),(1688,620),(1688,627)],PURPLE,2.5,True)
    p.line([(1348,780),(1348,812),(1519,812)],PURPLE,2.5)
    p.line([(1688,780),(1688,812),(1519,812),(1519,832)],PURPLE,2.5,True)
    p.label(1550,806,'选择就绪组排出',PURPLE,16)
    p.box(1194,841,650,110,'有序输出与回压',['整行排出；索引 0..25343','全部写事务确认后，系统才报告完成'],BLUE,BLUE_L,size=23)

    p.rect(66,810,1064,136,AMBER_L,None,12)
    p.text(88,846,'99 行 = 49 个完整行对 + 1 个尾行',25,AMBER,True)
    p.text(88,879,'尾组关闭第二行的输入读、MAC 和写出，只产生最后 256 个结果。',21,INK)
    p.text(88,912,'两组重排缓冲逻辑合计 6 KiB；指定宏取整、端口与面积需另行验收。',20,MUTED)
    p.line([(1194,887),(1165,887),(1165,796),(449,796),(449,747)],RED,2,True,True)
    p.label(647,797,'缓冲满 → 反向暂停；恢复后无丢失 / 重复 / 乱序',RED,17)
    p.text(66,991,'推导：内部 W 读字数 1,622,016 → 819,200（约 -49.5%）；这是访存量，不是整机能耗或性能实测。',21,INK)
    return p


def verification():
    p=Page('04-verification-release','验证、工艺验收与最终交付闭环',
           '两种正确性分别证明：位级一致 + 浮点误差  |  功能合格后，再比较系统效率与创新收益',5)
    p.box(56,191,390,151,'冻结输入与版本 · C',['官方源码 / 权重 / 数据划分','层号、尺度、格式与输入哈希','训练标定；验证评估；测试不调参'],TEAL,TEAL_L,size=23)
    p.box(506,191,370,113,'位精确软件模型',['产生整数期望 Y_code','输入同一份 X/W/b 编码'],TEAL,'#FFFFFF',size=23)
    p.box(506,362,370,113,'固定官方浮点模型',['原始浮点输入产生 Y_ref','对应每层正确的前馈输入'],TEAL,'#FFFFFF',size=23)
    p.line([(446,239),(497,239)],TEAL,3,True)
    p.line([(446,296),(474,296),(474,418),(497,418)],TEAL,3,True)
    p.box(56,535,390,151,'实际执行路径 · A/B',['E203 调度 → RTL 硬件计算','完整 Y 写回共享 SRAM','参考答案不参与硬件执行'],BLUE,BLUE_L,size=23)
    p.line([(251,343),(251,526)],BLUE,3,True)
    p.label(268,426,'实际编码 X/W/b',BLUE,19)
    p.box(506,535,370,151,'写回结果与解码',['读取全部 25,344 个结果','原始整数 Y_code → 位一致','解码 decode(Y_code) → 误差'],BLUE,'#FFFFFF',size=23)
    p.line([(446,610),(497,610)],BLUE,3,True)

    p.box(950,191,408,113,'位一致检查',['软件整数 == RTL / SoC 输出','所有已运行向量逐项比较'],TEAL,TEAL_L,size=23)
    p.box(950,362,408,159,'真实精度检查',['12 层全样本：软件模型评估','取最大 NRMSE ≤ 3%','12 个性能任务各自也须 ≤ 3%'],TEAL,TEAL_L,size=23)
    p.line([(877,247),(941,247)],TEAL,3,True)
    p.line([(740,305),(740,333),(1154,333),(1154,353)],TEAL,2.5,True)
    p.label(891,327,'decode(Y_model)',TEAL,17)
    p.line([(877,416),(941,416)],TEAL,3,True)
    p.line([(876,579),(910,579),(910,279),(941,279)],BLUE,2.5,True)
    p.line([(910,492),(941,492)],BLUE,2.5,True)
    p.label(884,266,'整数码',BLUE,16)
    p.label(884,479,'解码值',BLUE,16)
    p.label(912,558,'实际结果',BLUE,16)

    p.box(950,581,408,162,'指定工艺验收 · B',['SRAM / 标准单元库 / SDC','150 MHz；新增面积 ≤ 2.25 mm²','综合前后核对；功耗覆盖完整'],AMBER,AMBER_L,size=23)
    p.line([(446,667),(474,667),(474,730),(940,730)],PURPLE,2.5,True)
    p.label(594,730,'同一 RTL / 配置 / 宏版本',PURPLE,18)

    p.rect(1425,191,439,552,BG,LINE,14)
    p.text(1450,231,'资格门 → 公平对照 → 冻结',25,INK,True)
    p.box(1450,261,389,112,'G2：资格全部通过',['功能 + 位一致 + 精度','SoC + 时序 + 面积'],AMBER,'#FFFFFF',size=23)
    p.line([(1359,249),(1392,249),(1392,317),(1441,317)],TEAL,2,True)
    p.line([(1359,439),(1392,439),(1392,317)],TEAL,2)
    p.line([(1359,663),(1410,663),(1410,342),(1441,342)],AMBER,2,True)
    p.line([(1644,374),(1644,403)],INK,2.5,True)
    p.box(1450,412,389,142,'四配置公平对照',['V0：1×8  V1：1×16','V2：2×8  V3：+写回重叠','同数据 / 格式 / 工艺 / 测量窗口'],PURPLE,'#FFFFFF',size=22)
    p.line([(1644,555),(1644,585)],INK,2.5,True)
    p.box(1450,594,389,122,'最终配置与交付包',['D16 择优；D17 冻结','独立复现、报告、演示与贡献'],GREEN,GREEN_L,size=23)

    p.rect(56,795,1808,106,INK,None,14)
    p.text(80,830,'每次执行都保存证据',24,'#FFFFFF',True)
    p.text(80,870,'命令 + 退出码 + 完整结束标记 + 源码/输入/配置哈希 + 日志 + 工具版本 + 已知限制',23,'#D9E6F3')
    p.line([(690,687),(690,785)],BLUE,2,True)
    p.line([(1154,744),(1154,785)],AMBER,2,True)
    p.line([(1644,717),(1644,785)],GREEN,2,True)
    p.line([(251,795),(251,748),(37,748),(37,612),(47,612)],RED,2,True,True)
    p.label(61,770,'FAIL → 定位责任模块 → 修复 → 重跑',RED,18)
    p.rect(56,928,1808,64,BG,None,10)
    p.text(78,967,'harness 绑定证据 → PROGRESS 当前状态 → DECISION 设计取舍 → checkpoint 可恢复版本',23,INK,True)
    p.text(1700,967,'状态分层',17,MUTED)
    return p


def arrow_polygon(points, size=10):
    (x0,y0),(x1,y1)=points[-2:]
    a=math.atan2(y1-y0,x1-x0)
    return [(x1,y1),(x1-size*math.cos(a)+size*.46*math.sin(a),y1-size*math.sin(a)-size*.46*math.cos(a)),
            (x1-size*math.cos(a)-size*.46*math.sin(a),y1-size*math.sin(a)+size*.46*math.cos(a))]


def svg(page):
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
         f'<title id="title">{escape(page.title)}</title>',
         '<desc id="desc">KWT-1 项目工程图。规划与当前实现状态分开标注；不能将优化候选当作验收通过。</desc>']
    for e in page.e:
        if e['type']=='rect':
            st=e['stroke'] or 'none'
            ds=' stroke-dasharray="9 6"' if e['dashed'] else ''
            out.append(f'<rect x="{e["x"]}" y="{e["y"]}" width="{e["w"]}" height="{e["h"]}" rx="{e["radius"]}" fill="{e["fill"]}" stroke="{st}" stroke-width="{e["sw"]}"{ds}/>')
        elif e['type']=='text':
            anchor={'left':'start','center':'middle','right':'end'}[e['align']]
            out.append(f'<text x="{e["x"]}" y="{e["y"]}" fill="{e["color"]}" font-size="{e["size"]}" text-anchor="{anchor}" font-family="DejaVu Sans,Droid Sans Fallback,Noto Sans CJK SC,sans-serif" font-weight="{700 if e["bold"] else 400}">{escape(e["text"])}</text>')
        else:
            ps=' '.join(f'{x},{y}' for x,y in e['points'])
            ds=' stroke-dasharray="8 6"' if e['dashed'] else ''
            out.append(f'<polyline points="{ps}" fill="none" stroke="{e["color"]}" stroke-width="{e["sw"]}" stroke-linecap="round" stroke-linejoin="round"{ds}/>')
            if e['arrow']:
                aps=' '.join(f'{x:.2f},{y:.2f}' for x,y in arrow_polygon(e['points']))
                out.append(f'<polygon points="{aps}" fill="{e["color"]}"/>')
    return '\n'.join(out+['</svg>'])


def draw_pdf(pages):
    PDF.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(PDF),pagesize=(W/2,H/2),pageCompression=1)
    c.setTitle('KWT-1 工程流程与数据通路图册')
    c.setAuthor('KWT-1 Project Team')
    for p in pages:
        c.saveState(); c.scale(.5,.5)
        for e in p.e:
            c.saveState()
            if e['type']=='rect':
                c.setFillColor(HexColor(e['fill']))
                if e['stroke']: c.setStrokeColor(HexColor(e['stroke']))
                c.setLineWidth(e['sw'])
                if e['dashed']:c.setDash(9,6)
                c.roundRect(e['x'],H-e['y']-e['h'],e['w'],e['h'],e['radius'],stroke=bool(e['stroke']),fill=1)
            elif e['type']=='text':
                x=e['x']; width=tw(e['text'],e['size'],e['bold'])
                if e['align']=='center':x-=width/2
                if e['align']=='right':x-=width
                c.setFillColor(HexColor(e['color']))
                for font,t in runs(e['text'],e['bold']):
                    c.setFont(font,e['size']);c.drawString(x,H-e['y'],t)
                    x+=pdfmetrics.stringWidth(t,font,e['size'])
            else:
                c.setStrokeColor(HexColor(e['color'])); c.setLineWidth(e['sw']); c.setLineCap(1);c.setLineJoin(1)
                if e['dashed']:c.setDash(8,6)
                path=c.beginPath();path.moveTo(e['points'][0][0],H-e['points'][0][1])
                for x,y in e['points'][1:]:path.lineTo(x,H-y)
                c.drawPath(path)
                if e['arrow']:
                    c.setDash();c.setFillColor(HexColor(e['color']))
                    path=c.beginPath();pts=arrow_polygon(e['points']);path.moveTo(pts[0][0],H-pts[0][1])
                    for x,y in pts[1:]:path.lineTo(x,H-y)
                    path.close();c.drawPath(path,stroke=0,fill=1)
            c.restoreState()
        c.restoreState();c.showPage()
    c.save()


def drawio(pages):
    root=ET.Element('mxfile',host='app.diagrams.net',type='device',version='24.7.17')
    for p in pages:
        diagram=ET.SubElement(root,'diagram',name=p.title,id=p.name)
        model=ET.SubElement(diagram,'mxGraphModel',dx=str(W),dy=str(H),grid='1',gridSize='10',page='1',pageScale='1',pageWidth=str(W),pageHeight=str(H),background='#ffffff')
        r=ET.SubElement(model,'root');ET.SubElement(r,'mxCell',id='0');ET.SubElement(r,'mxCell',id='1',parent='0')
        for i,e in enumerate(p.e):
            attrs={'id':str(i+2),'parent':'1'}
            if e['type']=='line':
                attrs.update(edge='1',style=f'edgeStyle=none;rounded=0;html=1;strokeColor={e["color"]};strokeWidth={e["sw"]};endArrow={"block" if e["arrow"] else "none"};endFill=1;dashed={int(e["dashed"])};')
                cell=ET.SubElement(r,'mxCell',**attrs);g=ET.SubElement(cell,'mxGeometry',relative='1',**{'as':'geometry'})
                ps=e['points'];ET.SubElement(g,'mxPoint',x=str(ps[0][0]),y=str(ps[0][1]),**{'as':'sourcePoint'})
                ET.SubElement(g,'mxPoint',x=str(ps[-1][0]),y=str(ps[-1][1]),**{'as':'targetPoint'})
                if len(ps)>2:
                    a=ET.SubElement(g,'Array',**{'as':'points'})
                    for x,y in ps[1:-1]:ET.SubElement(a,'mxPoint',x=str(x),y=str(y))
            else:
                attrs['vertex']='1'
                if e['type']=='rect':
                    x,y,w,h=e['x'],e['y'],e['w'],e['h']
                    attrs['style']=f'rounded={int(e["radius"]>0)};arcSize=10;whiteSpace=wrap;html=1;fillColor={e["fill"]};strokeColor={e["stroke"] or "none"};strokeWidth={e["sw"]};dashed={int(e["dashed"])};'
                else:
                    w=tw(e['text'],e['size'],e['bold'])+14;h=e['size']*1.5
                    x=e['x']-7;y=e['y']-e['size']*1.12
                    if e['align']=='center':x-=w/2-7
                    if e['align']=='right':x-=w-14
                    attrs['value']=e['text']
                    attrs['style']=f'text;html=0;whiteSpace=wrap;overflow=visible;align=left;verticalAlign=middle;spacing=0;strokeColor=none;fillColor=none;fontColor={e["color"]};fontSize={e["size"]};fontStyle={1 if e["bold"] else 0};fontFamily=Noto Sans CJK SC;'
                cell=ET.SubElement(r,'mxCell',**attrs);ET.SubElement(cell,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),**{'as':'geometry'})
    return ET.tostring(root,encoding='unicode',xml_declaration=True)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    pages=[engineering(),workflow(),system(),micro(),verification()]
    for p in pages:
        (OUT/(p.name+'.svg')).write_text(svg(p),encoding='utf-8')
    (OUT/'kwt-engineering-atlas.drawio').write_text(drawio(pages),encoding='utf-8')
    (OUT/'diagram-source.json').write_text(json.dumps([{'name':p.name,'title':p.title,'elements':p.e} for p in pages],ensure_ascii=False,indent=2),encoding='utf-8')
    draw_pdf(pages)
    print(json.dumps({'status':'GENERATED','pages':len(pages),'pdf':str(PDF),'source_dir':str(OUT),'scope':'diagram generation only; no new hardware validation'},ensure_ascii=False))


if __name__=='__main__':main()
