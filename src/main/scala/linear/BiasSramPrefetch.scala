package linear

import chisel3._
import chisel3.util._
import memory.Sram1024x16

class BiasSramPrefetchIO extends Bundle {
    val computeActive = Input(Bool())
    val invalidate = Input(Bool())
    val clearValid = Input(Bool())
    val clearReady = Output(Bool())
    val clearDone = Output(Bool())
    val hostValid = Input(Bool())
    val hostReady = Output(Bool())
    val hostRead = Input(Bool())
    val hostAddr = Input(UInt(8.W))
    val hostData = Input(UInt(40.W))
    val hostMask = Input(UInt(5.W))
    val rspValid = Output(Bool())
    val rspReady = Input(Bool())
    val rspError = Output(Bool())
    val rspData = Output(UInt(40.W))
    // Idle includes the host response: a command cannot be mistaken for committed
    // merely because the SRAM sequencer returned to IDLE.
    val hostIdle = Output(Bool())
    val groupReqValid = Input(Bool())
    val groupReqReady = Output(Bool())
    val groupReqTag = Input(UInt(5.W))
    val groupValid = Output(Bool())
    val groupTag = Output(UInt(5.W))
    val groupEpoch = Output(UInt(32.W))
    val groupBias = Output(Vec(8, SInt(40.W)))
    val groupTake = Input(Bool())
    val epoch = Output(UInt(32.W))
}

private object BiasSramState extends ChiselEnum {
    val idle, selectWord, readIssue, readCapture, writeCommit, clearWord = Value
}
private object BiasSramOwner extends ChiselEnum {
    val hostRead, hostWrite, groupFill = Value
}

/** One real 1024x16 synchronous single-port memory; two tagged eight-bias slots.
  * Host descriptors are captured once. The response is not published until the
  * final physical write commits or all three read words have been sampled.
  * A full group uses 24 issue/capture pairs (48 memory cycles), deliberately
  * matching the independently exercised SV prototype before further pipelining.
  */
class BiasSramPrefetch extends Module {
    val io = IO(new BiasSramPrefetchIO)
    private val memory = Module(new Sram1024x16)
    private val state = RegInit(BiasSramState.idle)
    private val owner = RegInit(BiasSramOwner.hostRead)
    private val hostAddr = Reg(UInt(8.W))
    private val hostData = Reg(UInt(40.W))
    private val hostMask = Reg(UInt(5.W))
    private val hostWord = RegInit(0.U(2.W))
    private val readData = Reg(UInt(40.W))
    private val writeWord = Reg(UInt(16.W))
    private val clearAddr = RegInit(0.U(10.W))
    private val responseValid = RegInit(false.B)
    private val responseError = RegInit(false.B)
    private val responseData = Reg(UInt(40.W))
    private val clearDone = RegInit(false.B)
    private val epoch = RegInit(0.U(32.W))
    private val wantedPending = RegInit(false.B)
    private val wantedTag = RegInit(0.U(5.W))
    private val slotValid = RegInit(VecInit(Seq.fill(2)(false.B)))
    private val slotTag = Reg(Vec(2, UInt(5.W)))
    private val slotEpoch = Reg(Vec(2, UInt(32.W)))
    // No payload reset: software must load all parameters or explicitly clear.
    private val slotData = Reg(Vec(2, Vec(8, UInt(40.W))))
    private val fillSlot = Reg(Bool())
    private val fillTag = Reg(UInt(5.W))
    private val fillWord = RegInit(0.U(5.W))
    private val fillEpoch = Reg(UInt(32.W))
    private val lastGrantHost = RegInit(false.B)

    private val currentHits = VecInit((0 until 2).map(i =>
        slotValid(i) && slotTag(i) === wantedTag && slotEpoch(i) === epoch))
    private val currentHit = currentHits.asUInt.orR
    private val nextTag = (wantedTag + 1.U)(4, 0)
    private val nextHit = (0 until 2).map(i =>
        slotValid(i) && slotTag(i) === nextTag && slotEpoch(i) === epoch).reduce(_ || _)
    private val demandMissing = wantedPending && !currentHit
    private val prefetchMissing = wantedPending && currentHit && wantedTag =/= 31.U && !nextHit
    private val fillNeeded = demandMissing || prefetchMissing
    private val nextFillSlot = Mux(demandMissing, slotValid(0) && !slotValid(1), currentHits(0))
    private val nextFillTag = Mux(demandMissing, wantedTag, nextTag)
    private val clearFire = io.clearValid && io.clearReady
    private val hostFire = io.hostValid && io.hostReady
    private val groupFire = io.groupReqValid && io.groupReqReady

    io.clearReady := !reset.asBool && state === BiasSramState.idle &&
        !io.computeActive && !wantedPending && !io.invalidate
    io.hostReady := !reset.asBool && state === BiasSramState.idle &&
        (!responseValid || io.rspReady) && !clearFire && !io.invalidate &&
        (!fillNeeded || !lastGrantHost)
    io.groupReqReady := !reset.asBool && !wantedPending && !clearFire && !io.invalidate
    io.groupValid := !reset.asBool && wantedPending && currentHit && !io.invalidate && !clearFire
    io.groupTag := wantedTag
    io.groupEpoch := epoch
    io.epoch := epoch
    io.groupBias := VecInit(Mux(currentHits(0), slotData(0), slotData(1)).map(_.asSInt))
    io.rspValid := responseValid
    io.rspError := responseError
    io.rspData := responseData
    io.clearDone := clearDone
    io.hostIdle := !responseValid && (state === BiasSramState.idle ||
        (owner === BiasSramOwner.groupFill && state =/= BiasSramState.clearWord))

    private val wordMask = MuxLookup(hostWord, 0.U(2.W))(Seq(
        0.U -> hostMask(1, 0), 1.U -> hostMask(3, 2), 2.U -> Cat(0.U(1.W), hostMask(4))))
    private val wordData = MuxLookup(hostWord, 0.U(16.W))(Seq(
        0.U -> hostData(15, 0), 1.U -> hostData(31, 16), 2.U -> Cat(0.U(8.W), hostData(39, 32))))
    private val byteMask = Cat(Fill(8, wordMask(1)), Fill(8, wordMask(0)))
    private val hostPhysicalAddr = ((hostAddr << 1) +& hostAddr +& hostWord)(9, 0)
    private val groupPhysicalAddr = ((fillTag << 4) +& (fillTag << 3) +& fillWord)(9, 0)
    memory.io.en := false.B
    memory.io.isWrite := false.B
    memory.io.addr := 0.U
    memory.io.wdata := 0.S
    when(!reset.asBool && state === BiasSramState.readIssue) {
        memory.io.en := true.B
        memory.io.addr := Mux(owner === BiasSramOwner.groupFill, groupPhysicalAddr, hostPhysicalAddr)
    }.elsewhen(!reset.asBool && state === BiasSramState.writeCommit) {
        memory.io.en := true.B
        memory.io.isWrite := true.B
        memory.io.addr := hostPhysicalAddr
        memory.io.wdata := writeWord.asSInt
    }.elsewhen(!reset.asBool && state === BiasSramState.clearWord) {
        memory.io.en := true.B
        memory.io.isWrite := true.B
        memory.io.addr := clearAddr
    }

    clearDone := false.B
    when(responseValid && io.rspReady) { responseValid := false.B }
    when(groupFire) { wantedPending := true.B; wantedTag := io.groupReqTag }
    when(io.groupValid && io.groupTake) {
        wantedPending := false.B
        for (slot <- 0 until 2) when(currentHits(slot)) { slotValid(slot) := false.B }
    }
    when(io.invalidate) {
        epoch := epoch + 1.U
        slotValid.foreach(_ := false.B)
        // Keep an accepted demand alive. An obsolete in-flight fill is discarded
        // below and that same demand is retried with the new epoch.
    }

    switch(state) {
        is(BiasSramState.idle) {
            when(clearFire) {
                epoch := epoch + 1.U
                slotValid.foreach(_ := false.B)
                slotData.foreach(_.foreach(_ := 0.U))
                clearAddr := 0.U
                state := BiasSramState.clearWord
            }.elsewhen(hostFire) {
                lastGrantHost := true.B
                when(!io.hostRead && (io.computeActive || (io.groupValid && io.groupTake))) {
                    responseValid := true.B; responseError := true.B; responseData := 0.U
                }.otherwise {
                    owner := Mux(io.hostRead, BiasSramOwner.hostRead, BiasSramOwner.hostWrite)
                    hostAddr := io.hostAddr; hostData := io.hostData; hostMask := io.hostMask
                    hostWord := 0.U; readData := 0.U; state := BiasSramState.selectWord
                    when(!io.hostRead) { epoch := epoch + 1.U; slotValid.foreach(_ := false.B) }
                }
            }.elsewhen(fillNeeded && !io.invalidate) {
                lastGrantHost := false.B; owner := BiasSramOwner.groupFill
                fillSlot := nextFillSlot; fillTag := nextFillTag; fillWord := 0.U; fillEpoch := epoch
                slotValid(nextFillSlot) := false.B; state := BiasSramState.readIssue
            }
        }
        is(BiasSramState.selectWord) {
            when(owner === BiasSramOwner.hostRead) { state := BiasSramState.readIssue }
            .elsewhen(wordMask === 0.U) {
                when(hostWord === 2.U) {
                    responseValid := true.B; responseError := false.B; responseData := 0.U
                    state := BiasSramState.idle
                }.otherwise { hostWord := hostWord + 1.U }
            }.elsewhen(wordMask === 3.U || hostWord === 2.U) {
                writeWord := wordData; state := BiasSramState.writeCommit
            }.otherwise { state := BiasSramState.readIssue }
        }
        is(BiasSramState.readIssue) { state := BiasSramState.readCapture }
        is(BiasSramState.readCapture) {
            assert(memory.io.rvalid, "Bias SRAM Q sampled without a completed synchronous read")
            val data = memory.io.rdata.asUInt
            when(owner === BiasSramOwner.groupFill) {
                when(fillEpoch =/= epoch || io.invalidate) { state := BiasSramState.idle }
                .otherwise {
                    // Constants avoid inferred division/modulo or a variable
                    // part-select in the physical SRAM-to-staging path.
                    for (lane <- 0 until 8) {
                        when(fillWord === (lane * 3).U) {
                            slotData(fillSlot)(lane) := Cat(slotData(fillSlot)(lane)(39, 16), data)
                        }
                        when(fillWord === (lane * 3 + 1).U) {
                            slotData(fillSlot)(lane) := Cat(slotData(fillSlot)(lane)(39, 32), data,
                                slotData(fillSlot)(lane)(15, 0))
                        }
                        when(fillWord === (lane * 3 + 2).U) {
                            slotData(fillSlot)(lane) := Cat(data(7, 0), slotData(fillSlot)(lane)(31, 0))
                        }
                    }
                    when(fillWord === 23.U) {
                        slotValid(fillSlot) := true.B; slotTag(fillSlot) := fillTag
                        slotEpoch(fillSlot) := fillEpoch; state := BiasSramState.idle
                    }.otherwise { fillWord := fillWord + 1.U; state := BiasSramState.readIssue }
                }
            }.elsewhen(owner === BiasSramOwner.hostRead) {
                switch(hostWord) {
                    is(0.U) { readData := Cat(readData(39, 16), data) }
                    is(1.U) { readData := Cat(readData(39, 32), data, readData(15, 0)) }
                    is(2.U) { readData := Cat(data(7, 0), readData(31, 0)) }
                }
                when(hostWord === 2.U) {
                    responseValid := true.B; responseError := false.B
                    responseData := Cat(data(7, 0), readData(31, 0)); state := BiasSramState.idle
                }.otherwise { hostWord := hostWord + 1.U; state := BiasSramState.selectWord }
            }.otherwise {
                writeWord := (data & ~byteMask) | (wordData & byteMask)
                state := BiasSramState.writeCommit
            }
        }
        is(BiasSramState.writeCommit) {
            when(hostWord === 2.U) {
                responseValid := true.B; responseError := false.B; responseData := 0.U
                state := BiasSramState.idle
            }.otherwise { hostWord := hostWord + 1.U; state := BiasSramState.selectWord }
        }
        is(BiasSramState.clearWord) {
            when(clearAddr === 767.U) { clearDone := true.B; state := BiasSramState.idle }
            .otherwise { clearAddr := clearAddr + 1.U }
        }
    }
    when(memory.io.en) { assert(memory.io.addr < 768.U) }
    when(io.groupValid && io.groupTake) { assert(io.groupEpoch === epoch) }
}
