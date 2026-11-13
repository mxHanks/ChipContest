  # Appended after the byte-identical, native-proven fixed collector load prefix.
  # Bounded observations only: max_paths1/nworst1 per bit and delay type.
  # A tool may return one path per group; keep all headers and the minimum slack.
  # No get_timing_paths or timing_path/port attribute assumptions are needed.
  set io_expected {}
  foreach {name width direction} {
    sysbus_load_cmd_valid 1 input
    sysbus_load_cmd_ready 1 output
    sysbus_load_cmd_addr 32 input
    sysbus_load_cmd_read 1 input
    sysbus_load_cmd_wdata 32 input
    sysbus_load_cmd_wmask 4 input
    sysbus_load_rsp_valid 1 output
    sysbus_load_rsp_ready 1 input
    sysbus_load_rsp_err 1 output
    sysbus_load_rsp_rdata 32 output
  } {
    for {set bit 0} {$bit < $width} {incr bit} {
      set port_name [expr {$width == 1 ? $name : [format {%s[%d]} $name $bit]}]
      dict set io_expected $port_name $direction
    }
  }
  set io_ports [get_ports -quiet sysbus_load*]
  if {[sizeof_collection $io_ports] != 106 ||
      [lsort [get_object_name $io_ports]] ne [lsort [dict keys $io_expected]]} {
    error {actual sysbus_load* port set is not exactly the106 declared loader bits}
  }
  set io_inputs [all_inputs]
  set io_outputs [all_outputs]
  set io_in 0
  set io_out 0
  set io_no_path 0
  set io_numeric 0
  set io_without_slack 0
  set io_unparsed 0
  set io_catalog [open [file join $xu_out required-reports.list] w]
  set io_summary [open [file join $xu_out loader-io-observations.tsv] w]
  puts $io_summary "port\tdirection\tdelay_type\tstatus\treported_path_headers\tnumeric_slack_count\tworst_numeric_slack\tslack_state\tworst_startpoint_header\tworst_endpoint_header\tworst_path_group\tworst_path_type\tinput_external_delay_seen\toutput_external_delay_seen\treport"
  xu_capture host-usage.rpt {report_host_usage -verbose} 1
  xu_capture clocks.rpt {report_clock -attributes} 1
  xu_capture check_timing.rpt {check_timing -verbose} 1
  foreach io_name [lsort [dict keys $io_expected]] {
    set io_port [get_ports -quiet [list $io_name]]
    if {[sizeof_collection $io_port] != 1} {error "loader bit not unique: $io_name"}
    set io_direction [dict get $io_expected $io_name]
    set io_is_in [expr {[sizeof_collection [remove_from_collection $io_port $io_inputs]] == 0}]
    set io_is_out [expr {[sizeof_collection [remove_from_collection $io_port $io_outputs]] == 0}]
    if {$io_direction eq "input" && $io_is_in && !$io_is_out} {
      incr io_in
      set io_selector -from
    } elseif {$io_direction eq "output" && $io_is_out && !$io_is_in} {
      incr io_out
      set io_selector -to
    } else {error "actual port direction differs from sealed top: $io_name"}
    set io_safe [string map {\[ _ \] _} $io_name]
    foreach io_delay {max min} {
      set io_file ${io_safe}-${io_delay}.rpt
      set io_command [list report_timing $io_selector $io_port -delay_type $io_delay \
        -slack_lesser_than 1000000000 -max_paths 1 -nworst 1 \
        -path_type full_clock_expanded -significant_digits 8 -nets -input_pins \
        -transition_time -capacitance]
      if {![xu_capture $io_file $io_command 1]} {error "loader timing report failed: $io_name $io_delay"}
      puts $io_catalog reports/$io_file
      set io_f [open [file join $xu_reports $io_file] r]
      set io_text [read $io_f]; close $io_f
      if {[regexp {(^|\n)[ \t]*(Error:|Fatal:)} $io_text]} {error "native error in loader report: $io_file"}
      set io_count 0
      set io_slack_count 0
      set io_slack {}
      set io_slack_state {}
      set io_start {}
      set io_end {}
      set io_group {}
      set io_type {}
      set io_current_start {}
      set io_current_end {}
      set io_current_group {}
      set io_current_type {}
      foreach io_line [split $io_text \n] {
        if {[regexp {^[ \t]*Startpoint:[ \t]*(.*)$} $io_line -> value]} {
          incr io_count; set io_current_start $value
          set io_current_end {}; set io_current_group {}; set io_current_type {}
        }
        if {[regexp {^[ \t]*Endpoint:[ \t]*(.*)$} $io_line -> value]} {set io_current_end $value}
        if {[regexp {^[ \t]*Path Group:[ \t]*(.*)$} $io_line -> value]} {set io_current_group $value}
        if {[regexp {^[ \t]*Path Type:[ \t]*(.*)$} $io_line -> value]} {set io_current_type $value}
        if {[regexp {^[ \t]*slack[ \t]+\((MET|VIOLATED)\)[ \t]+([-+0-9.eE]+)[ \t]*$} $io_line -> state value]} {
          if {![string is double -strict $value]} {error "invalid slack number: $io_file"}
          incr io_slack_count
          if {$io_slack eq "" || $value < $io_slack} {
            set io_slack $value; set io_slack_state $state
            set io_start $io_current_start; set io_end $io_current_end
            set io_group $io_current_group; set io_type $io_current_type
          }
        }
      }
      if {$io_count > 0 && $io_slack ne ""} {
        set io_status REPORTED_PATHS_WITH_NUMERIC_SLACK; incr io_numeric
        if {$io_slack_count != $io_count} {set io_status PARTIAL_NUMERIC_SLACK_CONTEXTS_REVIEW_REQUIRED}
      } elseif {$io_count > 0} {
        set io_status REPORTED_PATH_WITHOUT_NUMERIC_SLACK; incr io_without_slack
      } elseif {[regexp -nocase {No paths[.]} $io_text]} {
        set io_status NO_PATH_REPORTED; incr io_no_path
      } else {
        set io_status UNPARSED_REPORT_REVIEW_REQUIRED; incr io_unparsed
      }
      foreach value [list $io_start $io_end $io_group $io_type] {
        if {[regexp {[\t\r]} $value]} {error "unexpected tab/CR in path header: $io_file"}
      }
      puts $io_summary [join [list $io_name $io_direction $io_delay $io_status $io_count \
        $io_slack_count $io_slack $io_slack_state $io_start $io_end $io_group $io_type \
        [regexp {input external delay} $io_text] [regexp {output external delay} $io_text] reports/$io_file] \t]
    }
  }
  close $io_catalog
  close $io_summary
  if {$io_in != 71 || $io_out != 35} {error "actual loader direction totals differ: in=$io_in out=$io_out"}
  if {[llength $xu_required_failures]} {error "required observation report commands failed: $xu_required_failures"}
  set io_f [open [file join $xu_out io-status.txt] w]
  puts $io_f "INPUT_BITS=$io_in\nOUTPUT_BITS=$io_out\nPORT_BITS=106\nBOUNDED_REPORTS=212"
  puts $io_f "NUMERIC_SLACK_REPORTS=$io_numeric\nNO_PATH_REPORTS=$io_no_path\nPATH_WITHOUT_NUMERIC_SLACK=$io_without_slack\nUNPARSED_REPORTS=$io_unparsed"
  puts $io_f "MAPPED_V_SHA256=$xu_mapped_sha\nORIGINAL_SDC_SHA256=$xu_sdc_sha\nPT_COMPAT_SDC_SHA256=$xu_sdc_compat_sha"
  puts $io_f {LIMIT=Bounded max_paths1/nworst1 per port/delay; tool may return a path per group. TSV records actual header/numeric counts and minimum returned slack. No all-context, transition-polarity, exception, CDC or complete IO qualification is established. NO_PATH is not a timing pass.}
  puts $io_f {STATUS=READ_ONLY_LOADER_IO_OBSERVATIONS_REVIEW_REQUIRED_NOT_QUALIFIED}
  close $io_f
  set io_f [open [file join $xu_out LOADER_IO_OBSERVATION_COMPLETE_NOT_QUALIFIED.txt] w]
  puts $io_f {Read-only106-bit loader IO report collection completed. This is not STA closure or complete IO/CDC qualification.}
  close $io_f
} xu_reason xu_options]
if {$xu_error} {
  set io_f [open [file join $xu_out LOADER_IO_OBSERVATION_FAILED.txt] w]
  puts $io_f $xu_reason
  if {[dict exists $xu_options -errorinfo]} {puts $io_f [dict get $xu_options -errorinfo]}
  close $io_f
  puts stderr "LOADER_IO_OBSERVATION_FAILED: $xu_reason"
  exit 1
}
puts {LOADER_IO_OBSERVATION_COMPLETE_NOT_QUALIFIED}
exit 0
