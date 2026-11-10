package linear

import chisel3._
import chisel3.util._
import dotproduct.DotProductEngine
import memory.Sram1024x16

/** One historical 2048x16 W bank, with independent physical clear of both halves. */
private class TileWeightBank extends Module {
  val io = IO(new Bundle {
    val loadWen = Input(Bool()); val loadAddr = Input(UInt(11.W)); val loadData = Input(SInt(16.W))
    val clearWen = Input(Bool()); val clearAddr = Input(UInt(10.W))
    val ren = Input(Bool()); val raddr = Input(UInt(11.W)); val rdata = Output(SInt(16.W))
  })
  val sram0 = Module(new Sram1024x16)
  val sram1 = Module(new Sram1024x16)
  val address = Mux(io.loadWen, io.loadAddr, io.raddr)
  for ((sram, half) <- Seq(sram0, sram1).zipWithIndex) {
    sram.io.en := io.clearWen || ((io.loadWen || io.ren) && address(10) === (half == 1).B)
    sram.io.isWrite := io.clearWen || io.loadWen
    sram.io.addr := Mux(io.clearWen, io.clearAddr, address(9, 0))
    sram.io.wdata := Mux(io.clearWen, 0.S, io.loadData)
  }
  val delayedSelect = RegNext(io.raddr(10), false.B)
  io.rdata := Mux(delayedSelect, sram1.io.rdata, sram0.io.rdata)
  assert(!(io.ren && (io.loadWen || io.clearWen)), "W read/write ownership overlap")
}

/** Same eight logical banks / sixteen 1024x16 macros. Four bank writes per W64 beat. */
private class TileWeightBankArray extends Module {
  val io = IO(new Bundle {
    val loadWen = Input(Bool()); val loadBank = Input(UInt(3.W))
    val loadAddr = Input(UInt(11.W)); val loadData = Input(Vec(4, SInt(16.W)))
    val clearWen = Input(Bool()); val clearAddr = Input(UInt(10.W))
    val ren = Input(Bool()); val raddr = Input(UInt(11.W)); val rdata = Output(Vec(8, SInt(16.W)))
  })
  private val banks = Seq.fill(8)(Module(new TileWeightBank))
  for (i <- 0 until 8) {
    val bank = banks(i)
    bank.io.loadWen := io.loadWen && io.loadBank === ((i / 4) * 4).U
    bank.io.loadAddr := io.loadAddr; bank.io.loadData := io.loadData(i % 4)
    bank.io.clearWen := io.clearWen; bank.io.clearAddr := io.clearAddr
    bank.io.ren := io.ren; bank.io.raddr := io.raddr; io.rdata(i) := bank.io.rdata
  }
  when(io.loadWen) { assert(io.loadBank === 0.U || io.loadBank === 4.U, "W64 base bank must be 0 or 4") }
}

/** Register X row, split even/odd so a public packed write updates two entries. */
private class TileXRowBuffer extends Module {
  val io = IO(new Bundle {
    val wen = Input(Bool()); val waddr = Input(UInt(6.W)); val wdata = Input(SInt(16.W))
    val packed = Input(Bool()); val wdataHi = Input(SInt(16.W))
    val raddr = Input(UInt(6.W)); val rdata = Output(SInt(16.W))
  })
  val even = Reg(Vec(32, SInt(16.W)))
  val odd = Reg(Vec(32, SInt(16.W)))
  when(io.wen) {
    when(!io.waddr(0)) {
      even(io.waddr(5, 1)) := io.wdata
      when(io.packed) { odd(io.waddr(5, 1)) := io.wdataHi }
    }.otherwise { odd(io.waddr(5, 1)) := io.wdata }
    when(io.packed) { assert(!io.waddr(0), "Packed X write must start at even k") }
  }
  io.rdata := Mux(io.raddr(0), odd(io.raddr(5, 1)), even(io.raddr(5, 1)))
}

/** Eight rows x eight columns; one shared W/bias copy, exact original 48-bit engines.
  * validRows=1..8 is captured at START; the 99-row tail uses three rows.
  * Two complete output-column tiles remain owned until every valid row is popped.
  */
class LinearTileDmaCore extends Module {
  val io = IO(new Bundle {
    val start = Input(Bool()); val validRows = Input(UInt(4.W)); val abort = Input(Bool())
    val active = Output(Bool()); val done = Output(Bool())
    val xLoadWen = Input(Bool()); val xLoadRow = Input(UInt(3.W))
    val xLoadSet = Input(Bool()); val xRunSet = Input(Bool())
    val xLoadAddr = Input(UInt(6.W)); val xLoadData = Input(SInt(16.W))
    val xLoadPacked = Input(Bool()); val xLoadDataHi = Input(SInt(16.W))
    val wLoadWen = Input(Bool()); val wLoadBank = Input(UInt(3.W))
    val wLoadAddr = Input(UInt(11.W)); val wLoadData = Input(Vec(4, SInt(16.W)))
    val biasHostValid = Input(Bool()); val biasHostReady = Output(Bool())
    val biasHostAddr = Input(UInt(8.W)); val biasHostData = Input(UInt(40.W))
    val biasRspValid = Output(Bool()); val biasRspError = Output(Bool())
    val clearValid = Input(Bool()); val clearReady = Output(Bool())
    val clearDone = Output(Bool()); val clearing = Output(Bool())
    val outValid = Output(Bool()); val outPop = Input(Bool())
    val outGroup = Output(UInt(5.W)); val outRow = Output(UInt(3.W))
    val outResult = Output(Vec(8, SInt(48.W)))
    val computeStart = Output(Bool()); val weightRead = Output(Bool())
    val macStep = Output(Bool()); val fifoFullWait = Output(Bool())
    val clearWeightWrite = Output(Bool()); val clearXWrite = Output(Bool())
  })
  val active = RegInit(false.B); val running = RegInit(false.B)
  val validRows = RegInit(0.U(4.W)); val runSet = RegInit(false.B)
  val produced = RegInit(0.U(6.W)); val retired = RegInit(0.U(6.W))
  val count = RegInit(0.U(2.W)); val head = RegInit(false.B); val tail = RegInit(false.B)
  val outputRow = RegInit(0.U(3.W))
  val results = Reg(Vec(2, Vec(8, Vec(8, SInt(48.W)))))
  val tags = Reg(Vec(2, UInt(5.W)))
  val clearing = RegInit(false.B); val clearIndex = RegInit(0.U(11.W))
  val biasCleared = RegInit(false.B); val clearDone = RegInit(false.B)
  val bias = withReset(reset.asBool || io.abort) { Module(new DmaBiasSramPrefetch) }
  io.clearReady := !active && !running && count === 0.U && !clearing && bias.io.clearReady && !io.abort
  val clearFire = io.clearValid && io.clearReady
  val engines = Seq.fill(8)(withReset(reset.asBool || clearFire || io.abort) { Module(new DotProductEngine) })
  private val xs = Seq.fill(2, 8)(Module(new TileXRowBuffer))
  private val weights = Module(new TileWeightBankArray)
  val selectedGroup = produced(4, 0)
  val biasReady = bias.io.groupValid && bias.io.groupTag === selectedGroup
  val launch = active && !running && produced < 32.U && count < 2.U && biasReady && !io.abort
  val enqueue = active && running && engines.head.io.done && !io.abort
  val pop = io.outPop && io.outValid
  val retireTile = pop && (outputRow +& 1.U) === validRows
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
  io.biasRspValid := bias.io.rspValid && !io.abort; io.biasRspError := bias.io.rspError
  bias.io.groupReqValid := ((active && !running && produced < 32.U) || nextBiasDemand) && !io.abort
  bias.io.groupReqTag := Mux(nextBiasDemand, (produced + 1.U)(4, 0), selectedGroup)
  bias.io.groupTake := takeBias && !io.abort
  when(takeBias && !io.abort) { assert(biasReady, "Tile INIT must consume its own bias group") }
  for (row <- 0 until 8) {
    val engine = engines(row)
    engine.io.start := launch && row.U < validRows
    engine.io.bias := bias.io.groupBias; engine.io.w := weights.io.rdata
    for (set <- 0 until 2) {
      val x = xs(set)(row)
      x.io.wen := !io.abort && ((io.xLoadWen && io.xLoadSet === (set == 1).B &&
        io.xLoadRow === row.U && !clearing && (!active || io.xLoadSet =/= runSet)) ||
        (clearing && clearIndex < 64.U))
      x.io.waddr := Mux(clearing, clearIndex(5, 0), io.xLoadAddr)
      x.io.wdata := Mux(clearing, 0.S, io.xLoadData)
      x.io.packed := !clearing && io.xLoadPacked
      x.io.wdataHi := Mux(clearing, 0.S, io.xLoadDataHi)
      x.io.raddr := engine.io.k
    }
    engine.io.x := Mux(runSet, xs(1)(row).io.rdata, xs(0)(row).io.rdata)
    when(running && row.U < validRows && !io.abort) {
      assert(engines(0).io.k === engine.io.k)
      assert(engines(0).io.weightRen === engine.io.weightRen)
      assert(engines(0).io.weightReadK === engine.io.weightReadK)
      assert(engines(0).io.done === engine.io.done)
    }
  }
  weights.io.loadWen := io.wLoadWen && !active && !clearing && !clearFire && !io.abort
  weights.io.loadBank := io.wLoadBank; weights.io.loadAddr := io.wLoadAddr; weights.io.loadData := io.wLoadData
  weights.io.clearWen := clearing && clearIndex < 1024.U && !io.abort
  weights.io.clearAddr := clearIndex(9, 0)
  weights.io.ren := engines.head.io.weightRen && !clearing && !io.abort
  weights.io.raddr := Cat(selectedGroup, engines.head.io.weightReadK)
  clearDone := false.B
  when(clearFire) {
    clearing := true.B; clearIndex := 0.U; biasCleared := false.B
    results.foreach(_.foreach(_.foreach(_ := 0.S))); tags.foreach(_ := 0.U)
    outputRow := 0.U; validRows := 0.U; produced := 0.U; retired := 0.U
    count := 0.U; head := false.B; tail := false.B
  }.elsewhen(clearing) {
    when(bias.io.clearDone) { biasCleared := true.B }
    when(clearIndex < 1024.U) { clearIndex := clearIndex + 1.U }
    when(clearIndex === 1024.U && (biasCleared || bias.io.clearDone)) {
      clearing := false.B; clearDone := true.B
    }
  }
  io.done := false.B
  when(io.abort) {
    active := false.B; running := false.B; count := 0.U
    produced := 0.U; retired := 0.U; head := false.B; tail := false.B
    validRows := 0.U; outputRow := 0.U
    clearing := false.B; clearDone := false.B; biasCleared := false.B
  }.elsewhen(io.start) {
    assert(!active && !running && count === 0.U && !clearing && !clearFire && bias.io.hostIdle)
    assert(io.validRows >= 1.U && io.validRows <= 8.U, "START needs 1..8 valid rows")
    assert(!(io.xLoadWen && io.xLoadSet === io.xRunSet), "Start must own a completed X set")
    active := true.B; running := false.B; produced := 0.U; retired := 0.U
    count := 0.U; head := false.B; tail := false.B
    validRows := io.validRows; runSet := io.xRunSet; outputRow := 0.U
  }.otherwise {
    when(launch) { running := true.B }
    when(enqueue) {
      assert(count < 2.U)
      for (row <- 0 until 8) results(tail)(row) := engines(row).io.result
      tags(tail) := selectedGroup; tail := !tail
      produced := produced + 1.U; running := false.B
    }
    when(pop) {
      when(retireTile) { outputRow := 0.U; head := !head; retired := retired + 1.U }
      .otherwise { outputRow := outputRow + 1.U }
    }
    when(retireTile && retired === 31.U) { active := false.B; io.done := true.B }
    when(enqueue =/= retireTile) { count := Mux(enqueue, count + 1.U, count - 1.U) }
  }
  assert(count <= 2.U)
  when(active && !io.abort) {
    assert(validRows >= 1.U && validRows <= 8.U)
    assert(produced - retired === count)
    assert(!io.wLoadWen && !io.biasHostValid && !io.clearValid)
    when(io.xLoadWen) { assert(io.xLoadSet =/= runSet, "DMA wrote the active X set") }
    when(io.outValid) { assert(outputRow < validRows) }
  }
  when(io.outPop && !io.abort) { assert(io.outValid, "POP without an owned tile row") }
  io.active := active && !io.abort; io.clearing := clearing && !io.abort
  io.clearDone := clearDone && !io.abort
  io.outValid := active && count =/= 0.U && !io.abort
  io.outGroup := tags(head); io.outRow := outputRow; io.outResult := results(head)(outputRow)
  io.computeStart := launch; io.weightRead := weights.io.ren
  io.macStep := running && RegNext(weights.io.ren, false.B) && !io.abort
  io.fifoFullWait := active && !running && produced < 32.U && count === 2.U && !io.abort
  io.clearWeightWrite := weights.io.clearWen
  io.clearXWrite := clearing && clearIndex < 64.U && !io.abort
}
