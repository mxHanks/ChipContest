package linear

import chisel3._
import chisel3.util.{Cat, Fill, log2Ceil}

/** Independent 64PE scheduler: one 32KiB logical W array, explicit 8/32/64
  * contracts. The frozen 32PE implementation is not edited by this experiment.
  */
class XuParallel64AutoGroupCore extends Module {
    private val peCount = 64
    private val g = XuParallelGeometry(peCount)
    override def desiredName = s"XuParallelAutoGroupCore${g.pes}"
    val io = IO(new LinearCachedCoreIO {
        val rowStart = Input(Bool())
        val rowMode = Input(UInt(2.W))
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
    private val mode = RegInit(0.U(2.W))
    private val produced = RegInit(0.U(6.W))
    private val retired = RegInit(0.U(6.W))
    private val count = RegInit(0.U(2.W))
    private val head = RegInit(false.B)
    private val tail = RegInit(false.B)
    private val results = Reg(Vec(2, Vec(g.pes, SInt(48.W))))
    private val resultSubgroup = RegInit(0.U(g.subgroupBits.W))
    private val groupCount = Mux(mode === 2.U, 4.U, Mux(mode === 1.U, 8.U, 32.U))
    private val launch = active && !running && produced < groupCount && count < 2.U
    private val enqueue = active && running && core.io.done
    private val pop = io.rowPop && active && count =/= 0.U
    private val legacyGroup = Mux(active, produced(4, 0), io.group)
    // 64-wide rows visit four physical groups, 32-compatible rows visit each
    // half of a physical group, and the original ABI visits eight-lane slices.
    private val selectedGroup = Mux(active && mode === 2.U, produced(1, 0),
        Mux(active && mode === 1.U, produced(2, 1), legacyGroup(4, 3)))
    private val mask = Mux(active && mode === 2.U, Fill(64, 1.U(1.W)),
        Mux(active && mode === 1.U,
            ("hffffffff".U(64.W) << (produced(0) << 5))(63, 0),
            (255.U(64.W) << (legacyGroup(2, 0) << 3))(63, 0)))
    when(io.rowStart) {
        assert(!active && count === 0.U)
        assert(io.rowMode <= 2.U)
        active := true.B
        running := false.B
        mode := io.rowMode
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
