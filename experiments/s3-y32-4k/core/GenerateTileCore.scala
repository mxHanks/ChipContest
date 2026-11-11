import circt.stage.ChiselStage
import linear.LinearTileDmaCore

object GenerateTileCore {
  def main(args: Array[String]): Unit = {
    val target = args.headOption.getOrElse("build/parallel4k-20261110/core-generated-r1")
    val widths = args.drop(1).map(_.toInt)
    require(widths.isEmpty || widths.length == 3, "Supply ACC/result/FIFO widths together")
    val selected = if (widths.isEmpty) Seq(48, 48, 48) else widths.toSeq
    ChiselStage.emitSystemVerilogFile(new LinearTileDmaCore(selected(0), selected(1), selected(2)),
      Array("--target-dir", target), firtoolOpts = Array(
        "--strip-debug-info", "--default-layer-specialization=enable",
        "--lowering-options=disallowLocalVariables,disallowPackedArrays"))
  }
}
