#!/user/bin/env python
'''
read/process xls files produced by ls6500 system
'''

import spreadsheetReader
import sys
import xlrd
import os
import pickle
import ROOT
import datetime
from ROOT import TH1D, TFile, gROOT, TCanvas, TLegend, TGraph, TDatime, TMultiGraph
from array import array

class ls6500():
    def __init__(self,mode='NSRL'):
        self.headerFileName = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/SampleInfo.xls'
        self.headerSheetName = 'LS Measurement arrangement'
        self.headerSheet = None

        if mode.lower()=='nsrl' or mode=='':
            self.headerFirstRowName = u'Pre-irradiation measurements 141014 (actual)'
            self.dataDir = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/LS6500/Pre-irrad_1_141014/'
        elif mode.lower()=='gamma':
        
            self.headerFirstRowName = u'Pre-irradiation measurements 141017 (actual)'
            self.dataDir = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/LS6500/Gamma_Pre-irradiation141017/'
        else:
            w = 'ls6500: Invalid mode ' + str(mode)
            sys.exit(w)

        suffix = self.dataDir.split('/')[-2]

        self.outDir = 'Histograms/'
        self.figuresDir = 'Figures/' + suffix + '/'
        self.picklesDir = 'Pickles/'
        for d in [self.outDir, self.figuresDir, self.picklesDir ]:
            if not os.path.isdir(d):
                os.makedirs(d)
                print 'Created',d
                


        # these are initialized in processHeader
        self.vialPosition = {} # map(key=position, value=sample)
        self.vialOrder = []  # names of samples in order of samples
        self.vialPositionOrder = [] # names of positions in order of samples
        self.noVial = [] # number of 'no vial' positions up to this position

        # initialized in matchVialMeas
        self.vialMsmts = {} # map(key=position, value=[list of filenames of measurements])
        # initialized in Main
        self.vialData  = {} # map(filename, value = [data])

        print "initialize ls6500"
        self.ssr = spreadsheetReader.spreadsheetReader()
        return
    def processHeader(self,checkPrint=False):
        '''
        open header file, get sheet with vial positions, produce ordered list of vials
        '''
        f = self.ssr.open(self.headerFileName)
        ##self.ssr.listSheets()  # debug
        self.headerSheet = self.ssr.findNamedSheet(sheetName = self.headerSheetName)
        if self.headerSheet is None:
            w = 'ls6500.processHeader: ERROR could not find sheet named ' + self.headerSheetName
            sys.exit(w)
        ##self.ssr.printSheet( self.headerSheet ) # debug

        done = False
        headerRowFound = False
        r = 0
        columnIDs = []
        slotColumn = None
        numNoVial = 0
        while (r<self.headerSheet.nrows) and not done:
            row = self.headerSheet.row_values(r)
            if row[0]=='' and headerRowFound : done = True
            if not done:
                if row[0]==self.headerFirstRowName :
                    headerRowFound = True
                    r += 1
                    row = self.headerSheet.row_values(r)
                    for c in row:
                        w = str(c).split()
                        wx= w[0]+w[1].zfill(2)
                        columnIDs.append(wx)
                        if wx=='TrayID': slotColumn = row.index(c)
                    if checkPrint: print 'ls6500.processHeader: columnIDs',columnIDs
                elif headerRowFound:
                    row = self.headerSheet.row_values(r)
                    # process row here
                    # handle columns in row that are empty
                    if len(row)!=len(columnIDs):
                        w = 'ls6500.processHeader: ERROR length of row'+str(len(row))+'does not equal length of columnIDs'+str(len(columnIDs))
                        sys.exit(w)
                    rowName = None
                    for i,pair in enumerate(zip(row,columnIDs)):
                        content,ID = pair
                        if i==slotColumn:
                            rowName = str(content)
                        else:
                            sampleName = str(content)
                            positionName = rowName + '_' + columnIDs[i]
                            if sampleName=='':
                                print 'ls6500.processHeader:',positionName,'has no vial'
                                numNoVial += 1
                            else:
                                self.vialOrder.append(sampleName)   # order of samples 
                                self.vialPosition[positionName] = sampleName # map of position to sample name
                                self.vialPositionOrder.append(positionName) # order of positions
                                self.noVial.append( numNoVial )
            r += 1
            
        if len(self.vialOrder)==0 :
            w = 'ls6500.processHeader: ERROR Could not find headerFirstRowName ' + self.headerFirstRowName \
                + ' in sheet named ' + self.headerSheetName
            sys.exit(w)
            
        # check to make sure the procedure was done correctly
        if checkPrint:
            print '{0:5} {1:>12} {2:>12} {3} {4}'.format('vial#','sampleName','position','check of sample name','Number of `no vial` slots to this slot')
        for i in range(len(self.vialOrder)):
            sampleName = self.vialOrder[i]
            positionName = self.vialPositionOrder[i]
            checkName = self.vialPosition[positionName]
            nnV = self.noVial[i]
            if checkName!=sampleName :
                print 'ERROR checkName',checkName,'does not match sampleName',sampleName
            if checkPrint:
                print '{0:>5d} {1:>12} {2:>12} {3} {4}'.format(i,sampleName,positionName,checkName,nnV)

        print 'ls6500.processHeader: Found',len(self.vialOrder),'total samples'
            
            
        return
    def isSummaryFile(self,fn):
        self.ssr.open(fn)
        s = self.ssr.getSheet(0)
        words = self.ssr.getRowColContents(s,row=0,col=0)
        #print 'fn',fn,'words',words
        if u'Instrument Type'==words: return True
        return False
        
    def matchVialMeas(self,checkPrint=False):
        '''
        fill map(key=position,value= list of files with measurements of position)
        reject non-.xls files
        reject .xls files that are summary files
        
        '''
        dataFileNames = os.listdir(self.dataDir)
        for fn in dataFileNames:
            #print 'fn',fn
            if 'xls'!=fn.split('.')[1]:
                dataFileNames.remove(fn)
            else:
                if self.isSummaryFile(self.dataDir + fn) :
                    print 'ls6500.matchVialMeas: remove summary file',fn,'from list'
                    dataFileNames.remove(fn)
        dataFileNames.sort()
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
    def getSRpT(self,sheet):
        '''
        extract the sample number, rack position, and programmed exposure time
        in minutes from the sheet
        return as integer, integer and float
        '''
        s = sheet
        rownum = 10 # sample, rackpos, time
        samnum = int(self.ssr.getRowColContents(s,row=rownum,col=4))
        rackpos= self.ssr.getRowColContents(s,row=rownum,col=5)
        rackpos= int(rackpos.replace('**-',''))
        exposuretime = float(self.ssr.getRowColContents(s,row=rownum,col=6))
        return samnum, rackpos,exposuretime
        
    def getMeasurement(self,fn,positionNumber=None,numNoVial=0):
        '''
        return header info and list of bin,contents from sheet 0 in file name fn
        perform checks on sheet contents, file name and positionNumber
        '''
        isheet = 0
        
        self.ssr.open(fn)
        name,date,totalCounts,ADC = self.ssr.unpackSheet(isheet)
        if name is None:
            w = 'ls6500.getMeasurement: ERROR Failure with file ' + fn
            sys.exit(w)
            
        s = self.ssr.getSheet(isheet)
        samnum, rackpos, exposuretime = self.getSRpT(s)

        # check measurement number in file name against sample number
        # an adjustment is made for the existence of a summary file for each lap
        measNo = int(fn.split('MeasurementNo')[1].replace('.xls',''))
        L = len(self.vialOrder)
        if samnum!=(measNo%(L+1))+numNoVial :
            w = 'ls6500.getMeasurement: ERROR Msmt# ' + str(measNo) \
                + '%(' + str(L+1) + ')' \
                + ' in filename not equal to samplenumber in file ' + str(samnum) \
                + ' for numNoVial ' + str(numNoVial)
            sys.exit(w)

        # check position number against rack-position number
        if positionNumber is not None:
            ipn =  int(positionNumber[-2:])
            if ipn!=rackpos :
                w = 'ls6500.getMeasurement: ERROR positionNumber'+str(ipn)+'not equal rack-position'+str(rackpos)
                sys.exit(w)

        return date, totalCounts, exposuretime, ADC
    def nameHist(self,fn,mode='_h1d'):
        name = fn.replace('.xls',mode).replace('MeasurementNo','M')
        return name
    def Analyze(self):
        '''
        produce histograms for each measurement
        '''
        print 'ls6500.Analyze'
        Hists = {}
        Graphs= []
        MultiGraphs = {}
        kinds = self.kindsOfSamples()
        for kind in kinds:
            MultiGraphs[kind] = TMultiGraph()
            MultiGraphs[kind].SetTitle('g'+kind+'g')
            MultiGraphs[kind].SetName('g'+kind+'g')

        for pn in self.vialPositionOrder:
            sample = self.vialPosition[pn]
            print 'pn',pn,'sample',sample
            for fn in self.vialMsmts[pn]:
                date,totalCounts,exposureTime,ADC = self.vialData[fn]
                title = sample + ' ' + pn + ' ' + date.strftime('%Y%m%d %H:%M:%S')
                name = self.nameHist(fn)
                print 'title',title,'name',name
                nx = len(ADC)
                xmi = -0.5
                xma = xmi + float(nx)
                Hists[name] = TH1D(name,title,nx,xmi,xma)
                for x,y in ADC: Hists[name].Fill(x,y)
        # perform root's KS test on all pairs
        for pn in self.vialPositionOrder:
            sample = self.vialPosition[pn]
            print sample,
            for i,fn1 in enumerate(self.vialMsmts[pn]):
                name1 = self.nameHist(fn1)
                h1 = Hists[name1]
                for j in range(i+1,len(self.vialMsmts[pn])):
                    fn2 = self.vialMsmts[pn][j]
                    name2 = self.nameHist(fn2)
                    h2 = Hists[name2]
                    ks = h1.KolmogorovTest(h2)
                    w = '{0} {1} {2:4f}'.format(name1.split('_')[0],name2.split('_')[0],ks)
                    print w,
            print ''

        

        # plot
        for pn in self.vialPositionOrder:
            hlist = []
            for fn in self.vialMsmts[pn]:
                hlist.append( Hists[self.nameHist(fn)] )
            self.multiPlot(hlist)
            tg = self.xPoint(hlist)
            t = tg.GetTitle()
            MultiGraphs[ t[:4] ].Add(tg)
            ngraphs =  MultiGraphs[ t[:4] ].GetListOfGraphs().GetSize() 
            tg.SetLineColor(ngraphs)
            Graphs.append( tg )


        
        outname = self.outDir + 'blah.root'
        outfile = TFile(outname,'RECREATE')
        for h in Hists: outfile.WriteTObject( Hists[h] )
        for tg in Graphs: outfile.WriteTObject( tg )
        for kind in MultiGraphs:
#            MultiGraphs[kind].GetXaxis().SetTimeDisplay(1)
#            MultiGraphs[kind].GetXaxis().SetTimeFormat("%Y-%m-%d %H:%M")
            outfile.WriteTObject( MultiGraphs[kind] )
        outfile.Close()
        print 'ls6500.Analyze: Wrote hists to',outname
        return
    def xint(self,x1,y1,x2,y2,yt):
        dx = x2-x1
        if dx==0. : return x1
        m = (y2-y1)/dx
        if m==0. : return (y1+y2)/2.
        b = y2 - m*x2
        return (yt-b)/m
    def makeTGraph(self,u,v,title,name):
        g = TGraph(len(u),array('d',u), array('d',v))
        g.SetTitle(title)
        g.SetName(name)
        return g
    def xPoint(self,hlist):
        '''
        TGraph of crossing-point for multiple hists
        '''
        thres = 100.
        maxchan = 1000
        h0 = hlist[0]
        sample = self.setSamName(h0)
        title = sample + ' channel for threshold=' + str(int(thres))
        X,Y = [],[]
        for h in hlist:
            s = h.GetTitle().split()
            date = datetime.datetime.strptime(s[2]+' '+s[3],'%Y%m%d %H:%M:%S')
            tdobj= TDatime( date.strftime('%Y-%m-%d %H:%M:%S') )
            X.append( tdobj.Convert() )
            x = None
            for i in range(maxchan,0,-1):
                y = h.GetBinContent(i)
                if y>thres:
                    x = self.xint(i,y,i+1,h.GetBinContent(i+1),thres)
                    Y.append( x )
                    break
        tg = self.makeTGraph(X,Y,title,'g'+sample)
        tg.SetMarkerStyle(20)
        tg.GetXaxis().SetTimeDisplay(1)
        tg.GetXaxis().SetTimeFormat("%Y-%m-%d %H:%M")
        return tg
    def setSamName(self,h0):
        '''
        get unique sample name from histogram title
        '''
        w = h0.GetTitle().split()
        sample = w[0]
        if 'EMPTY' in sample: sample += '_' + w[1]
        return sample
    def multiPlot(self,hlist):
        '''
        overlay multiple histograms on same canvas
        '''
        h0 = hlist[0]
        # sample name should include position for EMPTY samples
        sample = self.setSamName(h0)
        # upper limit of 1000. channels only for LS
        xma = 200.
        if sample[0]=='1': xma = 1000.
        pdf = self.figuresDir  + sample + '.pdf'
        ysize = 800
        xsize = 8.5/11.*ysize
        noPopUp = False
        if noPopUp : gRoot.ProcessLine("gRoot->SetBatch()")
        canvas = TCanvas(pdf,self.dataDir.split('/')[-2],xsize,ysize)
        canvas.SetLogy(1)
        h0.GetXaxis().SetRangeUser(0.,xma)
        lg = TLegend(.2,.7, .6,.95)
        for i,h in enumerate(hlist):
            h.SetLineColor(i+1) # 0=white
            opt = ""
            if i>0: opt = "same"
            h.Draw(opt)
            t = h.GetTitle().split()
            d = t[2] + ' ' + t[3]
            lg.AddEntry(h,d,"l")

        lg.Draw()
        canvas.SetGrid(1)
        canvas.cd()
        canvas.Modified()
        canvas.Update()
        canvas.Print(pdf,'pdf')
        return
    def putOrGet(self,mode='put'):
        '''
        mode = put = write info to pickle file
        mode = get = retrieve info from pickle file
        '''
        fn = self.picklesDir + self.dataDir.split('/')[-2] + '.pickle'
        if mode.lower()=='put':
            f = open(fn,'w')
            obj = self.vialPosition, self.vialOrder, self.vialPositionOrder, self.vialMsmts, self.vialData
            print 'ls6500.putOrGet: patience...writing pickled data to',fn
            pickle.dump( obj, f)
            f.close()
        elif mode.lower()=='get':
            f = open(fn,'r')
            print 'ls6500.putOrGet: unpickling...be patient'
            obj = pickle.load(f)
            self.vialPosition, self.vialOrder, self.vialPositionOrder, self.vialMsmts, self.vialData = obj
            f.close()
            print 'ls6500.putOrGet: pickled data read from',fn
        else:
            w = 'ls6500.putOrGet: ERROR Invalid mode ' + str(mode)
            sys.exit(mode)
        return
    def kindsOfSamples(self):
        '''
        fill list with kinds of samples
        '''
        kinds = []
        for sample in self.vialOrder:
            kind = sample[0:4]
            if kind not in kinds: kinds.append(kind)
        return kinds
    def Main(self,checkPrint=False,pickMode='put'):
        '''
        evocatively named module
        either: 
           process header file information to obtain sample + position information,
           associate measurement filename with sample+position information,
           associate each measurement with sample+position
           pickle results
        or:
           unpickle results
        analyze
        '''
        if checkPrint: print 'ls6500.Main: pickMode',pickMode
        if pickMode.lower()=='put':
            self.processHeader(checkPrint=False)
            self.matchVialMeas(checkPrint=False)
            for pn,numNoVial in zip(self.vialPositionOrder,self.noVial):
                if checkPrint: print 'Tray_Position',pn,'Number of `no vial` to this position',numNoVial

                for fn in self.vialMsmts[pn]:
                    fpath = self.dataDir + fn

                    if checkPrint: print 'get measurement from',fpath
                    self.vialData[fn] = date,totalCounts,exposureTime,ADC = self.getMeasurement(fpath,positionNumber=pn,numNoVial=numNoVial)
            self.putOrGet(mode=pickMode)
        elif pickMode.lower()=='get':
            self.putOrGet(mode=pickMode)
        self.Analyze()
        return
            
if __name__ == '__main__' :
    print '\n ---------'
    pickMode = 'put'
    runMode = 'gamma'
    args = sys.argv
    if len(args)>1: pickMode = str(args[1])
    if len(args)>2: runMode = str(args[2])
    ls = ls6500(mode=runMode)
    ls.Main(checkPrint=True,pickMode=pickMode)
