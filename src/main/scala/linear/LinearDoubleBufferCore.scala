package linear

import chisel3._

class LinearDoubleBufferCoreIO extends LinearAutoGroupCoreIO {
    val dbMode = Input(Bool())
    val dbSubmit = Input(Bool())
    val dbSubmitBank = Input(Bool())
    val dbSubmitTag = Input(UInt(7.W))
    val dbPop = Input(Bool())
    val dbXLoadWen = Input(Bool())
    val dbXLoadBank = Input(Bool())
    val dbXLoadAddr = Input(UInt(6.W))
    val dbXLoadData = Input(SInt(16.W))
    val dbBankFree = Output(UInt(2.W))
    val dbOutstanding = Output(UInt(2.W))
    val dbQueued = Output(UInt(2.W))
    val dbRunning = Output(Bool())
    val dbValid = Output(Bool())
    val dbCount = Output(UInt(2.W))
    val dbTag = Output(UInt(7.W))
    val dbGroup = Output(UInt(5.W))
    val dbResult = Output(Vec(8, SInt(48.W)))
}

/** xu S2d optional two-X-bank row queue. There remains exactly one W array,
  * dot-product engine and bias cache. S2c and manual operation use bank zero.
  * Descriptor ownership ends at group31 capture; result ownership ends only
  * at the explicit POP response retirement supplied by the bus wrapper.
  */
class LinearDoubleBufferCore extends Module {
    val io = IO(new LinearDoubleBufferCoreIO)
    private val core = Module(new LinearBufferedComputeCore)
    private val biasCache = Module(new BiasBankCache)

    // Frozen S2c scheduler behavior, now sharing the selectable X engine.
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
    when(io.rowStart) {
        assert(!io.dbMode && !active && count === 0.U)
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

    private val owned = RegInit(VecInit(Seq.fill(2)(false.B)))
    private val descriptorBank = Reg(Vec(2, Bool()))
    private val descriptorTag = Reg(Vec(2, UInt(7.W)))
    private val descriptorHead = RegInit(false.B)
    private val descriptorTail = RegInit(false.B)
    private val descriptors = RegInit(0.U(2.W))
    private val outstanding = RegInit(0.U(2.W))
    private val dbRunning = RegInit(false.B)
    private val producerGroup = RegInit(0.U(5.W))
    private val dbHead = RegInit(false.B)
    private val dbTail = RegInit(false.B)
    private val dbCount = RegInit(0.U(2.W))
    private val resultTag = Reg(Vec(2, UInt(7.W)))
    private val resultGroup = Reg(Vec(2, UInt(5.W)))
    private val dbLaunch = io.dbMode && descriptors =/= 0.U && !dbRunning && dbCount < 2.U
    private val dbEnqueue = io.dbMode && dbRunning && core.io.done
    private val producerLast = dbEnqueue && producerGroup === 31.U
    private val dbPop = io.dbPop && io.dbMode && dbCount =/= 0.U
    private val consumerLast = dbPop && resultGroup(dbHead) === 31.U
    when(io.dbSubmit) {
        assert(io.dbMode && !owned(io.dbSubmitBank) && descriptors < 2.U && outstanding < 2.U)
        descriptorBank(descriptorTail) := io.dbSubmitBank
        descriptorTag(descriptorTail) := io.dbSubmitTag
        descriptorTail := !descriptorTail
        owned(io.dbSubmitBank) := true.B
    }
    when(dbLaunch) { dbRunning := true.B }
    when(dbEnqueue) {
        assert(dbCount < 2.U)
        results(dbTail) := core.io.result
        resultTag(dbTail) := descriptorTag(descriptorHead)
        resultGroup(dbTail) := producerGroup
        dbTail := !dbTail
        dbRunning := false.B
        producerGroup := producerGroup + 1.U
    }
    when(producerLast) {
        owned(descriptorBank(descriptorHead)) := false.B
        descriptorHead := !descriptorHead
    }
    when(dbPop) { dbHead := !dbHead }
    when(io.dbSubmit =/= producerLast) {
        descriptors := Mux(io.dbSubmit, descriptors + 1.U, descriptors - 1.U)
    }
    when(io.dbSubmit =/= consumerLast) {
        outstanding := Mux(io.dbSubmit, outstanding + 1.U, outstanding - 1.U)
    }
    when(dbEnqueue =/= dbPop) { dbCount := Mux(dbEnqueue, dbCount + 1.U, dbCount - 1.U) }

    when(active) {
        assert(!io.dbMode && !io.start && !io.xLoadWen && !io.wLoadWen && !io.cacheWriteEnable)
        assert(io.cacheEnable && produced - retired === count)
    }
    when(io.dbMode) {
        assert(!active && !io.start && !io.rowStart && !io.rowPop && !io.xLoadWen)
        when(outstanding =/= 0.U) { assert(io.cacheEnable && !io.wLoadWen && !io.cacheWriteEnable) }
        when(io.dbXLoadWen) { assert(!owned(io.dbXLoadBank)) }
    }.otherwise {
        assert(outstanding === 0.U && descriptors === 0.U && dbCount === 0.U && !dbRunning)
    }
    assert(count <= 2.U && dbCount <= 2.U && outstanding <= 2.U && descriptors <= 2.U)

    private val selectedGroup = Mux(io.dbMode, producerGroup, Mux(active, produced(4, 0), io.group))
    core.io.start := Mux(io.dbMode, dbLaunch, Mux(active, launch, io.start))
    core.io.group := selectedGroup
    core.io.xReadBank := io.dbMode && descriptorBank(descriptorHead)
    core.io.xLoadBank := io.dbMode && io.dbXLoadBank
    core.io.xLoadWen := Mux(io.dbMode, io.dbXLoadWen, io.xLoadWen)
    core.io.xLoadAddr := Mux(io.dbMode, io.dbXLoadAddr, io.xLoadAddr)
    core.io.xLoadData := Mux(io.dbMode, io.dbXLoadData, io.xLoadData)
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
    io.computeStart := core.io.start
    io.rowActive := active
    io.rowRunning := running
    io.rowValid := count =/= 0.U
    io.rowCount := count
    io.rowProduced := produced
    io.rowRetired := retired
    io.rowGroup := retired(4, 0)
    io.rowResult := results(head)
    io.dbBankFree := (~owned.asUInt)(1, 0)
    io.dbOutstanding := outstanding
    io.dbQueued := descriptors
    io.dbRunning := dbRunning
    io.dbValid := dbCount =/= 0.U
    io.dbCount := dbCount
    io.dbTag := resultTag(dbHead)
    io.dbGroup := resultGroup(dbHead)
    io.dbResult := results(dbHead)
}
