package linear

import chisel3._

class LinearCachedCoreIO extends LinearComputeCoreIO {
    val cacheEnable = Input(Bool())
    val cacheWriteEnable = Input(Bool())
    val cacheWriteAddr = Input(UInt(8.W))
    val cacheWriteData = Input(UInt(40.W))
    val cacheWriteMask = Input(UInt(5.W))
    val cacheReadAddr = Input(UInt(8.W))
    val cacheReadData = Output(UInt(40.W))
}

/** xu optional full-bias cache around the unchanged eight-PE compute core. */
class LinearCachedCore extends Module {
    val io = IO(new LinearCachedCoreIO)
    private val core = Module(new LinearComputeCore)
    private val biasCache = Module(new BiasBankCache)

    core.io.start := io.start
    core.io.group := io.group
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
    biasCache.io.group := io.group
    core.io.bias := Mux(io.cacheEnable, biasCache.io.bias, io.bias)

    io.cacheReadData := biasCache.io.readData
    io.done := core.io.done
    io.result := core.io.result
}
