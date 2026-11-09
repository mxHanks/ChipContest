package linear

import chisel3._
import chisel3.util._
import dotproduct.DotProductEngine
import memory.{WeightBankArray, XRowBuffer}

/** Isolated, synthesizable dataflow experiment; this is not a CPU/MMIO ABI.
  * Two eight-PE engines share one physical weight-bank array and one bias SRAM.
  * Two pair slots hold at most four eight-lane bundles, never a complete row.
  * outPop is the consumer's commit, after its snapshot has captured the bundle.
  * A one-row launch uses the identical datapath with the second engine gated.
  */
class LinearRowPairPrototype extends Module {
  val io = IO(new Bundle {
    val start = Input(Bool()); val secondRow = Input(Bool())
    val active = Output(Bool()); val done = Output(Bool())
    val xLoadWen = Input(Bool()); val xLoadRow = Input(Bool())
    val xLoadAddr = Input(UInt(6.W)); val xLoadData = Input(SInt(16.W))
    val wLoadWen = Input(Bool()); val wLoadBank = Input(UInt(3.W))
    val wLoadAddr = Input(UInt(11.W)); val wLoadData = Input(SInt(16.W))
    val biasHostValid = Input(Bool()); val biasHostReady = Output(Bool())
    val biasHostAddr = Input(UInt(8.W)); val biasHostData = Input(UInt(40.W))
    val biasRspValid = Output(Bool()); val biasRspError = Output(Bool())
    val clearValid = Input(Bool()); val clearReady = Output(Bool())
    val clearDone = Output(Bool()); val clearing = Output(Bool())
    val outValid = Output(Bool()); val outPop = Input(Bool())
    val outGroup = Output(UInt(5.W)); val outSecond = Output(Bool())
    val outResult = Output(Vec(8, SInt(48.W)))
    val computeStart = Output(Bool()); val weightRead = Output(Bool())
    val macStep = Output(Bool()); val fifoFullWait = Output(Bool())
    val clearWeightWrite = Output(Bool()); val clearXWrite = Output(Bool())
  })
  val active = RegInit(false.B); val running = RegInit(false.B)
  val second = RegInit(false.B)
  val produced = RegInit(0.U(6.W)); val retired = RegInit(0.U(6.W))
  val count = RegInit(0.U(2.W)); val head = RegInit(false.B); val tail = RegInit(false.B)
  val outputSecond = RegInit(false.B)
  val results = Reg(Vec(2, Vec(2, Vec(8, SInt(48.W)))))
  val tags = Reg(Vec(2, UInt(5.W)))
  val clearing = RegInit(false.B); val clearIndex = RegInit(0.U(15.W))
  val biasCleared = RegInit(false.B); val clearDone = RegInit(false.B)
  val bias = Module(new BiasSramPrefetch)
  io.clearReady := !active && !running && count === 0.U && !clearing && bias.io.clearReady
  val clearFire = io.clearValid && io.clearReady
  val engines = Seq.fill(2)(withReset(reset.asBool || clearFire) { Module(new DotProductEngine) })
  val xs = Seq.fill(2)(Module(new XRowBuffer))
  val weights = Module(new WeightBankArray)
  val selectedGroup = produced(4, 0)
  val biasReady = bias.io.groupValid && bias.io.groupTag === selectedGroup
  val launch = active && !running && produced < 32.U && count < 2.U && biasReady
  val enqueue = active && running && engines.head.io.done
  val pop = io.outPop && io.outValid
  val retirePair = pop && (!second || outputSecond)
  val takeBias = RegNext(launch, false.B)
  val nextBiasDemand = active && running && !takeBias && produced < 31.U
  bias.io.computeActive := active
  bias.io.invalidate := false.B
  bias.io.clearValid := clearFire
  bias.io.hostValid := io.biasHostValid && !active && !clearing && !clearFire
  bias.io.hostRead := false.B
  bias.io.hostAddr := io.biasHostAddr; bias.io.hostData := io.biasHostData
  bias.io.hostMask := 31.U; bias.io.rspReady := true.B
  io.biasHostReady := bias.io.hostReady && !active && !clearing && !clearFire
  io.biasRspValid := bias.io.rspValid; io.biasRspError := bias.io.rspError
  bias.io.groupReqValid := (active && !running && produced < 32.U) || nextBiasDemand
  bias.io.groupReqTag := Mux(nextBiasDemand, (produced + 1.U)(4, 0), selectedGroup)
  bias.io.groupTake := takeBias
  when(takeBias) { assert(biasReady, "Pair INIT must consume its own bias group") }
  for (row <- 0 until 2) {
    val engine = engines(row); val x = xs(row)
    engine.io.start := launch && (if (row == 0) true.B else second)
    engine.io.bias := bias.io.groupBias; engine.io.w := weights.io.rdata
    x.io.wen := (io.xLoadWen && io.xLoadRow === (row == 1).B && !clearing && !active) ||
      (clearing && clearIndex < 64.U)
    x.io.waddr := Mux(clearing, clearIndex(5, 0), io.xLoadAddr)
    x.io.wdata := Mux(clearing, 0.S, io.xLoadData)
    x.io.raddr := engine.io.k; engine.io.x := x.io.rdata
  }
  weights.io.loadWen := (io.wLoadWen && !active && !clearing) || (clearing && clearIndex < 16384.U)
  weights.io.loadBank := Mux(clearing, clearIndex(13, 11), io.wLoadBank)
  weights.io.loadAddr := Mux(clearing, clearIndex(10, 0), io.wLoadAddr)
  weights.io.loadData := Mux(clearing, 0.S, io.wLoadData)
  weights.io.ren := engines.head.io.weightRen && !clearing
  weights.io.raddr := Cat(selectedGroup, engines.head.io.weightReadK)
  when(running && second) {
    assert(engines(0).io.k === engines(1).io.k)
    assert(engines(0).io.weightRen === engines(1).io.weightRen)
    assert(engines(0).io.weightReadK === engines(1).io.weightReadK)
    assert(engines(0).io.done === engines(1).io.done)
  }
  clearDone := false.B
  when(clearFire) {
    clearing := true.B; clearIndex := 0.U; biasCleared := false.B
    results.foreach(_.foreach(_.foreach(_ := 0.S)))
    tags.foreach(_ := 0.U); outputSecond := false.B
  }.elsewhen(clearing) {
    when(bias.io.clearDone) { biasCleared := true.B }
    when(clearIndex < 16384.U) { clearIndex := clearIndex + 1.U }
    when(clearIndex === 16384.U && (biasCleared || bias.io.clearDone)) {
      clearing := false.B; clearDone := true.B
    }
  }
  io.done := false.B
  when(io.start) {
    assert(!active && !running && count === 0.U && !clearing && !clearFire && bias.io.hostIdle)
    active := true.B; running := false.B; produced := 0.U; retired := 0.U
    count := 0.U; head := false.B; tail := false.B; second := io.secondRow
    outputSecond := false.B
  }.otherwise {
    when(launch) { running := true.B }
    when(enqueue) {
      assert(count < 2.U)
      for (row <- 0 until 2) results(tail)(row) := engines(row).io.result
      tags(tail) := selectedGroup
      tail := !tail; produced := produced + 1.U; running := false.B
    }
    when(pop) {
      when(second && !outputSecond) { outputSecond := true.B }
      .otherwise { outputSecond := false.B; head := !head; retired := retired + 1.U }
    }
    when(retirePair && retired === 31.U) { active := false.B; io.done := true.B }
    when(enqueue =/= retirePair) { count := Mux(enqueue, count + 1.U, count - 1.U) }
  }
  assert(count <= 2.U)
  when(active) {
    assert(produced - retired === count)
    assert(!io.xLoadWen && !io.wLoadWen && !io.biasHostValid && !io.clearValid)
  }
  when(io.outPop) { assert(io.outValid, "POP without an owned result") }
  io.active := active; io.clearing := clearing; io.clearDone := clearDone
  io.outValid := active && count =/= 0.U
  io.outGroup := tags(head); io.outSecond := outputSecond
  io.outResult := results(head)(outputSecond)
  io.computeStart := launch; io.weightRead := weights.io.ren
  // The synchronous SRAM return is consumed on each of the 64 MAC edges,
  // including k=63 (which issues no subsequent weight read).
  io.macStep := running && RegNext(weights.io.ren, false.B)
  io.fifoFullWait := active && !running && produced < 32.U && count === 2.U
  io.clearWeightWrite := clearing && clearIndex < 16384.U
  io.clearXWrite := clearing && clearIndex < 64.U
}
