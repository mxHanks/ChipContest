/* CPU64 development candidate; immutable offline config, not a final power-selected configuration. */
#define FFN_MAX_PAUSE_NOPS 64
#define FFN_CLEAR_CONFIG {1000000u, 1000000u, 0u, 0u, 0u, FFN_POLL_TIGHT}
#define FFN_COMPUTE_CONFIG {1000000u, 1000000u, 64u, 64u, 4u, FFN_POLL_PHASED}
