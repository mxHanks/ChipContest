from pathlib import Path
p=Path('build/packed-clear-20261109/packed_clear_compare.py')
s=p.read_text();s=s.replace('Read-only strict stream32 -> ready32 comparison of frozen campaign evidence.','Read-only strict READY scalar -> READY packed-MMIO clear comparison.')
s=s.replace('Only the fixed eight-PE stream32 and optional ready32 transports are accepted.','Only the fixed eight-PE READY payload, scalar baseline and packed clear are accepted.')
s=s.replace("VERIFIER_ORIGIN_SHA256 = '70432692d99bd15ac214e925f97626523d3c60ef4977705fe19b537943bfda9e'", "VERIFIER_ORIGIN_SHA256 = '"+__import__('hashlib').sha256(Path('build/ready-20261109/ready_compare.py').read_bytes()).hexdigest()+"'")
s=s.replace("BASELINE_RESULT_SHA256 = '6185e3531796b2b04d09471ecbd318ecd0d4c146a18fe724a1baf8f5bae5b3d4'", "BASELINE_RESULT_SHA256 = '0e57d26b7493cfc8a98846346bb5183b5d6132d089000782972adfe199a58a28'")
s=s.replace("BASELINE_SOURCES_SHA256 = 'e8b732b49a6682cf168adc28954e7c5577e4de6b03233f7266cda35198d4aab2'", "BASELINE_SOURCES_SHA256 = '72995228ff13f91112dc148c059dd873838a912e53a95f95b6857106d5f7f3f9'")
a=s.index('PROFILES = {');b=s.index('\n\ndef profile_arguments',a)
s=s[:a]+'''PROFILES = {
    name: dict(transport='ready32', schedule=READY_SCHEDULE,
        clear_profile=clear_profile, helper=helper,
        requests=99, extra_macro='-DXU_NICE_DRAINN=1', extra_selector='+NICE_STREAM=1',
        pes=8, groups=3168, fires=202752)
    for name,clear_profile,helper in (
        ('ready32-scalar','scalar','tools/ppa/s3_task_clear_protocol.py'),
        ('ready32-packed','packed16-mmio','tools/ppa/s3_task_packed_clear_protocol.py'))}
PE8_CORE_SHA = 'ebc9c411a6318000369f6c466381767a469bb9d33454e4c955df713c728f9ab4'
NEW_HELPER = 'tools/ppa/s3_task_packed_clear_protocol.py'
ALLOWED_SOURCE_CHANGES = frozenset(('campaign.py', NEW_HELPER))
REQUIRED_SOURCE_CHANGES = ALLOWED_SOURCE_CHANGES
BASELINE_CAMPAIGN_SHA = '9d04abeb87ed1d0d8da1870f8faf2e11c9c116a9b5c3f63019ae818b380f0f2f'
''' +s[b:]
# clear recipe and reconstruction
old="""    require(recipe['frozen_main_sha256'] == sources['tests/e203/firmware/main.c'] and
            recipe['helper_sha256'] == sources['tools/ppa/s3_task_clear_protocol.py'],
            'clear recipe main/helper identity differs from source pins')"""
new="""    require(recipe['frozen_main_sha256'] == sources['tests/e203/firmware/main.c'] and
            recipe['helper_sha256'] == sources[profile['helper']],
            'clear recipe main/selected helper identity differs from source pins')
    require(args.get('clear_profile','scalar') == profile['clear_profile'], 'clear-profile argument differs')
    if profile['clear_profile']=='packed16-mmio':
        for document in (report,plan):
            require(document.get('clear_profile')==profile['clear_profile'] and
                    document.get('clear_helper_source_path')==profile['helper'] and
                    document.get('clear_helper_sha256')==sources[profile['helper']],
                    'packed selected helper identity is missing/different')
        require(recipe.get('clear_profile')==profile['clear_profile'] and
                recipe.get('helper_source_path')==profile['helper'], 'packed clear recipe selector differs')
    else:
        require('clear_profile' not in args and 'clear_profile' not in report and
                'clear_profile' not in recipe, 'fixed historical scalar schema differs')
    require(recipe['policy']=='REVIEW_PENDING' and recipe['fifo_payload_physical_zero']=='UNPROVEN' and
            report['cache_policy']=='REVIEW_PENDING' and report['fifo_payload_physical_zero']=='UNPROVEN',
            'pending clear policy or FIFO UNPROVEN cannot be promoted by this experiment')"""
assert old in s;s=s.replace(old,new)
old="""    clear_c_identity = generated_clear_c_identity(generated_c, old_out)
    artifact(root, 'tb.sv', recipe['generated_tb_sha256'])"""
new="""    clear_c_identity = generated_clear_c_identity(generated_c, old_out)
    generated_tb = artifact(root, 'tb.sv', recipe['generated_tb_sha256'])
    regeneration = verify_clear_generation(root, old_out, sources, profile, recipe,
                                           generated_c, generated_tb, args)"""
assert old in s;s=s.replace(old,new)
# clear checks replacement
old="""        require(clear['commands'] == clear['responses'] and clear['nice_idle'] == '1' and
                int(clear['mode_sram']) == int(report['bias_kind'] == 'sram') and
                int(clear['writes']) == (32930 if report['bias_kind'] == 'sram' else 33697),
                'clear protocol differs')"""
new="""        validate_clear_marker(clear, profile['clear_profile'], report['bias_kind'])"""
assert old in s;s=s.replace(old,new)
s=s.replace("    conditions['startup_profile'] = startup_profile", "    conditions['clear_profile'] = profile['clear_profile']\n    conditions['clear_helper_source_path'] = profile['helper']\n    conditions['startup_profile'] = startup_profile")
s=s.replace("                generated_c_sha256=recipe['generated_c_sha256'], generated_clear_c_identity=clear_c_identity,", "                generated_c_sha256=recipe['generated_c_sha256'], generated_clear_c_identity=clear_c_identity,\n                clear_regeneration=regeneration,")
# canonical allowed changes
s=s.replace("    changes = []\n    for step in conditions['commands']:", """    changes = []
    require(conditions['clear_profile']==profile['clear_profile'] and
            conditions['clear_helper_source_path']==profile['helper'], 'clear identity differs before normalization')
    for key in ('clear_profile','clear_helper_source_path'):
        changes.append(dict(field=key,removed_exact_value=conditions.pop(key)))
    # Work counts are different MMIO strategies; exact helper/recipe and marker
    # checks validate each independently. Physical logical work remains fixed.
    changes.append(dict(field='clear_recipe_configuration.clear_counts',
                        removed_exact_value=conditions['clear_recipe_configuration'].pop('clear_counts')))
    for step in conditions['commands']:""")
# compare
start=s.index("    changed_transport = bprofile['transport'] != aprofile['transport']",s.index('def compare'))
end=s.index('    comparisons=[]',start)
s=s[:start]+'''    require(base['postflow_profile']=='ready32-scalar' and candidate['postflow_profile']=='ready32-packed',
            'only fixed READY scalar -> READY packed-clear comparison is supported')
    require(bprofile['pes']==aprofile['pes']==8 and bprofile['transport']==aprofile['transport']=='ready32',
            'payload architecture/transport differs')
    bc,bn=canonical_conditions(base)
    ac,an=canonical_conditions(candidate)
    require(bc==ac, 'conditions differ beyond explicit clear helper/profile/work-count normalization')
    before_sources,after_sources=base['source_sha256'],candidate['source_sha256']
    observed={key:(before_sources.get(key),after_sources.get(key))
              for key in set(before_sources)|set(after_sources)
              if before_sources.get(key)!=after_sources.get(key)}
    expected={key:tuple(value) for key,value in expected_source_changes.items()}
    require(observed==expected, 'source changes differ from exact reviewed SHA pairs')
    require(set(observed)==REQUIRED_SOURCE_CHANGES, 'only campaign.py and one new helper must change')
    require(observed[NEW_HELPER][0] is None and observed[NEW_HELPER][1] is not None,
            'new packed helper must be the only source addition')
    require(observed['campaign.py'][0]==BASELINE_CAMPAIGN_SHA and observed['campaign.py'][1] is not None,
            'campaign exact source pair differs')
    require(len(before_sources)==170 and len(after_sources)==171, 'fixed source count differs')
    image_checks=dict(baseline=verify_loaded_image(base),candidate=verify_loaded_image(candidate))
    same_firmware=(base['firmware_image_sha256']==candidate['firmware_image_sha256'] and
                   base['firmware_loaded_elf']==candidate['firmware_loaded_elf'])
''' +s[end:]
old="""        timing={'clear_cycles','response_end_cycle','gap_to_source_request'}
        require({k:v for k,v in before['clear'].items() if k not in timing}==
                {k:v for k,v in after['clear'].items() if k not in timing}, 'physical clear work differs')"""
new="""        physical_keys=('mode_sram','w','x','legacy_bias','bias_entries','sram_clear_commands','sram_done',
                       'nice_idle','fifo_payload_physical_zero','policy')
        require({k:before['clear'][k] for k in physical_keys}==
                {k:after['clear'][k] for k in physical_keys}, 'logical physical-clear work/policy differs')
        require(before['payload_cycles']==after['payload_cycles'] and before['phases']==after['phases'] and
                before['bus_counters']==after['bus_counters'] and before['nice']==after['nice'] and
                before['auto']==after['auto'] and before['transport']==after['transport'],
                'frozen READY payload measurement changed')"""
assert old in s;s=s.replace(old,new)
s=s.replace("schema='s3-ready-strict-comparison-v1'", "schema='s3-packed-clear-strict-comparison-v1'")
s=s.replace("loaded_firmware_change_allowed=changed_transport,\n            loaded_firmware_change_reason='exact reviewed optional 0x24 accel.c instruction; only named schedule/macros/selectors normalized'\n                if changed_transport else None,", "loaded_firmware_change_allowed=True,\n            loaded_firmware_change_reason='exact regenerated selected public-MMIO clear helper; frozen main/accel sources unchanged; helper code changes may relocate payload code',")
# replace pins function
start=s.index('def pinned_candidate_sources');end=s.index('\n\ndef project_layers',start)
s=s[:start]+'''def pinned_candidate_sources(base_sources,pairs):
    require(set(pairs)==REQUIRED_SOURCE_CHANGES, 'exact campaign+new-helper source pairs required')
    result=dict(base_sources)
    for key,pair in pairs.items():
        require(isinstance(pair,(list,tuple)) and len(pair)==2, 'invalid exact source pair: '+key)
        before,after=pair
        require(result.get(key)==before and isinstance(after,str) and SHA.fullmatch(after) and before!=after,
                'source pair baseline/candidate SHA differs: '+key)
        require((key==NEW_HELPER)==(before is None), 'only the new helper may be added')
        result[key]=after
    return result
''' +s[end:]
s=s.replace("choices=('stream32-pe8',),default='stream32-pe8'", "choices=('ready32-scalar',),default='ready32-scalar'")
s=s.replace("choices=('ready32-pe8',),default='ready32-pe8'", "choices=('ready32-packed',),default='ready32-packed'")
s=s.replace('fixed 170-source selected-full12 map','fixed 170-source ready-full12 map')
s=s.replace('baseline is not the pinned selected-full12 result','baseline is not the pinned ready-full12 result')
s=s.replace('READY_SAVED_EVIDENCE_COMPARED','PACKED_CLEAR_SAVED_EVIDENCE_COMPARED').replace('READY_COMPARISON_REJECTED','PACKED_CLEAR_COMPARISON_REJECTED')
p.write_text(s)
