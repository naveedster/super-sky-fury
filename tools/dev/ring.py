import struct,sys
d=open(sys.argv[1],'rb').read(); n=int(sys.argv[2])
v=[x for x in struct.unpack(f'<{n}H',d[0x10000:0x10000+2*n]) if x!=0x5555]
s=sorted(v)
print("frames",len(v),"max",s[-8:],"p99",s[int(len(s)*.99)],"over250",sum(x>250 for x in v),"over262",sum(x>262 for x in v))
