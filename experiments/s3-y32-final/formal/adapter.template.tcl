# Deliberately unapproved. Fill ONLY from captured native help/man, then bind
# exact bytes and documentation sections in api-contract.json. This file is not
# sourced by prepare.py and cannot accidentally start read/match/verify.
proc final_fm_configure_resources {maximum_cores report_dir} {
  error {UNCONFIRMED_NATIVE_API: configure and report an actual max2core limit}
}
proc final_fm_configure_assumptions {report_dir} {
  error {UNCONFIRMED_NATIVE_API: choose and report actual HDL/undriven/auto_setup policy; no generic unresolved blackboxing}
}
proc final_fm_collect {phase report_dir} {
  error {UNCONFIRMED_NATIVE_API: collect all native reports listed in README; unavailable reports must fail}
}
proc final_fm_assert_boundaries {report_dir expected_count expected_cell} {
  error {UNCONFIRMED_NATIVE_API: inventory both full tops, pair every physical macro and opaque pin, reject unresolved/extra blackboxes}
}
