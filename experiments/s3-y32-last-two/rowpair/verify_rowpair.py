#!/usr/bin/env python3
"""Independently check logs, actual raw48 captures and frozen input/source hashes."""
import argparse,hashlib,json,pathlib,re

def check(ok,msg):
    if not ok:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def words(p):return [int(x,16) for x in p.read_text().split()]
def verify(folder, resolve=lambda path: pathlib.Path(path)):
    folder=pathlib.Path(folder);receipt=json.loads((folder/'receipt.json').read_text())
    check(receipt['schema']=='rowpair_module_campaign_v1','schema')
    check(receipt['source_drift']==[],'source drift')
    for kind in ('sources','inputs'):
        for name,digest in receipt[kind].items():check(sha(resolve(name))==digest,kind+' SHA '+name)
    inputs={pathlib.Path(p).name:resolve(p) for p in receipt['inputs']}
    golden=words(inputs['y.mem']);gold32=words(inputs['y32.mem'])
    check(len(golden)==len(gold32)==25344,'golden size')
    check(len(receipt['commands'])==11,'command count')
    for c in receipt['commands']:check(c['returncode']==0,'command '+c['name'])
    records=[]
    for stall in (0,31,60,80,255):
        for rows in (1,2):
            name=f'rows{rows}-stall{stall}';j=json.loads((folder/(name+'.json')).read_text())
            actual=words(folder/(name+'.json.actual-raw48.mem'))
            actual32=words(folder/(name+'.json.cpp-rne-y32.mem'))
            check(actual==golden,name+' actual raw48')
            check(actual32==gold32,name+' actual C++ RNE Y32')
            check(j['rows']==rows and j['consumer_stall_edges_per_bundle']==stall,name+' config')
            pairs=(99+rows-1)//rows
            check(j['compute_starts']==32*pairs,name+' starts')
            check(j['weight_array_read_requests']==2048*pairs,name+' array reads')
            check(j['weight_16bit_macro_reads']==16384*pairs,name+' macro reads')
            check(j['mac_steps_per_active_engine']==2048*pairs,name+' MAC steps')
            check(j['x_load_cycles']==6336,name+' X load')
            check(j['active_plus_x_load_cycles']==j['active_cycles']+6336,name+' active+X')
            check(j['clear_parameter_x_compute_consume_window_cycles']==j['active_cycles']+6336+18432+16387,name+' full module window')
            for key,n in {'outputs_exact_raw48':25344,'outputs_exact_cpp_rne_y32':25344,
                          'reset_boundaries':3,'reset_recovery_outputs':512,'legal_endpoint_raw48_outputs':512,
                          'public_nonzero_before_clear_outputs':512,'physical_clear_calls':2,
                          'physical_clear_observed_cycles':32774,'physical_clear_weight_writes':32768,
                          'physical_clear_x_writes':256,'post_clear_zero_outputs':512}.items():
                check(j[key]==n,name+' '+key)
            log=(folder/(name+'.log')).read_text()
            check(len(re.findall(r'^ROWPAIR_ACTUAL_MACRO_READ_PASS second_row=[01] W=16384 BIAS=768$',log,re.M))==pairs+4,name+' actual macro-port reads')
            for call,dirty in ((1,0),(2,1)):
                check(f'ROWPAIR_PHYSICAL_CLEAR_PASS call={call} W=16384 BIAS=768 X=128 ACC=16 ENGINE_RESULT=16 FIFO=32 nonzero_prestate={dirty}' in log,name+' physical clear')
            check(f'ROWPAIR_PASS rows={rows} stall={stall}' in log,name+' PASS marker')
            check(not re.search(r'FAIL|Assertion failed|%Error',log),name+' failing log')
            records.append(dict(name=name,result_sha256=sha(folder/(name+'.json')),
                                actual_raw48_sha256=sha(folder/(name+'.json.actual-raw48.mem')),
                                cpp_rne_y32_sha256=sha(folder/(name+'.json.cpp-rne-y32.mem'))))
    return dict(schema='rowpair_module_verify_v1',pass_=True,cases=10,outputs_per_case=25344,
                source_drift=[],records=records,
                scope='Module RTL raw48; C++ Y32 RNE; physical-port clear observer; not SoC timing or formal clear policy')
def main():
    p=argparse.ArgumentParser();p.add_argument('campaign');p.add_argument('--out',type=pathlib.Path);a=p.parse_args()
    result=verify(a.campaign)
    if a.out:a.out.write_text(json.dumps(result,indent=2)+'\n')
    print('ROWPAIR_INDEPENDENT_VERIFY_PASS cases=10 actual_raw48_per_case=25344')
if __name__=='__main__':main()
