"""Explicit, fail-closed SRAM backend source selection shared by entry points."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'configs/sram-backends.json'
ALIASES={'behavioral':'BEHAVIORAL','blackbox':'BLACKBOX','ff':'FF_FALLBACK','official':'OFFICIAL_MACRO'}
VALUES={'BEHAVIORAL':0,'BLACKBOX':1,'FF_FALLBACK':2,'OFFICIAL_MACRO':3}
INTERFACE={'ports':'1RW','read_latency_cycles':1,'disabled_output':'hold',
           'simultaneous_read_write':'forbidden','payload_reset':False}


def select_backend(mode,purpose,*,root=ROOT,config_path=CONFIG,allow_full_ff=False):
    root=Path(root).resolve();config_path=Path(config_path).resolve()
    config=json.loads(config_path.read_text())
    if (config.get('schema')!='kwt-sram-backends-v1' or
        config.get('top')!='kwt_linear_engine_rowpair_sram' or
        config.get('numeric_contract')!='fixed16_acc48_v1' or
        config.get('logical_bank_count')!=20 or config.get('logical_payload_bits')!=415744 or
        config.get('configured_bits')!=462848 or config.get('interface')!=INTERFACE):
        raise ValueError('SRAM source configuration differs from the validated contract')
    name=ALIASES.get(mode,mode)
    if name not in VALUES or purpose not in ('simulation','synthesis'):
        raise ValueError('unknown SRAM backend or build purpose')
    backend=config['backends'][name]
    if type(backend.get('SRAM_BACKEND')) is not int or backend['SRAM_BACKEND']!=VALUES[name]:
        raise ValueError('SRAM backend parameter/configuration mismatch')
    if (purpose=='simulation' and name=='BLACKBOX') or (purpose=='synthesis' and name=='BEHAVIORAL'):
        raise ValueError('SRAM backend is incompatible with '+purpose)
    if purpose=='synthesis' and name=='FF_FALLBACK' and not allow_full_ff:
        raise ValueError('full-capacity FF synthesis requires explicit opt-in')
    names=list(config['common_sources'])
    if name=='OFFICIAL_MACRO':
        required=('functional_sources','setup_liberty','hold_liberty','power_liberty','area_table')
        if backend.get('status')!='READY' or any(not backend.get(k) for k in required):
            raise FileNotFoundError('official SRAM package/adapter is not available; no fallback permitted')
        names+=backend['functional_sources']
        # Timing/area files are dependencies, not Verilog compilation units.
        technology=[backend[k] for k in required[1:]]
    else:
        names+=backend.get('extra_sources',[])
        technology=[]
    def resolve(names):
        if not isinstance(names,list) or not names or any(not isinstance(n,str) for n in names):
            raise ValueError('SRAM file set must be an explicit nonempty list')
        paths=[]
        for name in names:
            path=(root/name).resolve()
            if not path.is_relative_to(root):raise ValueError('SRAM file escapes project root: '+name)
            if not path.is_file():raise FileNotFoundError('SRAM input is missing: '+name)
            if path in paths:raise ValueError('duplicate SRAM source/dependency: '+name)
            paths.append(path)
        return paths
    sources=resolve(names)
    if any(p.suffix not in ('.sv','.v') for p in sources):raise ValueError('non-Verilog compilation source')
    extra=resolve(technology) if technology else []
    return {'name':name,'value':backend['SRAM_BACKEND'],'sources':sources,
            'dependencies':[config_path,Path(__file__).resolve(),*extra]}
