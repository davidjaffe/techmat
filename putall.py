#!/user/bin/env python
'''
process all ls6500 system data
20141028
'''

import subprocess
import os
import datetime
import shlex

parentDir = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/LS6500/'
DirList = []
for d in os.listdir(parentDir):
    good = True
    if 'csv' in d : good = False
    if d[0]=='.'  : good = False
    if good:
        DirList.append(d)

for d in DirList:
    cmd = 'python ls6500.py put ' + d + ' redirect '
    print cmd
    args = shlex.split(cmd)
    subprocess.call(args)

mergelist = ['mergegamma', 'mergensrl']
for d in mergelist:
    cmd = 'python ls6500.py merge ' + d + ' redirect '
    print cmd
    args = shlex.split(cmd)
    subprocess.call(args)
    
