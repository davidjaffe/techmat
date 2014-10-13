#!/usr/bin/env python
'''
read oscilloscope data from nsrl 14c run
20141012
'''
import math
import sys
import os
import datetime

class oscope():
    def __init__(self):

        self.parentDir = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/NSRLTest141010/'
        self.pawDir = '/Users/djaffe/work/paw/TECHMAT/'
        self.headerWords = ['waveform', 't0', 'delta t','time']
        self.dateformat = '%m/%d/%Y%H:%M:%S.%f'
        
        return
    def test(self):
        dirs = self.getDirs(self.parentDir)
        path = self.parentDir + dirs[0]
        h, fl = self.getFileList(path)
        allData = []
        shortFileList = fl
        for f in shortFileList:
            print f
            header,data = self.readFile(path + '/' + f)
            allData.extend( data )
            #for entry in data: print entry
        print 'total files',len(shortFileList),'total data length',len(allData)
        debugStuff = 0
        if debugStuff :
            t0 = allData[0][0]

            print 't0',t0
            for i,entry in enumerate(allData):
                if i==0 or i%100==0:
                    dt = entry[0]-t0
                    print i,dt.total_seconds(),entry[1:]
        self.makeNtuple(allData, outputFileName=dirs[0])
        return
    def makeNtuple(self,data,outputFileName='oscope'):
        fn = self.pawDir + outputFileName
        f = open(fn,'w')
        t0 = data[0][0]
        for entry in data:
            dt = entry[0]-t0
            s = str(dt.total_seconds()) + ' '
            for e in entry[1:]: s += str(e) + ' '
            s += '\n'
            f.write(s)
        f.close()
        print 'oscope.makeNtuple: wrote',len(data),'lines to',fn
        return 
    def getDirs(self,parent):
        return os.listdir(parent)
    def getFileList(self,directory):
        '''
        returned order list of files and the header file
        '''
        l = os.listdir(directory)
        headerFile = None
        for f in l:
            if f=='HeaderInfo.txt':
                headerFile = f
                break
        l.remove(headerFile)

        s = sorted(l,None,key=lambda w: int(w.split('_')[1]))
        return headerFile,s
    def readFile(self,fn=None):
        '''
        read an input file and produce an output array
        perform some consistency checks on data
        '''
        if fn is None:
            sys.exit('oscope.readFile: ERROR no input file specified')
        f = open(fn,'r')
        header = []
        data = []
        for line in f:
            #print 'oscope.readFile: len(line)',len(line),'line',line[:-1]
            if len(line)<=1 :
                pass
            elif self.lineHasHeaderWord(line):
                header.append(line)
            else:
                a = self.parseDataLine(line)
                data.append(a)
        f.close()
        return header, data
    def parseDataLine(self,line):
        '''
        parse a line of data
        
        convert date=line[0] and time=line[1] into a datetime object
        convert the 4 channels 
        '''
        s = line.split()
        datestring = s[0]+s[1]
        dtobj = datetime.datetime.strptime(datestring,self.dateformat)
        chandata = [dtobj]
        for c in s[2:2+4]:
            chandata.append(float(c))
        return chandata
    def lineHasHeaderWord(self,line):
        for h in self.headerWords:
            if h in line: return True
        return False
if __name__ == '__main__' :
    o = oscope()
    o.test()
    
