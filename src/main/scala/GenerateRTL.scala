import chisel3._
import circt.stage.ChiselStage
import dotproduct._
import linear._

object GenerateRTL {

    // 注册可以生成的顶层模块
    private val modules: Map[String, () => RawModule] = Map(
        "MacPE" -> (() => new MacPE),
        // Explicit experiments; the historical names retain 48-bit internals.
        "MacPE40Counterexample" -> (() => new MacPE(accWidth = 40)),
        "MacPE41" -> (() => new MacPE(accWidth = 41)),
        "MacPEArray41" -> (() => new MacPEArray(accWidth = 41)),
        "DotProductEngine41" -> (() => new DotProductEngine(accWidth = 41)),
        "LinearComputeCore41" -> (() => new LinearComputeCore(accWidth = 41)),
        "LinearAutoGroupCore41" -> (() => new LinearAutoGroupCore(accWidth = 41)),
        "LinearRowPairPrototype" -> (() => new LinearRowPairPrototype),
        "MacPEArray" -> (() => new MacPEArray),
        "MacController" -> (() => new MacController),
        "DotProductEngine" -> (() => new DotProductEngine),
        "LinearComputeCore" -> (() => new LinearComputeCore),
        "LinearCachedCore" -> (() => new LinearCachedCore),
        "LinearAutoGroupCore" -> (() => new LinearAutoGroupCore),
        "LinearAutoGroupCoreRegisters" -> (() => new LinearAutoGroupCore(useBiasSram = false)),
        "BiasBankCache" -> (() => new BiasBankCache),
        "BiasSramPrefetch" -> (() => new BiasSramPrefetch),
        "LinearLayerEngine" -> (() => new LinearLayerEngine)
    )

    def main(args: Array[String]): Unit = {

        val moduleName = args.headOption.getOrElse("LinearComputeCore")

        val generator = modules.getOrElse(
            moduleName,
            throw new IllegalArgumentException(
                s"未知模块: $moduleName。可用模块: ${modules.keys.toSeq.sorted.mkString(", ")}"
            )
        )

        ChiselStage.emitSystemVerilogFile(
            generator(),
            Array("--target-dir", s"generated/$moduleName"),
            firtoolOpts = Array(
                "--strip-debug-info",
                // Keep every verification assertion in the emitted modules.
                // Otherwise Chisel 7 emits optional bind layers that plain
                // Icarus/SoC file lists do not automatically enable.
                "--default-layer-specialization=enable",
                "--lowering-options=disallowLocalVariables,disallowPackedArrays"
            )
        )

        println(s"已生成 $moduleName 的 SystemVerilog")
    }
}
