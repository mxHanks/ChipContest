package linear

import chisel3._
import chisel3.util._

class LinearSramCachedCoreIO extends LinearCachedCoreIO {
    val cacheWriteReady = Output(Bool())
    val cacheReadEnable = Input(Bool())
    val cacheReadReady = Output(Bool())
    val cacheReadValid = Output(Bool())
}

/** xu independent S1 SRAM candidate, retaining the baseline eight-PE core.
  * Cached START adds exactly two cycles before core START: synchronous SRAM
  * read and tile capture. The tile remains stable throughout engine INIT and
  * compute, independently of subsequent MMIO readback requests.
  */
class LinearSramCachedCore extends Module {
    val io = IO(new LinearSramCachedCoreIO)
    private val core = Module(new LinearComputeCore)
    private val cache = Module(new BiasSramCache)
    private val cached = RegEnable(io.cacheEnable, false.B, io.start)
    private val group = RegEnable(io.group, io.start)

    cache.io.prefetch := io.start && io.cacheEnable
    cache.io.group := io.group
    cache.io.writeEnable := io.cacheWriteEnable
    cache.io.writeAddr := io.cacheWriteAddr
    cache.io.writeData := io.cacheWriteData
    cache.io.writeMask := io.cacheWriteMask
    cache.io.readEnable := io.cacheReadEnable
    cache.io.readAddr := io.cacheReadAddr
    io.cacheWriteReady := cache.io.writeReady
    io.cacheReadReady := cache.io.readReady
    io.cacheReadValid := cache.io.readValid
    io.cacheReadData := cache.io.readData

    core.io.start := (io.start && !io.cacheEnable) || cache.io.prefetchDone
    core.io.group := Mux(cached, group, io.group)
    core.io.bias := Mux(cached, cache.io.bias, io.bias)
    core.io.xLoadWen := io.xLoadWen
    core.io.xLoadAddr := io.xLoadAddr
    core.io.xLoadData := io.xLoadData
    core.io.wLoadWen := io.wLoadWen
    core.io.wLoadBank := io.wLoadBank
    core.io.wLoadAddr := io.wLoadAddr
    core.io.wLoadData := io.wLoadData
    io.done := core.io.done
    io.result := core.io.result
}
