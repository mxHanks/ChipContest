from pathlib import Path
import json,random
out=Path('/home/mxhanks/.codex/worktrees/s3-y32-writeback/ChipContest/build/postflow-20261108')
# Bilinear products attain extrema on the four signed16 domain corners.
xs=[-(1<<15),(1<<15)-1];bs=[-(1<<39),(1<<39)-1]
products=[x*w for x in xs for w in xs]
pmin,pmax=min(products),max(products)
prefix=[dict(terms=k,minimum=bs[0]+k*pmin,maximum=bs[1]+k*pmax) for k in range(65)]
assert all(-(1<<40)<=r['minimum']<=r['maximum']<(1<<40) for r in prefix)
assert prefix[-1]['minimum']<-(1<<39) and prefix[-1]['maximum']>=(1<<39)
# Exercise exact sign extension after bounded 41-bit additions on varied traces.
rng=random.Random(20261108);traces=256
for _ in range(traces):
 acc=rng.randrange(-(1<<39),1<<39);wide=acc
 for k in range(64):
  x,w=[rng.randrange(-(1<<15),1<<15) for _ in range(2)]
  wide+=x*w
  raw=(acc+x*w)&((1<<41)-1)
  acc=raw-(1<<41) if raw&(1<<40) else raw
  assert acc==wide
proof={'status':'EXACT_DOMAIN_BOUND_VERIFIED','scope':'Mathematical interval bound for all legal operands and prefix lengths; random traces are supplemental, not exhaustive proof','product_extrema':{'min':pmin,'max':pmax},'prefix_bounds':prefix,'minimum_signed_accumulator_bits':41,'bits40_rejected':True,'bits48_external_interface_can_be_preserved_by':'sign extension','supplemental_random_traces':traces,'area_timing_energy':'NOT_MEASURED','raw_mac_register_bits_8PE':{'48bit':8*48,'41bit':8*41}}
(out/'accumulator-width-assessment.json').write_text(json.dumps(proof,indent=2)+'\n')
M,K,N=99,64,256
mapping={'status':'ANALYTIC_ARCHITECTURE_ASSESSMENT_NOT_RTL_SIMULATION','shape':{'M':M,'K':K,'N':N},'one_row_16_columns':{'physical_mac_cycles':M*(N//16)*K,'weight_sram_16bit_reads':M*N*K,'logical_bias_values':M*N,'contiguous_Y_words_per_pair':16},'two_rows_8_columns':{'row_pairs':(M+1)//2,'physical_mac_cycles_if_tail_row_masked':((M+1)//2)*(N//8)*K,'weight_sram_16bit_reads':((M+1)//2)*N*K,'logical_bias_values':((M+1)//2)*N,'additional_X_row_raw_bytes':K*2,'Y_stride_between_rows_bytes':N*4,'optional_second_row_output_buffer_raw_bytes':N*4,'tail_row_policy':'mask absent row99; preserve only99 real output rows'},'decision':'DEFER until batch16 and bias pipeline identify residual bandwidth/overlap limit. Requires strided row-aware result ownership and output scheduling; no measured speedup claim.'}
(out/'row-mapping-assessment.json').write_text(json.dumps(mapping,indent=2)+'\n')
print('BOUND_PASS full_domain signed41; signed40 insufficient; ROW_MAPPING_MODEL_SAVED')
