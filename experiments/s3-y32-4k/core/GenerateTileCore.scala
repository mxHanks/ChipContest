import circt.stage.ChiselStage
import linear.LinearTileDmaCore

object GenerateTileCore {
  def main(args: Array[String]): Unit = {
    val target = args.headOption.getOrElse("build/parallel4k-20261110/core-generated-r1")
    ChiselStage.emitSystemVerilogFile(new LinearTileDmaCore,
      Array("--target-dir", target), firtoolOpts = Array(
        "--strip-debug-info", "--default-layer-specialization=enable",
        "--lowering-options=disallowLocalVariables,disallowPackedArrays"))
  }
}
