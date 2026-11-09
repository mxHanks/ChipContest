import circt.stage.ChiselStage
import dotproduct.DotProductEngine

object RejectDotProductEngine40 {
  def main(args: Array[String]): Unit = {
    try {
      ChiselStage.emitSystemVerilog(new DotProductEngine(accWidth = 40))
      throw new RuntimeException("40-bit fixed64 engine unexpectedly elaborated")
    } catch {
      case error: IllegalArgumentException =>
        require(error.getMessage.contains("64 signed16 products plus signed40 bias require at least 41 bits"))
        println("ACC40_ENGINE_ELABORATION_REJECTED_PASS")
    }
  }
}
