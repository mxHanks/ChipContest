import chisel3._
import circt.stage.ChiselStage
import dotproduct._
import linear._

object GenerateRTL {

    // 注册可以生成的顶层模块
    private val modules: Map[String, () => RawModule] = Map(
        "MacPE" -> (() => new MacPE),
        "MacPEArray" -> (() => new MacPEArray),
        "MacController" -> (() => new MacController),
        "DotProductEngine" -> (() => new DotProductEngine),
        "LinearComputeCore" -> (() => new LinearComputeCore),
        "LinearLayerEngine" -> (() => new LinearLayerEngine)
    )

    def main(args: Array[String]): Unit = {

        val moduleName = args.headOption.getOrElse("DotProductEngine")

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
                "--lowering-options=disallowLocalVariables,disallowPackedArrays"
            )
        )

        println(s"已生成 $moduleName 的 SystemVerilog")
    }
}
