package linear

/** Separate the DMA-specialized generated interface from the legacy core.
  * Both use the same implementation, with their own live generated ports.
  */
class DmaBiasSramPrefetch extends BiasSramPrefetch {
  override def desiredName: String = "DmaBiasSramPrefetch"
}
