# fix ca65 branch range errors: "bxx tgt" -> "inv @rfN ; jmp tgt ; @rfN:" (named, never anonymous)
import re,subprocess,sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
inv={'bcc':'bcs','bcs':'bcc','beq':'bne','bne':'beq','bmi':'bpl','bpl':'bmi','bvc':'bvs','bvs':'bvc'}
n=0
for it in range(40):
    r=subprocess.run(sys.argv[1:],capture_output=True,text=True,cwd=ROOT)
    errs=re.findall(r'(src/\S+)\((\d+)\): Error: Range error',r.stderr+r.stdout)
    if not errs: print("ok"); break
    f,l=errs[0]; l=int(l)
    L=open(os.path.join(ROOT,f)).read().split('\n')
    m=re.match(r'(\s*)(b\w\w)\s+(\S+)(.*)',L[l-1])
    if not m or m.group(2) not in inv: print("cannot fix",f,l,L[l-1]); break
    ind,op,tgt,rest=m.groups()
    lab=f"@rf{abs(hash((f,l,it)))%100000}"
    L[l-1]=f"{ind}{inv[op]} {lab}{rest}\n{ind}jmp {tgt}\n{lab}:"
    open(os.path.join(ROOT,f),'w').write('\n'.join(L)); print("fixed",f,l,op,tgt)
