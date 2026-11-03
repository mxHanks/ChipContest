package linear

import chisel3._
import chisel3.util.{Cat, Fill, PopCount, log2Ceil}
import dotproduct.{MacController, MacPE}
import memory.{Sram1024x16, XRowBuffer}

/** Fixed 64x256 logical W; one designated 1024x16 1RW macro per output lane.
  * 32 lanes use 512 words/bank (2x physical padding); 64 use 256 (4x).
  * Padding addresses are unreachable, never additional logical parameters.
  */
case class XuParallelGeometry(pes: Int) {
    require(Set(32, 64).contains(pes))
    val bankBits = log2Ceil(pes)
    val groups = 256 / pes
    val groupBits = log2Ceil(groups)
    val addrBits = groupBits + 6
    val subgroupBits = bankBits - 3
}

class XuParallelWeightBank(g: XuParallelGeometry) extends Module {
    override def desiredName = s"XuParallelWeightBank${g.pes}"
    val io = IO(new Bundle {
        val wen = Input(Bool())
        val ren = Input(Bool())
        val addr = Input(UInt(g.addrBits.W))
        val data = Input(SInt(16.W))
        val result = Output(SInt(16.W))
    })
    private val ram = Module(new Sram1024x16)
    assert(!(io.wen && io.ren))
    ram.io.en := io.wen || io.ren
    ram.io.isWrite := io.wen
    ram.io.addr := Cat(0.U((10 - g.addrBits).W), io.addr)
    ram.io.wdata := io.data
    io.result := ram.io.rdata
}

class XuParallelComputeCore(g: XuParallelGeometry) extends Module {
    override def desiredName = s"XuParallelComputeCore${g.pes}"
    val io = IO(new Bundle {
        val start = Input(Bool())
        val group = Input(UInt(g.groupBits.W))
        val laneMask = Input(UInt(g.pes.W))
        val xLoadWen = Input(Bool())
        val xLoadAddr = Input(UInt(6.W))
        val xLoadData = Input(SInt(16.W))
        val wLoadWen = Input(Bool())
        val wLoadBank = Input(UInt(g.bankBits.W))
        val wLoadAddr = Input(UInt(g.addrBits.W))
        val wLoadData = Input(SInt(16.W))
        val bias = Input(Vec(g.pes, SInt(40.W)))
        val result = Output(Vec(g.pes, SInt(48.W)))
        val done = Output(Bool())
        val capture = Output(Bool())
        val macFire = Output(Bool())
        val laneMacs = Output(UInt(log2Ceil(g.pes + 1).W))
    })
    private val x = Module(new XRowBuffer)
    private val controller = Module(new MacController)
    private val banks = Seq.fill(g.pes)(Module(new XuParallelWeightBank(g)))
    private val pes = Seq.fill(g.pes)(Module(new MacPE))
    private val result = RegInit(VecInit(Seq.fill(g.pes)(0.S(48.W))))
    controller.io.start := io.start
    x.io.wen := io.xLoadWen
    x.io.waddr := io.xLoadAddr
    x.io.wdata := io.xLoadData
    x.io.raddr := controller.io.k
    private val readK = Mux(controller.io.init, 0.U, controller.io.k + 1.U)
    private val ren = controller.io.init || (controller.io.accumulate && controller.io.k =/= 63.U)
    for (lane <- 0 until g.pes) {
        val bank = banks(lane)
        val pe = pes(lane)
        val wen = io.wLoadWen && io.wLoadBank === lane.U
        bank.io.wen := wen
        bank.io.ren := ren && io.laneMask(lane)
        bank.io.addr := Mux(wen, io.wLoadAddr, Cat(io.group, readK))
        bank.io.data := io.wLoadData
        pe.io.init := controller.io.init && io.laneMask(lane)
        pe.io.enable := controller.io.accumulate && io.laneMask(lane)
        pe.io.x := x.io.rdata
        pe.io.w := bank.io.result
        pe.io.bias := io.bias(lane)
        when(controller.io.capture) { result(lane) := pe.io.result }
    }
    io.result := result
    io.done := controller.io.done
    io.capture := controller.io.capture
    io.macFire := controller.io.accumulate
    io.laneMacs := Mux(controller.io.accumulate, PopCount(io.laneMask), 0.U)
}

class XuParallelBiasCache(g: XuParallelGeometry) extends Module {
    override def desiredName = s"XuParallelBiasCache${g.pes}"
    val io = IO(new Bundle {
        val writeEnable = Input(Bool())
        val writeAddr = Input(UInt(8.W))
        val writeData = Input(UInt(40.W))
        val writeMask = Input(UInt(5.W))
        val readAddr = Input(UInt(8.W))
        val readData = Output(UInt(40.W))
        val group = Input(UInt(g.groupBits.W))
        val bias = Output(Vec(g.pes, SInt(40.W)))
    })
    private val banks = Reg(Vec(g.pes, Vec(g.groups, UInt(40.W))))
    private val mask = Cat((4 to 0 by -1).map(i => Fill(8, io.writeMask(i))))
    for (lane <- 0 until g.pes) {
        when(io.writeEnable && io.writeAddr(g.bankBits - 1, 0) === lane.U) {
            val group = io.writeAddr(7, g.bankBits)
            banks(lane)(group) := (banks(lane)(group) & ~mask) | (io.writeData & mask)
        }
        io.bias(lane) := banks(lane)(io.group).asSInt
    }
    io.readData := banks(io.readAddr(g.bankBits - 1, 0))(io.readAddr(7, g.bankBits))
}

/** One compute/W array serves old 8-column ABI and opt-in wide rows.
  * Old modes enable only their eight lanes; no discarded arithmetic is hidden.
  * Every legacy load address maps bijectively into the same 16384 words.
  */
class XuParallelAutoGroupCore(val peCount: Int = 32) extends Module {
    private val g = XuParallelGeometry(peCount)
    override def desiredName = s"XuParallelAutoGroupCore${g.pes}"
    val io = IO(new LinearCachedCoreIO {
        val rowStart = Input(Bool())
        val rowWide = Input(Bool())
        val rowPop = Input(Bool())
        val rowActive = Output(Bool())
        val rowRunning = Output(Bool())
        val rowValid = Output(Bool())
        val rowCount = Output(UInt(2.W))
        val rowProduced = Output(UInt(6.W))
        val rowRetired = Output(UInt(6.W))
        val rowGroup = Output(UInt(5.W))
        val rowResult = Output(Vec(g.pes, SInt(48.W)))
        val computeStart = Output(Bool())
        val macFire = Output(Bool())
        val laneMacs = Output(UInt(log2Ceil(g.pes + 1).W))
    })
    private val core = Module(new XuParallelComputeCore(g))
    private val bias = Module(new XuParallelBiasCache(g))
    private val active = RegInit(false.B)
    private val running = RegInit(false.B)
    private val wide = RegInit(false.B)
    private val produced = RegInit(0.U(6.W))
    private val retired = RegInit(0.U(6.W))
    private val count = RegInit(0.U(2.W))
    private val head = RegInit(false.B)
    private val tail = RegInit(false.B)
    private val results = Reg(Vec(2, Vec(g.pes, SInt(48.W))))
    private val resultSubgroup = RegInit(0.U(g.subgroupBits.W))
    private val groupCount = Mux(wide, g.groups.U, 32.U)
    private val launch = active && !running && produced < groupCount && count < 2.U
    private val enqueue = active && running && core.io.done
    private val pop = io.rowPop && active && count =/= 0.U
    private val legacyGroup = Mux(active, produced(4, 0), io.group)
    private val selectedGroup = Mux(active && wide, produced(g.groupBits - 1, 0),
                                   legacyGroup(4, g.subgroupBits))
    private val mask = Mux(active && wide, Fill(g.pes, 1.U(1.W)),
                          (255.U(g.pes.W) << (legacyGroup(g.subgroupBits - 1, 0) << 3))(g.pes - 1, 0))
    when(io.rowStart) {
        assert(!active && count === 0.U)
        active := true.B
        running := false.B
        wide := io.rowWide
        produced := 0.U
        retired := 0.U
        count := 0.U
        head := false.B
        tail := false.B
    }.otherwise {
        when(launch) { running := true.B }
        when(enqueue) {
            assert(count < 2.U)
            results(tail) := core.io.result
            tail := !tail
            produced := produced + 1.U
            running := false.B
        }
        when(pop) {
            head := !head
            retired := retired + 1.U
            when(retired === groupCount - 1.U) { active := false.B }
        }
        when(enqueue =/= pop) { count := Mux(enqueue, count + 1.U, count - 1.U) }
    }
    when(active) {
        assert(!io.start && !io.xLoadWen && !io.wLoadWen && !io.cacheWriteEnable)
        assert(io.cacheEnable)
        assert(produced - retired === count)
    }
    assert(count <= 2.U)
    core.io.start := Mux(active, launch, io.start)
    core.io.group := selectedGroup
    core.io.laneMask := mask
    core.io.xLoadWen := io.xLoadWen
    core.io.xLoadAddr := io.xLoadAddr
    core.io.xLoadData := io.xLoadData
    // Legacy bank/addr -> column -> the unique physical wide bank/addr.
    private val column = Cat(io.wLoadAddr(10, 6), io.wLoadBank)
    core.io.wLoadWen := io.wLoadWen
    core.io.wLoadBank := column(g.bankBits - 1, 0)
    core.io.wLoadAddr := Cat(column(7, g.bankBits), io.wLoadAddr(5, 0))
    core.io.wLoadData := io.wLoadData
    bias.io.writeEnable := io.cacheWriteEnable
    bias.io.writeAddr := io.cacheWriteAddr
    bias.io.writeData := io.cacheWriteData
    bias.io.writeMask := io.cacheWriteMask
    bias.io.readAddr := io.cacheReadAddr
    bias.io.group := selectedGroup
    for (lane <- 0 until g.pes) {
        core.io.bias(lane) := Mux(io.cacheEnable, bias.io.bias(lane), io.bias(lane % 8))
    }
    for (lane <- 0 until 8) {
        val index = Cat(resultSubgroup, lane.U(3.W))
        io.result(lane) := core.io.result(index)
    }
    when(core.io.capture) { resultSubgroup := legacyGroup(g.subgroupBits - 1, 0) }
    io.cacheReadData := bias.io.readData
    io.done := core.io.done
    io.rowActive := active
    io.rowRunning := running
    io.rowValid := count =/= 0.U
    io.rowCount := count
    io.rowProduced := produced
    io.rowRetired := retired
    io.rowGroup := retired(4, 0)
    io.rowResult := results(head)
    io.computeStart := core.io.start
    io.macFire := core.io.macFire
    io.laneMacs := core.io.laneMacs
}
