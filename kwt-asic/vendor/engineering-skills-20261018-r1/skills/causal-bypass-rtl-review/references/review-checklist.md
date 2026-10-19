# Bypass RTL review checklist

## Predicate and boundaries

- Is eligibility derived from authoritative metadata or from data already accepted by the stage?
- Does it require the complete tile/packet/row to be masked, invalid, or redundant?
- Are diagonal, tail, padding, short row, and non-multiple-dimension cases correct?
- Are signedness, widths, position comparisons, and parameter-derived widths safe at minimum and maximum values?
- Can the predicate change while a stalled transaction is presented?

## Queue and handshake conservation

For each accepted unit, account for exactly one disposition: normal processing, bypass, explicit drop/error, or abort cleanup.

Useful equations include:

```text
accepted = processed + bypassed + explicitly_aborted + in_flight
enqueued - dequeued = occupancy
outputs_expected = outputs_emitted + outputs_pending
```

Check that the implementation increments each term on the corresponding handshake, not merely on `valid` or state entry.

## State and metadata

- FIFO read pointer/dequeue and occupancy;
- row/tile/token coordinates;
- head/group/cluster/epoch identifiers;
- `last`, row commit, packet completion, and output ordering;
- busy/done flags and outstanding counts;
- normal, bypass, error, and abort counters;
- cached operands and accumulator lifecycle.

Look for duplicated updates across bypass and normal branches, and for state that advances only in the expensive datapath's completion state.

## Suppressed work

Verify the bypass actually suppresses the intended actions without suppressing obligations:

- compute launch or IP valid;
- memory request and outstanding credit;
- V/value fetch;
- accumulator/context update;
- downstream payload generation;
- performance counter increments.

An optimization that still launches the expensive work but ignores its output is functionally plausible yet performance-ineffective.

## Stall and recovery

- stable valid payload until ready;
- no dequeue without accepted ownership transfer;
- no combinational ready/valid loop through the new predicate;
- reset leaves occupancy and counters coherent;
- clear/abort drains or invalidates every outstanding unit exactly once;
- mode changes cannot reinterpret an already accepted unit.

## Evidence

Accept functional correctness only with self-checking results tied to the intended sources and parameters. Counter reductions demonstrate activity savings, not output correctness. Timing/resource changes demonstrate implementation effects, not functional equivalence. Board logs require matching BIT/XSA/ELF identity when software participates.

