import circt.stage.ChiselStage
import linear.LinearRowPairDmaCore

object GenerateDmaCore {
  def main(args: Array[String]): Unit = {
    val target = args.headOption.getOrElse("generated/LinearRowPairDmaCore")
    ChiselStage.emitSystemVerilogFile(new LinearRowPairDmaCore,
      Array("--target-dir", target), firtoolOpts = Array(
        "--strip-debug-info", "--default-layer-specialization=enable",
        "--lowering-options=disallowLocalVariables,disallowPackedArrays"))
  }
}
