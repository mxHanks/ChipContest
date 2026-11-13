#!/usr/bin/env python3
"""Cycle-level traffic feasibility model for the B41 preliminary submission.

The model deliberately counts the complete task path:

    CPU/entry load -> shared SRAM -> DMA reread -> compute/writeback -> clear

It is a traffic/service-rate model, not a replacement for RTL/VCS/STA.  All
inputs are explicit so that the report can be regenerated without credentials
or a remote server.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


FREQUENCY_HZ = 150_000_000
BASELINE_MEASURED_CYCLES = 297_391
BASELINE_STAGE_CYCLES = {
    "source_load": 126_331,
    "dma_read_compute_writeback": 169_965,
    "clear": 1_028,
}
BASELINE_STAGE_SUM = sum(BASELINE_STAGE_CYCLES.values())
BASELINE_OTHER_CYCLES = BASELINE_MEASURED_CYCLES - BASELINE_STAGE_SUM


@dataclass(frozen=True)
class Traffic:
    x_words: int
    w_words: int
    bias_words: int
    y_words: int

    @property
    def source_load_words(self) -> int:
        return self.x_words + self.w_words + self.bias_words

    @property
    def dma_read_words(self) -> int:
        return self.source_load_words

    @property
    def total_words(self) -> int:
        return self.source_load_words + self.dma_read_words + self.y_words

    @property
    def bytes_moved(self) -> int:
        return self.total_words * 4

    @property
    def source_load_bytes(self) -> int:
        return self.source_load_words * 4

    @property
    def dma_read_bytes(self) -> int:
        return self.dma_read_words * 4

    @property
    def y_write_bytes(self) -> int:
        return self.y_words * 4


@dataclass(frozen=True)
class Scenario:
    name: str
    service_interval: int
    x_packed16: bool
    residual_cycles: int = 0


def traffic_for(x_packed16: bool) -> Traffic:
    # Current layout stores one INT16 X value per 32-bit word.  packed16
    # stores two INT16 values per 32-bit word and therefore removes 3168
    # writes and 3168 rereads per task.
    x_words = 3_168 if x_packed16 else 6_336
    return Traffic(x_words=x_words, w_words=8_192, bias_words=512, y_words=25_344)


def simulate_serial_task(traffic: Traffic, service_interval: int, clear_cycles: int,
                         residual_cycles: int = 0) -> dict:
    """Simulate one ordered shared-bus task at transaction granularity.

    Each accepted request/response pair occupies ``service_interval`` cycles.
    The path is intentionally serialized because this is the conservative
    original-interconnect bound used for the feasibility decision.  The
    residual term represents non-traffic work (CPU mailbox/control, compute
    waits, and other fixed overhead) and is kept separate from the traffic
    floor.
    """
    if service_interval < 1:
        raise ValueError("service_interval must be >= 1")
    if clear_cycles < 0 or residual_cycles < 0:
        raise ValueError("cycle costs must be non-negative")

    cursor = 0
    phases = []
    for name, count in (
        ("source_load", traffic.source_load_words),
        ("dma_reread", traffic.dma_read_words),
        ("y_writeback", traffic.y_words),
    ):
        start = cursor
        cursor += count * service_interval
        phases.append({
            "name": name,
            "transactions": count,
            "start_cycle": start,
            "end_cycle": cursor,
            "cycles": cursor - start,
        })

    start = cursor
    cursor += clear_cycles
    phases.append({
        "name": "clear",
        "transactions": None,
        "start_cycle": start,
        "end_cycle": cursor,
        "cycles": clear_cycles,
    })

    start = cursor
    cursor += residual_cycles
    phases.append({
        "name": "residual_control_compute",
        "transactions": None,
        "start_cycle": start,
        "end_cycle": cursor,
        "cycles": residual_cycles,
    })

    return {
        "cycles": cursor,
        "throughput_tasks_per_s": FREQUENCY_HZ / cursor,
        "latency_us": cursor * 1_000_000 / FREQUENCY_HZ,
        "phases": phases,
    }


def scenario_result(scenario: Scenario, clear_cycles: int = 1_028) -> dict:
    traffic = traffic_for(scenario.x_packed16)
    sim = simulate_serial_task(
        traffic,
        service_interval=scenario.service_interval,
        clear_cycles=clear_cycles,
        residual_cycles=scenario.residual_cycles,
    )
    return {
        "name": scenario.name,
        "service_interval_cycles": scenario.service_interval,
        "x_packed16": scenario.x_packed16,
        "residual_cycles": scenario.residual_cycles,
        "traffic": asdict(traffic),
        "traffic_words": traffic.total_words,
        "traffic_bytes": traffic.bytes_moved,
        **sim,
    }


def required_service_interval(target_tasks_per_s: float, traffic: Traffic,
                              clear_cycles: int = 1_028,
                              residual_cycles: int = 0) -> float:
    budget = FREQUENCY_HZ / target_tasks_per_s
    return (budget - clear_cycles - residual_cycles) / traffic.total_words


def self_check() -> None:
    """Tight regression checks for the omitted-transfer failure mode."""
    current = traffic_for(False)
    packed = traffic_for(True)
    assert current.source_load_words == 15_040
    assert current.dma_read_words == 15_040
    assert current.y_words == 25_344
    assert current.total_words == 55_424
    assert current.bytes_moved == 221_696
    assert packed.total_words == 49_088
    assert current.total_words - packed.total_words == 6_336
    baseline_floor = simulate_serial_task(current, 4, 1_028)
    assert baseline_floor["cycles"] == 222_724
    assert round(baseline_floor["throughput_tasks_per_s"], 2) == 673.48


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="write JSON result to this path")
    args = parser.parse_args()
    self_check()

    dma_residual = BASELINE_STAGE_CYCLES["dma_read_compute_writeback"] - (
        (traffic_for(False).dma_read_words + traffic_for(False).y_words) * 4
    )
    measured_traffic_floor = traffic_for(False).total_words * 4 + 1_028
    measured_residual = BASELINE_MEASURED_CYCLES - measured_traffic_floor

    scenarios = [
        Scenario("one-beat-per-cycle-original-layout", 1, False),
        Scenario("one-beat-per-cycle-packed16-x", 1, True),
        Scenario("frozen-entry-original-interconnect", 4, False),
        Scenario("optimized-entry-original-interconnect", 2, False),
        Scenario("frozen-entry-original-interconnect-packed16-x", 4, True),
        Scenario("optimized-entry-original-interconnect-packed16-x", 2, True),
        Scenario("optimized-entry-with-current-residual-overhead", 2, False,
                 measured_residual),
        Scenario("optimized-entry-packed16-with-current-residual-overhead", 2,
                 True, measured_residual),
    ]

    result = {
        "model": "b41-throughput-feasibility-r2",
        "frequency_hz": FREQUENCY_HZ,
        "workload": {
            "macs_per_task": 1_622_016,
            "outputs_y32_per_task": 25_344,
            "tasks_in_frozen_campaign": 12,
            "outputs_in_frozen_campaign": 304_128,
        },
        "measured_baseline": {
            "cycles_per_task": BASELINE_MEASURED_CYCLES,
            "throughput_tasks_per_s": FREQUENCY_HZ / BASELINE_MEASURED_CYCLES,
            "stage_cycles": BASELINE_STAGE_CYCLES,
            "stage_sum": BASELINE_STAGE_SUM,
            "unclassified_cycles": BASELINE_OTHER_CYCLES,
            "traffic_counts_explanation": {
                "source_load": traffic_for(False).source_load_words,
                "dma_reread": traffic_for(False).dma_read_words,
                "y_writeback": traffic_for(False).y_words,
                "old_40384_count": traffic_for(False).dma_read_words + traffic_for(False).y_words,
                "complete_55424_count": traffic_for(False).total_words,
            },
        },
        "inferred_residuals": {
            "dma_compute_writeback_residual_at_4_cycle_service": dma_residual,
            "all_non_traffic_residual_vs_4_cycle_floor": measured_residual,
            "measured_traffic_floor_at_4_cycle_service": measured_traffic_floor,
            "stage_boundary_residual": BASELINE_OTHER_CYCLES,
        },
        "scenarios": [scenario_result(s) for s in scenarios],
        "required_service_interval_cycles": {
            str(target): {
                "baseline_x_layout": required_service_interval(target, traffic_for(False)),
                "packed16_x_layout": required_service_interval(target, traffic_for(True)),
            }
            for target in (1_000, 1_500, 2_000, 2_706, 3_000)
        },
        "interpretation": {
            "traffic_floor_excludes": [
                "CPU mailbox polling and software control",
                "compute waits not hidden by data movement",
                "extra arbitration latency beyond the selected service interval",
                "STA frequency uncertainty",
            ],
            "official_status": "diagnostic estimate; not an official score",
        },
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
