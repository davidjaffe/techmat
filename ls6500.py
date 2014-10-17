#!/user/bin/env python
'''
read/process xls files produced by ls6500 system
'''

import spreadsheetReader
import sys
import xlrd
import os

class ls6500():
    def __init__(self):
        self.headerFileName = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/SampleInfo.xls'
        self.headerSheetName = 'LS Measurement arrangement'
        self.headerSheet = None
        self.headerFirstRowName = u'Pre-irradiation measurements (actual)'


        self.dataDir = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/LS6500/Pre-irrad_1/'

        # these are initialized in processHeader
        self.vialPosition = {} # map(key=position, value=sample)
        self.vialOrder = []  # names of samples in order of samples
        self.vialPositionOrder = [] # names of positions in order of samples

        print "initialize ls6500"
        self.ssr = spreadsheetReader.spreadsheetReader()
        return
    def processHeader(self,checkPrint=False):
        '''
        open header file, get sheet with vial positions, produce ordered list of vials
        '''
        f = self.ssr.open(self.headerFileName)
        self.headerSheet = self.ssr.findNamedSheet(sheetName = self.headerSheetName)

        done = False
        r = 0
        columnIDs = []
        slotColumn = None
        while (r<self.headerSheet.nrows) and not done:
            row = self.headerSheet.row_values(r)
            if row[0]=='' : done = True
            if not done:
                if row[0]==self.headerFirstRowName :
                    r += 1
                    row = self.headerSheet.row_values(r)
                    for c in row:
                        w = str(c).split()
                        wx= w[0]+w[1].zfill(2)
                        columnIDs.append(wx)
                        if wx=='TrayID': slotColumn = row.index(c)
                    if checkPrint: print 'ls6500.processHeader: columnIDs',columnIDs
                else:
                    row = self.headerSheet.row_values(r)
                    # process row here
                    if len(row)!=len(columnIDs):
                        w = 'ls6500.processHeader: ERROR length of row'+str(len(row))+'does not equal length of columnIDs'+str(len(columnIDs))
                        sys.exit(w)
                    rowName = None
                    for i,pair in enumerate(zip(row,columnIDs)):
                        content,ID = pair
                        if i==slotColumn:
                            rowName = str(content)
                        else:
                            positionName = rowName + '_' + columnIDs[i]
                            sampleName = str(content)
                            self.vialOrder.append(sampleName)   # order of samples 
                            self.vialPosition[positionName] = sampleName # map of position to sample name
                            self.vialPositionOrder.append(positionName) # order of positions
            r += 1
            
        # check to make sure the procedure was done correctly
        if checkPrint:
            print '{0:5} {1:>12} {2:>12} {3}'.format('vial#','sampleName','position','check of sample name')
        for i in range(len(self.vialOrder)):
            sampleName = self.vialOrder[i]
            positionName = self.vialPositionOrder[i]
            checkName = self.vialPosition[positionName]
            if checkName!=sampleName :
                print 'ERROR checkName',checkName,'does not match sampleName',sampleName
            if checkPrint:
                print '{0:>5d} {1:>12} {2:>12} {3}'.format(i,sampleName,positionName,checkName)

        print 'ls6500.processHeader: Found',len(self.vialOrder),'total samples'
            
        return
    def matchVialMeas(self,checkPrint=False):
        '''
        fill map(key=position,value= list of files with measurements of position)
        '''
        dataFileNames = os.listdir(self.dataDir)
        for fn in dataFileNames:
            if 'xls'!=fn.split('.')[1]: dataFileNames.remove(fn)
        dataFileNames.sort()
        self.vialMsmts = {}
        j = 0
        for fn in dataFileNames:
            j = j%len(self.vialPositionOrder)
            pn = self.vialPositionOrder[j]
            if pn in self.vialMsmts:
                self.vialMsmts[pn].append(fn)
            else:
                self.vialMsmts[pn] = [fn]
            j += 1
        # check what we did
        if checkPrint:
            print '{0:>20} {1:>15} {2}'.format('Position','Sample','Measurements')
            for pn in self.vialPositionOrder:
                sn = self.vialPosition[pn]
                dfn = self.vialMsmts[pn]
                print '{0:>20} {1:>15} {2}'.format(pn,sn,dfn)
        return
    def getMeasurement(self,fn):
        '''
        return header info and list of bin,contents
        '''
        return
if __name__ == '__main__' :
    ls = ls6500()
    print '\n ---------'
    ls.processHeader(checkPrint=False)
    ls.matchVialMeas(checkPrint=False)
    for i in range(20):
        pn = ls.vialPositionOrder[i]
        fn = ls.dataDir + ls.vialMsmts[pn][0]
        print pn,fn
        ls.ssr.open(fn)
        #ls.ssr.listSheets()
        # ls.ssr.printSheet(0)
        s = ls.ssr.getSheet(0)
        t,d = ls.ssr.getDate(s)
        print 'title',t,'date',d,
        tot = ls.ssr.getTotalCounts(s,totalcountscol = 5)
        print 'total counts',tot,
        rownum = 10 # sample, rackpos, time
        samnum = ls.ssr.getTotalCounts(s,totalrow=rownum,totalcountscol=4)
        rackpos= ls.ssr.getTotalCounts(s,totalrow=rownum,totalcountscol=5)
        exposuretime = ls.ssr.getTotalCounts(s,totalrow=rownum,totalcountscol=6)
        print 'sample#',samnum,'rack-pos',rackpos,'exposure time(min)',exposuretime,
        z = ls.ssr.getChannelContents(s)
        print 'contents',z[:3]
