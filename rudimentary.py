#!/user/bin/env python
'''
process listing of xls files made by ls6500
'''
import os

mainDir = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/LS6500/'
dirList = []

for d in os.listdir(mainDir):
    if not ( 'csv' in d or '.' in d ) : dirList.append(d)

print dirList
lmi = 999999
lma = 0
smi = 999999
sma = 0
zmi = 999999
zma = 0
thres = 200000
L,S,Z = 0,0,0
sizes = []
for d in dirList:
    parent = mainDir + d + '/'
    for f in os.listdir(parent):
        fn = parent + f
        if ('.xls' in fn) and os.path.exists(fn):
            sz =os.path.getsize(fn)
            if sz<100000: print fn,sz
            sizes.append(sz)
            lmi = min(lmi,sz)
            lma = max(lma,sz)
            L +=1
            if sz>thres:
                smi = min(smi,sz)
                sma = max(sma,sz)
                S += 1
            else:
                zmi = min(zmi,sz)
                zma = max(zma,sz)
                Z += 1

print 'L',L,'lmi',lmi,'lma',lma
print 'S',S,'smi',smi,'sma',sma
print 'Z',Z,'zmi',zmi,'zma',zma

sizes.sort()
#print 'sizes'
#print sizes
