/* CPU64 development candidate; immutable offline config, not a final power-selected configuration. */
#define FFN_MAX_PAUSE_NOPS 32
#define FFN_CLEAR_CONFIG {1000000u, 1000000u, 0u, 0u, 0u, FFN_POLL_TIGHT}
#define FFN_COMPUTE_CONFIG {1000000u, 1000000u, 32u, 32u, 0u, FFN_POLL_FIXED}
