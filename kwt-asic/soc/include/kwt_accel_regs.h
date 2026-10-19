#ifndef KWT_ACCEL_REGS_H
#define KWT_ACCEL_REGS_H

#include <stdint.h>

#define KWT_ACCEL_BASE       UINT32_C(0x10042000)
#define KWT_ACCEL_ID         UINT32_C(0x4b575431)
#define KWT_REG_ID           UINT32_C(0x000)
#define KWT_REG_STATUS       UINT32_C(0x004)
#define KWT_REG_CONTROL      UINT32_C(0x008)
#define KWT_REG_ERROR        UINT32_C(0x00c)
#define KWT_REG_CORE_CYCLES  UINT32_C(0x010)
#define KWT_REG_OUTPUT_COUNT UINT32_C(0x014)
#define KWT_REG_WINDOW_CYCLES UINT32_C(0x018)
#define KWT_REG_LOAD_KIND    UINT32_C(0x020)
#define KWT_REG_LOAD_ADDR    UINT32_C(0x024)
#define KWT_REG_LOAD_DATA_LO UINT32_C(0x028)
#define KWT_REG_LOAD_DATA_HI UINT32_C(0x02c)
#define KWT_REG_LOAD_COMMIT  UINT32_C(0x030)
#define KWT_REG_Y_LO         UINT32_C(0x040)
#define KWT_REG_Y_HI         UINT32_C(0x044)
#define KWT_REG_Y_INDEX      UINT32_C(0x048)

#define KWT_STATUS_BUSY           (UINT32_C(1) << 0)
#define KWT_STATUS_LOAD_READY     (UINT32_C(1) << 1)
#define KWT_STATUS_START_READY    (UINT32_C(1) << 2)
#define KWT_STATUS_Y_VALID        (UINT32_C(1) << 3)
#define KWT_STATUS_Y_LO_LATCHED   (UINT32_C(1) << 4)
#define KWT_STATUS_CORE_DONE      (UINT32_C(1) << 5)
#define KWT_STATUS_SOFTWARE_DONE  (UINT32_C(1) << 6)
#define KWT_STATUS_CORE_ERROR     (UINT32_C(1) << 7)
#define KWT_STATUS_PROTOCOL_ERROR (UINT32_C(1) << 8)
#define KWT_STATUS_TASK_STARTED   (UINT32_C(1) << 9)
#define KWT_STATUS_WINDOW_ACTIVE  (UINT32_C(1) << 10)
#define KWT_Y_INDEX_MASK          UINT32_C(0x00007fff)
#define KWT_Y_LAST                UINT32_C(0x80000000)

/* Write exactly one action value, using an aligned full 32-bit store. */
#define KWT_CONTROL_START         UINT32_C(1)
#define KWT_CONTROL_WRITEBACK_ACK  UINT32_C(2)
#define KWT_CONTROL_ABORT_RESET   UINT32_C(4)
#define KWT_LOAD_COMMIT_WORD      UINT32_C(1)
#define KWT_LOAD_X                UINT32_C(0)
#define KWT_LOAD_W                UINT32_C(1)
#define KWT_LOAD_BIAS             UINT32_C(2)
#define KWT_X_COUNT               UINT32_C(6336)
#define KWT_W_COUNT               UINT32_C(16384)
#define KWT_BIAS_COUNT            UINT32_C(256)
#define KWT_Y_COUNT               UINT32_C(25344)

/* ERROR[7:0] records the latest protocol error; ERROR[16] mirrors core error.
 * Protocol errors are sticky diagnostics and clear on ABORT_RESET or rst_n.
 */
#define KWT_ERROR_NONE            UINT32_C(0)
#define KWT_ERROR_ADDRESS         UINT32_C(1)
#define KWT_ERROR_ACCESS          UINT32_C(2)
#define KWT_ERROR_MASK            UINT32_C(3)
#define KWT_ERROR_VALUE           UINT32_C(4)
#define KWT_ERROR_STATE           UINT32_C(5)
#define KWT_ERROR_LOAD_RANGE      UINT32_C(6)
#define KWT_ERROR_LOAD_SEQUENCE   UINT32_C(7)
#define KWT_ERROR_LOAD_INCOMPLETE UINT32_C(8)
#define KWT_ERROR_OUTPUT_EMPTY    UINT32_C(9)
#define KWT_ERROR_OUTPUT_ORDER    UINT32_C(10)
#define KWT_ERROR_WRITEBACK       UINT32_C(11)

/* X/W use their raw uint16_t payload in DATA_LO[15:0], upper bits zero.
 * Bias uses raw two's-complement 40 bits: LO[31:0], HI[7:0], upper bits zero.
 * Set KIND and ADDR once per tensor. A successful COMMIT auto-increments ADDR
 * and clears both payload-valid bits; every bias needs fresh LO and HI.
 * Read Y_LO before Y_HI. HI response acceptance consumes exactly one word.
 * Write WRITEBACK_ACK only after all output stores have completed externally.
 */

#endif
