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
        self.parentDir = '/Users/djaffe/work/GIT/LINDSEY/NSRL14C_testing/'
        self.pawDir = '/Users/djaffe/work/paw/TECHMAT/'
        self.headerWords = ['waveform', 't0', 'delta t','time']
        self.dateformat = '%m/%d/%Y%H:%M:%S.%f'
        
        return
    def test(self):
        '''
        process files in all input directories and make ntuples from each
        '''
        dirs = self.getDirs(self.parentDir)
        for onedir in dirs:
            path = self.parentDir + onedir
            print 'processing',path
            h, fl = self.getFileList(path)
            allData = []
            shortFileList = fl
            print '',
            for f in shortFileList:
                print '\r',f,
                sys.stdout.flush()
                header,data,signals = self.readFile(path + '/' + f)
                allData.extend( data )
                #for entry in data: print entry
            print ''
            print 'total files',len(shortFileList),'total data length',len(allData),\
                  'time span from',allData[0][0],'to',allData[-1][0]
            debugStuff = 0
            if debugStuff :
                t0 = allData[0][0]
                print 't0',t0
                for i,entry in enumerate(allData):
                    if i==0 or i%100==0:
                        dt = entry[0]-t0
                        print i,dt.total_seconds(),entry[1:]
            self.makeNtuple(allData, outputFileName=onedir)
        return
    def process(self):
        '''
        process files in all input directories and make ntuples from each
        '''
        rawNtuple = True
        blsNtuple = True
        intNtuple = True
        dirs = self.getDirs(self.parentDir)
        for onedir in dirs:
            path = self.parentDir + onedir
            print 'processing',path

            if rawNtuple:
                nfn = self.pawDir + onedir + 'raw'
                fout = open(nfn,'w')
                print 'opened ntuple file',nfn
            if blsNtuple:
                blsfn = self.pawDir + onedir + 'bls'
                blsout= open(blsfn,'w')
                print 'opened ntuple file',blsfn
            if intNtuple:
                intfn = self.pawDir + onedir + 'int'
                intout= open(intfn,'w')
                print 'opened ntuple file',intfn
            
            h, fl = self.getFileList(path)
            shortFileList = fl
            print '',
            t0 = None
            t1 = None
            totlen = 0
            for f in shortFileList:
                print '\r',f,
                sys.stdout.flush()
                header,data,signals = self.readFile(path + '/' + f)
                if t0 is None: t0 = data[0][0]
                data = self.reduceData(t0,data) # subtract t0
                if rawNtuple: self.fillNtuple(fout,data) # fill ntuple of reduced raw data
                data,signals,baselines = self.blsData(data,signals) # baseline subtraction of data
                if blsNtuple: self.fillNtuple(blsout,data) # fill ntuple of baseline-subtracted data
                i1,i2,t1,t2,integral = self.integrateData(t0,data,signals,baselines)
                if intNtuple: self.fillIntNtuple(intout, i1,i2,t1,t2,integral)
                totlen += len(data)
                t1 = data[-1][0]

            print 'total files',len(shortFileList),'total data length',totlen,\
                  'time span from',t0,'to',t1
            if rawNtuple: fout.close()
            if blsNtuple: blsout.close()
            if intNtuple: intout.close()

        return
    def fillIntNtuple(self, f,  i1,i2,t1,t2,integral):
        '''
        write out integrated data in spill
        '''
        s = str(i1) + ' ' + str(i2) + ' ' + str(t1) + ' ' + str(t2) + ' '
        for k in integral: s += str(integral[k]) + ' '
        s += '\n'
        f.write(s)
        return
    def integrateData(self,t0,data,signals,baselines):
        '''
        integrate data within spill defined by spillgate = data[4]
        return first,last bin #, time of first, last bin, integral of each signal
        '''
        iGate = 4
        threshold = baselines[iGate-1] + 1.
        i1 = None
        i2 = None
        for i,entry in enumerate(data):
            if i1 is None and entry[iGate]>threshold: i1 = i
            if (i1 is not None) and (i2 is None):
                if entry[iGate]<threshold:
                    i2 = i
                    break
        if i1 is None:
            i1 = 0
            i2 = 0
        t1 = (data[i1][0]).total_seconds()
        t2 = (data[max(0,i2-1)][0]).total_seconds()
        #print 'threshold',threshold,'i1',i1,'i2',i2,'t1',t1,'t2',t2
        integral = {}
        for k in signals:
            integral[k] = sum(signals[k][i1:i2])
        return i1,i2,t1,t2,integral
    def blsData(self,data,signals):
        '''
        estimate and subtract baseline
        '''
        useMeanAsBaseline = True
        mean     = {}
        nentry   = {}
        limits = {0: [-1.,1.], 1: [-1.,1.], 2: [-1.,1.], 3: [-1.,1.] }
        for k in signals:
            signal = []
            for A in signals[k]:
                if limits[k][0]<A and A<limits[k][1]: signal.append(A)
            nentry[k] = len(signal)
            mean[k] = sum(signal)
            if nentry[k]>0. : mean[k] = sum(signal)/float(nentry[k])
            if useMeanAsBaseline:
                bl = mean[k]
            else:
                d = {x:signal.count(x) for x in signal} # frequency dictionary
                maxFreq = max(d.values()) # number of occurances of most frequent value in signal
                iFreq = d.values().index(maxFreq) # index of most frequent value in dict
                bl = d.keys()[iFreq]
                mean[k] = bl # use most frequent value as mean
            #print 'channel',k,'baseline',bl,'mean',mean[k],'entries',nentry[k]
            signals[k] = [x-bl for x in signals[k]]
        for entry in data:
            for i,A in enumerate(entry):
                if i>0: entry[i] = entry[i]-mean[i-1]
        return data,signals,mean
    def reduceData(self,t0,data):
        '''
        subtract t0 from data
        '''
        for entry in data: entry[0]=entry[0]-t0
        return data
    def fillNtuple(self,f,data):
        '''
        fill ntuple with reduced raw data
        '''
        for entry in data:
            s = str(entry[0].total_seconds()) + ' '
            for e in entry[1:]: s += str(e) + ' '
            s += '\n'
            f.write(s)
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
        '''
        return list of directories with special directories removed
        '''
        l = os.listdir(parent)
        lgood = []
        for f in l:
            if f[0]!='.': lgood.append(f)
        return lgood
    def getFileList(self,directory):
        '''
        returned ordered list of files and the header file
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
        [eventually] perform some consistency checks on data
        '''
        if fn is None:
            sys.exit('oscope.readFile: ERROR no input file specified')
        f = open(fn,'r')
        header = []
        data = []
        signals = {}
        for line in f:
            #print 'oscope.readFile: len(line)',len(line),'line',line[:-1]
            if len(line)<=1 :
                pass
            elif self.lineHasHeaderWord(line):
                header.append(line)
            else:
                a = self.parseDataLine(line)
                data.append(a)
                for i,b in enumerate(a):
                    if i>0:
                        J = i-1
                        if J not in signals: signals[J] = []
                        signals[J].append(b)
                        
        f.close()
        return header, data, signals
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
    o.process()
    
