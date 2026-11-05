#!/usr/bin/env python3
"""Negative/identity/escaped-name checks; no simulation qualification."""
import contextlib
import io
import json
from pathlib import Path
import tempfile

import extract_private133 as xu

checks = []


def checked(name, condition):
    if not condition:
        raise AssertionError(name)
    checks.append(name)


refs = xu.load_references()
checked('all60 original private references retained', len(refs) == 60)
checked('all9 PLL controls retained', sum(r['original_macro'] == 'XU_HCLK' for r in refs) == 9)
checked('all3 EXU observations retained', sum(r['original_macro'] == 'EXU' for r in refs) == 3)

text = r'''
module xu_soc_ppa_top (tie);
  input tie;
  block u_soc (.unused(tie));
endmodule
module block (unused);
  input unused;
  wire [31:0] named;
  wire \bank[0][3] , \bank[0][2] , \bank[0][1] , \bank[0][0] ;
  dff \regfile[3].rfno0.rf_dffl ( .qout(named) );
endmodule
module dff (qout);
  output [31:0] qout;
  assign qout = {32{1'bx}};
endmodule
'''
design = xu.parser.modules(text)
scopes = xu.elaborate(design, 'xu_soc_ppa_top')
rf = xu.locate(scopes, 'u_soc.regfile[3].rfno0.rf_dffl.qout', 32)
checked('escaped atomic instance with dots resolved', rf is not None and rf['exact_width'])
checked('physical endpoint port direction retained', rf['direction'] == 'output')
bundle = xu.locate(scopes, 'u_soc.bank[0]', 4)
checked('escaped unpacked-array scalar bundle resolved', bundle['kind'] == 'escaped_scalar_bundle')
checked('scalar bundle MSB order explicit', bundle['bits'][0] == 'u_soc.bank[0][3]' and
        bundle['bits'][-1] == 'u_soc.bank[0][0]')
checked('wrong declared width rejected', xu.locate(scopes, 'u_soc.named', 8)['exact_width'] is False)
checked('absent name stays absent', xu.locate(scopes, 'u_soc.unbound', 1) is None)
checked('unknown constant stays unmodified token', design['dff']['records'][0]['rhs'] ==
        ['{', '32', '{', "1'bx", '}', '}'])
try:
    xu.parser.modules('module bad (); always @(posedge c) q <= d; endmodule')
except ValueError:
    checks.append('behavioral or unknown structural syntax fails closed')
else:
    raise AssertionError('behavioral syntax accepted')

with tempfile.TemporaryDirectory(prefix='xu-private133-check-') as temp:
    temp = Path(temp)
    wrong = temp / 'wrong-mapped.v'
    wrong.write_text(text)
    out = temp / 'must-not-be-created'
    for mechanism in (False, True):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                xu.run(wrong, out, mechanism)
        except ValueError as error:
            checked('wrong netlist rejected before any output ' + str(mechanism),
                    'wrong mapped hash' in str(error) and not out.exists())
        else:
            raise AssertionError('wrong netlist accepted')

record = json.loads((xu.HERE / 'mechanism116-v3/inventory133.json').read_text())
checked('actual116 exact identity and input immutability',
        record['mapped_before'] == record['mapped_after'] and
        record['mapped_before']['sha256'] == xu.MECHANISM_SHA)
checked('actual116 cannot claim S2c target mapping', record['target_mapping_proved'] is False and
        record['status'] == 'OTHER_NETLIST116_PARSER_MECHANISM_ONLY')
checked('static lookups discharge zero original gates', record['private_gates_discharged'] == 0 and
        record['original_private_gates_remaining'] == 60 and record['runtime_adapters_implemented'] == 0)
checked('all public input helper identities frozen before and after',
        record['helper_before'] == record['helper_after'] and
        record['helper_before']['extract_private133.py']['sha256'] == xu.digest(xu.HERE / 'extract_private133.py'))
checked('unrelated116 missing S2c row state remains unbound',
        next(r for r in record['references'] if r['original_path'] == 'row_active')['classification'] == xu.CLASS3)
checked('actual116 rf3 atomic scope mechanism exercised',
        next(r for r in record['references'] if r['original_path'] == 'u_e203_exu_regfile.rf_r')
        ['endpoint_lookups'][0]['width'] == 32)
checked('unbound source expression cannot count as physical reconstruction',
        next(r for r in record['references'] if r['original_path'] == 'row_start_accept')['classification'] == xu.CLASS3)

print(json.dumps(dict(status='PASS_HOST_MECHANISMS_ONLY_NOT_QUALIFIED',
                      count=len(checks), checks=checks), indent=2))
