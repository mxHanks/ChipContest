#!/usr/bin/env python3
import hashlib,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent
out=root/'ready-fenced-task0'; elf=out/'accel_soc'; binary=out/'accel_soc.load.bin'
command=['/usr/bin/riscv64-unknown-elf-objcopy','-O','binary',str(elf),str(binary)]
p=subprocess.run(command,capture_output=True,text=True);assert p.returncode==0,p.stderr
b=binary.read_bytes();ins=[];offset=0
while offset<len(b):
 size=4 if b[offset]&3==3 else 2
 value=int.from_bytes(b[offset:offset+size],'little')
 if size==4 and value&0x7f==0x7b:
  rd=(value>>7)&31;funct3=(value>>12)&7;funct7=value>>25
  assert funct3==7 and funct7==0x24 and rd!=0
  assert b[offset-4:offset]==bytes.fromhex('0f00f00f') and b[offset+4:offset+8]==bytes.fromhex('0f00f00f')
  ins.append(dict(address=hex(0x80000000+offset),word=hex(value),rd=rd,funct3=funct3,funct7=funct7,preceding_fence=True,following_fence=True))
 offset+=size
assert len(ins)==1
r=dict(status='PASS',command=command,native_exit=p.returncode,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),load_sha256=hashlib.sha256(b).hexdigest(),ready_instructions=ins,disassembly='ready-fenced-task0/firmware-disassembly.log')
(root/'checks/ready-binary.json').write_text(json.dumps(r,indent=2)+'\n')
print('PASS: actual ready ELF has one funct7=0x24, real rd, immediate pre/post fences')
