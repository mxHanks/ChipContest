package linear

import chisel3._
import chisel3.util._
import dotproduct.DotProductEngine
import memory.{WeightBank, XRowBuffer}

/** Eight original banks, each containing the original two 1024x16 macros.
  * Clear uses all eight independent write ports at once; normal host loading
  * still selects one bank and keeps the historical SRAM layout and latency.
  */
private class DmaWeightBankArray extends Module {
  val io = IO(new Bundle {
    val loadWen = Input(Bool()); val loadBank = Input(UInt(3.W))
    val loadAddr = Input(UInt(11.W)); val loadData = Input(SInt(16.W))
    val loadPacked = Input(Bool()); val loadDataHi = Input(SInt(16.W))
    val clearWen = Input(Bool()); val clearAddr = Input(UInt(11.W))
    val ren = Input(Bool()); val raddr = Input(UInt(11.W))
    val rdata = Output(Vec(8, SInt(16.W)))
  })
  val banks = Seq.fill(8)(Module(new WeightBank))
  for (i <- 0 until 8) {
    val bank = banks(i)
    val low = io.loadBank === i.U
    val high = if (i % 2 == 1) io.loadPacked && io.loadBank === (i - 1).U(3.W) else false.B
    bank.io.wen := io.clearWen || (io.loadWen && (low || high))
    bank.io.waddr := Mux(io.clearWen, io.clearAddr, io.loadAddr)
    bank.io.wdata := Mux(io.clearWen, 0.S, Mux(low, io.loadData, io.loadDataHi))
    bank.io.ren := io.ren
    bank.io.raddr := io.raddr
    io.rdata(i) := bank.io.rdata
  }
}

/** DMA-facing two-row compute block. It owns no external memory master.
  * An external scheduler transfers X to an inactive ping-pong set while this
  * block computes the current pair. Results remain owned until outPop.
  * abort cancels computation and ownership; it does not claim physical clear.
  */
class LinearRowPairDmaCore extends Module {
  val io = IO(new Bundle {
    val start = Input(Bool()); val secondRow = Input(Bool())
    val abort = Input(Bool())
    val active = Output(Bool()); val done = Output(Bool())
    val xLoadWen = Input(Bool()); val xLoadRow = Input(Bool())
    val xLoadSet = Input(Bool()); val xRunSet = Input(Bool())
    val xLoadAddr = Input(UInt(6.W)); val xLoadData = Input(SInt(16.W))
    val wLoadWen = Input(Bool()); val wLoadBank = Input(UInt(3.W))
    val wLoadAddr = Input(UInt(11.W)); val wLoadData = Input(SInt(16.W))
    val wLoadPacked = Input(Bool()); val wLoadDataHi = Input(SInt(16.W))
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
  val second = RegInit(false.B); val runSet = RegInit(false.B)
  val produced = RegInit(0.U(6.W)); val retired = RegInit(0.U(6.W))
  val count = RegInit(0.U(2.W)); val head = RegInit(false.B); val tail = RegInit(false.B)
  val outputSecond = RegInit(false.B)
  val results = Reg(Vec(2, Vec(2, Vec(8, SInt(48.W)))))
  val tags = Reg(Vec(2, UInt(5.W)))
  val clearing = RegInit(false.B); val clearIndex = RegInit(0.U(12.W))
  val biasCleared = RegInit(false.B); val clearDone = RegInit(false.B)
  val bias = withReset(reset.asBool || io.abort) { Module(new BiasSramPrefetch) }
  io.clearReady := !active && !running && count === 0.U && !clearing &&
    bias.io.clearReady && !io.abort
  val clearFire = io.clearValid && io.clearReady
  val engines = Seq.fill(2)(withReset(reset.asBool || clearFire || io.abort) {
    Module(new DotProductEngine)
  })
  val xs = Seq.fill(2, 2)(Module(new XRowBuffer))
  private val weights = Module(new DmaWeightBankArray)
  val selectedGroup = produced(4, 0)
  val biasReady = bias.io.groupValid && bias.io.groupTag === selectedGroup
  val launch = active && !running && produced < 32.U && count < 2.U && biasReady && !io.abort
  val enqueue = active && running && engines.head.io.done && !io.abort
  val pop = io.outPop && io.outValid
  val retirePair = pop && (!second || outputSecond)
  val takeBias = RegNext(launch, false.B)
  val nextBiasDemand = active && running && !takeBias && produced < 31.U
  bias.io.computeActive := active && !io.abort
  bias.io.invalidate := false.B
  bias.io.clearValid := clearFire
  bias.io.hostValid := io.biasHostValid && !active && !clearing && !clearFire && !io.abort
  bias.io.hostRead := false.B
  bias.io.hostAddr := io.biasHostAddr; bias.io.hostData := io.biasHostData
  bias.io.hostMask := 31.U; bias.io.rspReady := true.B
  io.biasHostReady := bias.io.hostReady && !active && !clearing && !clearFire && !io.abort
  io.biasRspValid := bias.io.rspValid && !io.abort
  io.biasRspError := bias.io.rspError
  bias.io.groupReqValid := ((active && !running && produced < 32.U) || nextBiasDemand) && !io.abort
  bias.io.groupReqTag := Mux(nextBiasDemand, (produced + 1.U)(4, 0), selectedGroup)
  bias.io.groupTake := takeBias && !io.abort
  when(takeBias && !io.abort) { assert(biasReady, "Pair INIT must consume its own bias group") }
  for (row <- 0 until 2) {
    val engine = engines(row)
    engine.io.start := launch && (if (row == 0) true.B else second)
    engine.io.bias := bias.io.groupBias; engine.io.w := weights.io.rdata
    for (set <- 0 until 2) {
      val x = xs(set)(row)
      x.io.wen := !io.abort && ((io.xLoadWen && io.xLoadSet === (set == 1).B &&
        io.xLoadRow === (row == 1).B && !clearing && (!active || io.xLoadSet =/= runSet)) ||
        (clearing && clearIndex < 64.U))
      x.io.waddr := Mux(clearing, clearIndex(5, 0), io.xLoadAddr)
      x.io.wdata := Mux(clearing, 0.S, io.xLoadData)
      x.io.raddr := engine.io.k
    }
    engine.io.x := Mux(runSet, xs(1)(row).io.rdata, xs(0)(row).io.rdata)
  }
  weights.io.loadWen := io.wLoadWen && !active && !clearing && !io.abort
  weights.io.loadBank := io.wLoadBank; weights.io.loadAddr := io.wLoadAddr
  weights.io.loadData := io.wLoadData
  weights.io.loadPacked := io.wLoadPacked; weights.io.loadDataHi := io.wLoadDataHi
  when(io.wLoadWen && io.wLoadPacked && !io.abort) {
    assert(!io.wLoadBank(0), "Packed W load must select an even low bank")
  }
  weights.io.clearWen := clearing && clearIndex < 2048.U && !io.abort
  weights.io.clearAddr := clearIndex(10, 0)
  weights.io.ren := engines.head.io.weightRen && !clearing && !io.abort
  weights.io.raddr := Cat(selectedGroup, engines.head.io.weightReadK)
  when(running && second && !io.abort) {
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
    produced := 0.U; retired := 0.U; count := 0.U; head := false.B; tail := false.B
  }.elsewhen(clearing) {
    when(bias.io.clearDone) { biasCleared := true.B }
    when(clearIndex < 2048.U) { clearIndex := clearIndex + 1.U }
    when(clearIndex === 2048.U && (biasCleared || bias.io.clearDone)) {
      clearing := false.B; clearDone := true.B
    }
  }
  io.done := false.B
  when(io.abort) {
    active := false.B; running := false.B; count := 0.U
    produced := 0.U; retired := 0.U; head := false.B; tail := false.B
    second := false.B; outputSecond := false.B
    clearing := false.B; clearDone := false.B; biasCleared := false.B
  }.elsewhen(io.start) {
    assert(!active && !running && count === 0.U && !clearing && !clearFire && bias.io.hostIdle)
    assert(!(io.xLoadWen && io.xLoadSet === io.xRunSet), "Start must own a completed X set")
    active := true.B; running := false.B; produced := 0.U; retired := 0.U
    count := 0.U; head := false.B; tail := false.B; second := io.secondRow
    runSet := io.xRunSet; outputSecond := false.B
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
  when(active && !io.abort) {
    assert(produced - retired === count)
    assert(!io.wLoadWen && !io.biasHostValid && !io.clearValid)
    when(io.xLoadWen) { assert(io.xLoadSet =/= runSet, "DMA wrote the active X set") }
  }
  when(io.outPop && !io.abort) { assert(io.outValid, "POP without an owned result") }
  io.active := active && !io.abort; io.clearing := clearing && !io.abort
  io.clearDone := clearDone && !io.abort
  io.outValid := active && count =/= 0.U && !io.abort
  io.outGroup := tags(head); io.outSecond := outputSecond
  io.outResult := results(head)(outputSecond)
  io.computeStart := launch; io.weightRead := weights.io.ren
  io.macStep := running && RegNext(weights.io.ren, false.B) && !io.abort
  io.fifoFullWait := active && !running && produced < 32.U && count === 2.U && !io.abort
  io.clearWeightWrite := weights.io.clearWen
  io.clearXWrite := clearing && clearIndex < 64.U && !io.abort
}
