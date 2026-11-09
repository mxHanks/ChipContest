package linear

import chisel3._

class LinearAutoGroupCoreIO extends LinearCachedCoreIO {
    // cacheWriteEnable is now a valid signal: hold its descriptor until ready.
    // A read uses cacheReadEnable/cacheReadAddr. Both share one response slot.
    val cacheReadEnable = Input(Bool())
    val cacheCmdReady = Output(Bool())
    val cacheRspValid = Output(Bool())
    val cacheRspReady = Input(Bool())
    val cacheRspError = Output(Bool())
    val cacheIdle = Output(Bool())
    val cacheInvalidate = Input(Bool())
    val cacheClearValid = Input(Bool())
    val cacheClearReady = Output(Bool())
    val cacheClearDone = Output(Bool())
    // Elaborated storage identity: zero for the register-cache ablation.
    // The MMIO wrapper must not advertise or dispatch an unsupported clear.
    val biasSramCapability = Output(UInt(32.W))
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
class LinearAutoGroupCore(useBiasSram: Boolean = true, accWidth: Int = 48) extends Module {
    val io = IO(new LinearAutoGroupCoreIO)
    io.biasSramCapability := (if (useBiasSram) "h42530001".U(32.W) else 0.U(32.W))
    private val core = Module(new LinearComputeCore(accWidth))
    private val active = RegInit(false.B)
    private val running = RegInit(false.B)
    private val produced = RegInit(0.U(6.W))
    private val retired = RegInit(0.U(6.W))
    private val count = RegInit(0.U(2.W))
    private val head = RegInit(false.B)
    private val tail = RegInit(false.B)
    private val results = Reg(Vec(2, Vec(8, SInt(48.W))))
    private val manualPending = RegInit(false.B)
    private val manualRunning = RegInit(false.B)
    private val manualGroup = Reg(UInt(5.W))
    private val manualCached = Reg(Bool())
    private val biasReady = Wire(Bool())
    private val selectedBias = Wire(Vec(8, SInt(40.W)))

    private val launch = active && !running && produced < 32.U && count < 2.U &&
        (!io.cacheEnable || biasReady)
    private val enqueue = active && running && core.io.done
    private val pop = io.rowPop && active && count =/= 0.U
    private val selectedGroup = Mux(active, produced(4, 0), Mux(manualPending || manualRunning,
        manualGroup, io.group))
    private val manualLaunch = !active && manualPending && biasReady
    private val computeLaunch = Mux(active, launch,
        Mux(io.cacheEnable, manualLaunch, io.start))
    // INIT samples bias on the edge following start. Releasing the group on
    // start itself would permit its slot to be reused one edge too early.
    private val takeBias = RegNext(computeLaunch && io.cacheEnable, false.B)
    private val modeChanged = RegNext(io.cacheEnable, false.B) =/= io.cacheEnable
    private val schedulerIdle = !active && !manualPending && !manualRunning && !takeBias

    // External invalidation is a configuration operation. The standalone SRAM
    // module can retry a cancelled demand, but this scheduler must not retract
    // a bias group during the compute core's INIT sampling edge.
    when(io.cacheInvalidate) {
        assert(schedulerIdle && !io.start && !io.rowStart,
            "Bias invalidation requires an idle scheduler and no START")
    }
    when(modeChanged) {
        assert(schedulerIdle && !io.start && !io.rowStart,
            "Bias mode switch requires an idle scheduler and no START")
    }
    assert(!(io.start && io.rowStart), "Manual START and ROW_START are mutually exclusive")

    when(io.start && !active) {
        assert(!manualPending && !manualRunning && io.cacheIdle)
        manualGroup := io.group
        manualCached := io.cacheEnable
        when(io.cacheEnable) { manualPending := true.B }
        .otherwise { manualRunning := true.B }
    }
    when(manualLaunch) { manualPending := false.B; manualRunning := true.B }
    when(core.io.done && !active) { manualRunning := false.B }
    when(manualPending || manualRunning) {
        assert(io.cacheEnable === manualCached, "Bias mode changed during a manual computation")
    }

    when(io.rowStart) {
        assert(!active && count === 0.U && !manualPending && !manualRunning && io.cacheIdle)
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

    core.io.start := computeLaunch
    core.io.group := selectedGroup
    core.io.xLoadWen := io.xLoadWen
    core.io.xLoadAddr := io.xLoadAddr
    core.io.xLoadData := io.xLoadData
    core.io.wLoadWen := io.wLoadWen
    core.io.wLoadBank := io.wLoadBank
    core.io.wLoadAddr := io.wLoadAddr
    core.io.wLoadData := io.wLoadData
    if (useBiasSram) {
        val biasCache = Module(new BiasSramPrefetch)
        biasCache.io.computeActive := active || manualPending || manualRunning
        biasCache.io.invalidate := io.cacheInvalidate || modeChanged
        biasCache.io.clearValid := io.cacheClearValid
        io.cacheClearReady := biasCache.io.clearReady
        io.cacheClearDone := biasCache.io.clearDone
        biasCache.io.hostValid := io.cacheWriteEnable || io.cacheReadEnable
        biasCache.io.hostRead := io.cacheReadEnable
        biasCache.io.hostAddr := Mux(io.cacheReadEnable, io.cacheReadAddr, io.cacheWriteAddr)
        biasCache.io.hostData := io.cacheWriteData
        biasCache.io.hostMask := io.cacheWriteMask
        io.cacheCmdReady := biasCache.io.hostReady
        io.cacheRspValid := biasCache.io.rspValid
        biasCache.io.rspReady := io.cacheRspReady
        io.cacheRspError := biasCache.io.rspError
        io.cacheReadData := biasCache.io.rspData
        io.cacheIdle := biasCache.io.hostIdle
        // INIT samples the current bias before takeBias releases its demand.
        // Once that edge has passed, request the next group while this group's
        // MACs run. The compute selector remains on produced until enqueue;
        // only the independent bias request looks ahead. A pending demand is
        // held by the SRAM module and its ready prevents duplicate acceptance.
        val nextBiasDemand = active && running && !takeBias && produced < 31.U
        biasCache.io.groupReqValid := io.cacheEnable &&
            ((active && !running && produced < 32.U) || nextBiasDemand ||
                (!active && manualPending))
        biasCache.io.groupReqTag := Mux(nextBiasDemand,
            (produced + 1.U)(4, 0), selectedGroup)
        biasCache.io.groupTake := takeBias
        biasReady := biasCache.io.groupValid && biasCache.io.groupTag === selectedGroup
        selectedBias := biasCache.io.groupBias
        when(takeBias) {
            assert(biasCache.io.groupValid && biasCache.io.groupTag === selectedGroup,
                "Compute INIT must consume its own bias group")
        }
    } else {
        // Explicit register-cache ablation. The host still uses the same
        // command/response interface, so its response cannot escape timing.
        val biasCache = Module(new BiasBankCache)
        val responseValid = RegInit(false.B)
        val responseData = Reg(UInt(40.W))
        val hostFire = (io.cacheWriteEnable || io.cacheReadEnable) && io.cacheCmdReady
        io.cacheCmdReady := !responseValid || io.cacheRspReady
        io.cacheRspValid := responseValid
        io.cacheRspError := false.B
        io.cacheReadData := responseData
        io.cacheIdle := !responseValid
        io.cacheClearReady := false.B
        io.cacheClearDone := false.B
        when(responseValid && io.cacheRspReady) { responseValid := false.B }
        when(hostFire) {
            responseValid := true.B
            responseData := Mux(io.cacheReadEnable, biasCache.io.readData, 0.U)
        }
        biasCache.io.writeEnable := hostFire && io.cacheWriteEnable
        biasCache.io.writeAddr := io.cacheWriteAddr
        biasCache.io.writeData := io.cacheWriteData
        biasCache.io.writeMask := io.cacheWriteMask
        biasCache.io.readAddr := io.cacheReadAddr
        biasCache.io.group := selectedGroup
        selectedBias := biasCache.io.bias
        biasReady := true.B
        assert(!io.cacheClearValid, "The register-cache ablation has no SRAM-clear operation")
    }
    assert(!(io.cacheWriteEnable && io.cacheReadEnable))
    core.io.bias := Mux(io.cacheEnable, selectedBias, io.bias)
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
