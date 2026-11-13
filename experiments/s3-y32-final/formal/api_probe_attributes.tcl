# Read-only attribute-definition queries. Syntax is from the captured native
# list_attributes/help_attributes manuals; no design or technology library read.
set missing 0
foreach class {cell pin design} {
 puts "XU_FINAL374_FM_API_BEGIN\tattributes\t$class"
 set rc [catch {list_attributes -application -class $class -nosplit} output]
 if {$output ne ""} {puts $output}
 puts "XU_FINAL374_FM_API_END\tattributes\t$class\t1\t$rc"
 if {$rc!=0} {incr missing}
}
foreach pair {{cell full_name} {cell ref_name} {pin full_name} {pin direction}} {
 set class [lindex $pair 0];set attribute [lindex $pair 1]
 set name ${class}.${attribute}
 puts "XU_FINAL374_FM_API_BEGIN\tattribute_help\t$name"
 set rc [catch {help_attributes -verbose $class $attribute} output]
 if {$output ne ""} {puts $output}
 puts "XU_FINAL374_FM_API_END\tattribute_help\t$name\t1\t$rc"
 if {$rc!=0} {incr missing}
}
puts "XU_FINAL374_FM_API_DOCUMENTATION_COLLECTED\tmissing=$missing"
exit 0
