package linear

import chisel3._

class LinearAutoGroupCoreIO extends LinearCachedCoreIO {
    val rowStart = Input(Bool())
    // Pulse only when the explicit POP response retires on the host bus.
    val rowPop = Input(Bool())
    val rowActive = Output(Bool())
    val rowRunning = Output(Bool())
    val rowValid = Output(Bool())
    val rowCount = Output(UInt(2.W))
    val rowProduced = Output(UInt(6.W))
    val rowRetired = Output(UInt(6.W))
    val rowGroup = Output(UInt(5.W))
    val rowResult = Output(Vec(8, SInt(48.W)))
    val computeStart = Output(Bool())
}

/** Optional row scheduler. The existing manual START interface and compute
  * modules are unchanged. Two groups of eight signed48 values decouple the
  * single producer from host readback. A launch reserves its slot: no other
  * producer exists, and count cannot increase until that launch completes.
  * X/W/bias writes must be excluded by the host wrapper throughout rowActive.
  */
class LinearAutoGroupCore extends Module {
    val io = IO(new LinearAutoGroupCoreIO)
    private val core = Module(new LinearComputeCore)
    private val biasCache = Module(new BiasBankCache)
    private val active = RegInit(false.B)
    private val running = RegInit(false.B)
    private val produced = RegInit(0.U(6.W))
    private val retired = RegInit(0.U(6.W))
    private val count = RegInit(0.U(2.W))
    private val head = RegInit(false.B)
    private val tail = RegInit(false.B)
    private val results = Reg(Vec(2, Vec(8, SInt(48.W))))

    private val launch = active && !running && produced < 32.U && count < 2.U
    private val enqueue = active && running && core.io.done
    private val pop = io.rowPop && active && count =/= 0.U
    private val selectedGroup = Mux(active, produced(4, 0), io.group)

    when(io.rowStart) {
        assert(!active && count === 0.U)
        active := true.B
        running := false.B
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
            when(retired === 31.U) { active := false.B }
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
    core.io.xLoadWen := io.xLoadWen
    core.io.xLoadAddr := io.xLoadAddr
    core.io.xLoadData := io.xLoadData
    core.io.wLoadWen := io.wLoadWen
    core.io.wLoadBank := io.wLoadBank
    core.io.wLoadAddr := io.wLoadAddr
    core.io.wLoadData := io.wLoadData
    biasCache.io.writeEnable := io.cacheWriteEnable
    biasCache.io.writeAddr := io.cacheWriteAddr
    biasCache.io.writeData := io.cacheWriteData
    biasCache.io.writeMask := io.cacheWriteMask
    biasCache.io.readAddr := io.cacheReadAddr
    biasCache.io.group := selectedGroup
    core.io.bias := Mux(io.cacheEnable, biasCache.io.bias, io.bias)
    io.cacheReadData := biasCache.io.readData
    io.done := core.io.done
    io.result := core.io.result
    io.rowActive := active
    io.rowRunning := running
    io.rowValid := count =/= 0.U
    io.rowCount := count
    io.rowProduced := produced
    io.rowRetired := retired
    io.rowGroup := retired(4, 0)
    io.rowResult := results(head)
    io.computeStart := core.io.start
}
