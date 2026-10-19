# Assertion patterns for bypass pipelines

These are intent patterns. Rename signals and choose sampling delays from the actual microarchitecture.

## Stable stalled transaction

```systemverilog
assert property (@(posedge clk) disable iff (!rst_n)
  out_valid && !out_ready |=> out_valid && $stable(out_payload));
```

Include all metadata covered by the ready/valid contract, not only the data field.

## Mutually exclusive disposition

```systemverilog
assert property (@(posedge clk) disable iff (!rst_n)
  accepted |-> $onehot({launch_normal, take_bypass, take_error, take_abort}));
```

If disposition occurs later, track the accepted unit with an ID/occupancy scoreboard instead of using same-cycle implication.

## Bypass suppresses expensive work

```systemverilog
assert property (@(posedge clk) disable iff (!rst_n)
  take_bypass |-> !compute_launch && !memory_request);
```

Use a bounded `until`/scoreboard when suppression must last for the lifetime of a unit.

## Counter delta

```systemverilog
assert property (@(posedge clk) disable iff (!rst_n)
  take_bypass |=> bypass_count == $past(bypass_count) + 1);
```

Account for clear, saturation, and simultaneous events. Avoid `$past` immediately after reset unless guarded.

## Occupancy conservation

Prefer a small testbench scoreboard that increments on enqueue handshake and decrements on dequeue handshake, then compares against DUT occupancy. This handles simultaneous enqueue/dequeue and exposes double-drain bugs more clearly than several local assertions.

## End-to-end equivalence

Instantiate optimized and reference configurations when practical. Feed identical accepted inputs, decouple their output backpressure if necessary with scoreboards, and compare the ordered output transaction stream plus completion/counter contracts. Do not require internal cycle equivalence unless it is part of the specification.

