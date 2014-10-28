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
    def __init__(self,mode='NSRL',redirect=False):
        self.headerFileName = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/SampleInfo.xls'
        self.headerSheetName = 'LS Measurement arrangement' #OLD. See below
        self.headerSheet = None

        # this avoids the annoying TCanvas::Print Info messages?
        ROOT.gErrorIgnoreLevel = ROOT.kWarning

        if redirect:
            unique = '_{0}'.format(datetime.datetime.now().strftime("%Y%m%d%H%M_%f"))
            lfn = 'Log/' + mode + unique + '.log'
            print 'ls6500: direct stdout to',lfn
            sys.stdout = open(lfn,'w',1)
            print 'This file is',lfn
            os.system("tail -f "+lfn + "&")


        self.dataSubDir = None
        # list of possible subdirectories
        maindir = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/LS6500/'
        dD = []
        for q in os.listdir(maindir):
            if 'csv' not in q and q[0]!='.': dD.append(maindir + q + '/')
        # sort by date in filename    
        dD = sorted(dD, key=lambda word: word.split('/')[-2][-6:])
        

        ml = mode.lower()
        
        # used for merging
        self.listOfDataDirs = [ ] #
        Merge = 'merge' in ml
        if Merge:
            if ml=='mergegamma': firstWord = 'Gamma'
            if ml=='mergensrl':  firstWord = 'Pre-irrad_'
            for d in dD:
                suffix = d.split('/')[-2]
                if firstWord==suffix[:len(firstWord)]:
                    self.listOfDataDirs.append(d)
            suffix = ml

                    
        else:
            # assign data directory based on date
            self.dataDir = None
            for q in dD:
                if ml in q or mode in q:
                    self.dataDir = q
                    break
                
            if self.dataDir is None:
                w = 'ls6500: Invalid mode ' + str(mode)
                sys.exit(w)

            # parsing of data directory into sub-directory, parent directory
            suffix = self.dataDir.split('/')[-2]
            self.dataSubDir = suffix + '/'
            self.dataParentDir = self.dataDir.replace(self.dataSubDir,'')
            # new system: subdirectory name is sheet name
            self.headerFirstRowName = None
            self.headerSheetName = suffix

        # directories for input or output. make new output directory if needed
        self.outDir = 'Histograms/'
        self.histFile = self.outDir + suffix + '.root'
        if self.dataSubDir is None: self.dataSubDir = suffix + '/'
        self.figuresDir = 'Figures/' + self.dataSubDir
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

        # introduce map from sample to list of measurements
        self.sampleMsmts = {} # map(key=sample, value=[list of filenames of measurements])

        # use in color()
        self.goodColors = [x for x in range(1,10)]
        self.goodColors.extend( [11, 12, 18] )
        self.goodColors.extend( [x for x in range(28,50)] )
        self.goodMarkers = [x for x in range(20,31) ]

        if Merge:
            print 'initialize ls6500',mode,'. Merging',
            print ', '.join([d for d in self.listOfDataDirs])
        else:
            print "initialize ls6500\ndataDir",self.dataDir,'\ndataSubDir',self.dataSubDir
            self.ssr = spreadsheetReader.spreadsheetReader()
        return
    def readTempVar(self,checkPrint=False):
        '''
        read special sheet with temperature information
        performs functions of both processHeader and matchVialMeas
        '''
        headerRowFound = False
        done = False
        r = 0
        if checkPrint: self.ssr.printSheet(self.headerSheet) 
        while (r<self.headerSheet.nrows) and not done:
            row = self.headerSheet.row_values(r)
            if row[0]=='' and headerRowFound: done = True
            if not done:
                if not headerRowFound:
                    if str(row[0])=='Measurement Number':
                        headerRowFound = True
                else:
                    measNo = int(row[0])
                    content= str(row[1])
                    sampleName = content.replace(' ','_')
                    measNoFileName = self.dataSubDir + 'MeasurementNo' + str(measNo).zfill(5) + '.xls'
                    if sampleName not in self.sampleMsmts: self.sampleMsmts[sampleName] = []
                    self.sampleMsmts[sampleName].append(measNoFileName)
            r += 1
        if checkPrint: print 'ls6500.readTempVar: sampleMsmts',self.sampleMsmts

        # now generate fake positions to fill vialPosition, vialPositionOrder and vialMsmts
        prename = 'FAKE'
        for posnum,sampleName in enumerate(self.sampleMsmts):
            pn = prename + str(posnum).zfill(3)
            self.vialPositionOrder.append(pn)
            self.vialPosition[pn] = sampleName
            self.vialMsmts[pn] = self.sampleMsmts[sampleName]
        print 'ls6500.readTempVar: found',len(self.sampleMsmts),'unique sample measurements'
        if checkPrint:
            print 'ls6500.readTempVar: vialPosition',self.vialPosition
            print 'ls6500.readTempVar: vialPositionOrder',self.vialPositionOrder
            print 'ls6500.readTempVar: vialMsmts',self.vialMsmts
        return
    def processHeader(self,checkPrint=False):
        '''
        open header file, get sheet with vial positions, produce ordered list of vials
        '''
        debug = False
        
        f = self.ssr.open(self.headerFileName)
        ##self.ssr.listSheets()  # debug
        self.headerSheet = self.ssr.findNamedSheet(sheetName = self.headerSheetName)
        if self.headerSheet is None:
            w = 'ls6500.processHeader: ERROR could not find sheet named ' + self.headerSheetName
            sys.exit(w)
        ##self.ssr.printSheet( self.headerSheet ) # debug

        if 'TempVariation' in self.headerSheetName:
            self.readTempVar()
            return False # not normal

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
                if not headerRowFound and (row[0]==self.headerFirstRowName or (self.headerFirstRowName is None)):
                    headerRowFound = True
                    if self.headerFirstRowName is not None: r += 1
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
                    if debug: print 'ls6500.processHeader: row',row
                    for i,pair in enumerate(zip(row,columnIDs)):
                        content,ID = pair
                        if i==slotColumn:
                            rowName = str(content)
                        else:
                            sampleName = str(content).replace(' ','_') # replace blanks with underscore
                            positionName = rowName + '_' + columnIDs[i]
                            if sampleName=='0.0':
                                print 'ls6500.processHeader: WARNING Found sampleName',sampleName,'for positionName',positionName,\
                                      '\nrow',row
                            if debug: print 'ls6500.processHeader:i',i,'content',content,'sampleName',sampleName,'positionName',positionName
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
            
            
        return True
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
        goodFiles = [] # temporary list
        for fn in dataFileNames:
            #print 'fn',fn
            if '.xls' in fn:
                if self.isSummaryFile(self.dataParentDir + self.dataSubDir + fn) :
                    print 'ls6500.matchVialMeas: remove summary file',fn,'from list'
                else:
                    goodFiles.append(self.dataSubDir + fn)
        dataFileNames = goodFiles 
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
        
    def getMeasurement(self,fn,positionNumber=None,numNoVial=0,performChecks=True):
        '''
        return header info and list of bin,contents from sheet 0 in file name fn
        perform checks on sheet contents, file name and positionNumber
        '''
        isheet = 0
        
        self.ssr.open(fn)
        name,date,totalCounts,ADC = self.ssr.unpackSheet(isheet)
        #print 'ls6500.getMeasurement: name',name,'date',date,'totalCounts',totalCounts
        if name is None:
            w = 'ls6500.getMeasurement: ERROR Failure with file ' + fn
            sys.exit(w)
            
        s = self.ssr.getSheet(isheet)
        samnum, rackpos, exposuretime = self.getSRpT(s)

        if performChecks:
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
        name = fn.replace('.xls',mode).replace('MeasurementNo','M').replace('/','_').replace('-','_')
        return name
    def getTimeOfMeasurement(self,fn):
        return self.vialData[fn][0]
    def setThres(self,sample,defaultThres=100.):
        thres = defaultThres
        if sample[0:3]=='STD': thres = 2000.
        return thres
    def Analyze(self):
        '''
        produce histograms for each measurement
        '''
        debugMG = False
        plotKS  = False
        
        print 'ls6500.Analyze'
        Hists = {}
        Graphs= []
        MultiGraphs = {}
        kinds = self.kindsOfSamples()
        part1, part2 = ['', 'n', 'c'], ['g', 'n', 'c']
        if plotKS:
            part1.append('k')
            part2.append('k')
        for kind in kinds:
            for pair in zip(part1,part2):
                p1,p2 = pair
                if p1+kind in MultiGraphs: # should not happen
                    words = 'ls.Analyze: ERROR '+str(p1+kind)+' already exists as key in MultiGraphs. kind='+str(kind)+' p1='+str(p1)+' p2='+str(p2)
                    sys.exit(words)
                MultiGraphs[p1+kind] = TMultiGraph()
                MultiGraphs[p1+kind].SetTitle(p2+kind)  # may be changed below
                MultiGraphs[p1+kind].SetName(p2+kind)
                if debugMG: print 'MultiGraphs make map for kind',kind


        # make histograms of raw data (counts vs channel #) for each measurement
        # and graphs of total counts vs time for each sample.
        # (datetime object 'date' must be converted to root-happy object)
        for pn in self.vialPositionOrder:
            sample = self.vialPosition[pn]
            print 'pn',pn,'sample',sample
            T,C = [],[]
            for fn in self.vialMsmts[pn]:
                date,totalCounts,exposureTime,ADC = self.vialData[fn]
                T.append ( TDatime( date.strftime('%Y-%m-%d %H:%M:%S') ).Convert() )
                C.append( float(totalCounts) )
                title = sample + ' ' + pn + ' ' + date.strftime('%Y%m%d %H:%M:%S')
                name = self.nameHist(fn)
                #print 'title',title,'name',name
                nx = len(ADC)
                xmi = -0.5
                xma = xmi + float(nx)
                Hists[name] = TH1D(name,title,nx,xmi,xma)
                for x,y in ADC: Hists[name].Fill(x,y)
            title = sample + ' ' + pn + 'total counts'
            name = 'c' + sample
            g = self.makeTGraph(T,C,title,name)
            self.fixTimeDisplay( g )
            Graphs.append(g)
            kind = 'c' + self.getKind(title)
            MultiGraphs[ kind ].Add(g)
            if debugMG: print 'Add graph',g.GetName(),'to MultiGraphs. kind=',kind
            self.color(g, MultiGraphs[ kind ].GetListOfGraphs().GetSize() )

                
        # perform root's KS test to compare first msmt with others of same sample
        # optionally plot results vs time difference
        for pn in self.vialPositionOrder:
            sample = self.vialPosition[pn]
            i = 0
            fn1 = self.vialMsmts[pn][i]
            name1 = self.nameHist(fn1)
            date1 = self.getTimeOfMeasurement(fn1)
            h1 = Hists[name1]
            print sample,name1.split('_')[0],
            T, KS = [], []
            for j in range(i+1,len(self.vialMsmts[pn])):
                fn2 = self.vialMsmts[pn][j]
                date2 = self.getTimeOfMeasurement(fn2)
                name2 = self.nameHist(fn2)
                h2 = Hists[name2]
                ks = h1.KolmogorovTest(h2)
                T.append( (date2-date1).total_seconds()/60./60. )
                KS.append( ks )
                w = '{0:4f}'.format(ks)
                print w,
            print ''
            if plotKS:
                name = 'k' + sample
                title = sample + ' ' + pn + 'KS test vs time difference in hours'
                g = self.makeTGraph(T,KS,title,name)
                Graphs.append(g)
                kind = 'k' + self.getKind(title)
                MultiGraphs[ kind ].Add(g)
                if debugMG: print 'Add graph',g.GetName(),'to MultiGraphs. kind=',kind
                self.color(g, MultiGraphs[ kind ].GetListOfGraphs().GetSize() )
                                
        # plot data from multiple hists or tgraphs
        for pn in self.vialPositionOrder:
            sample = self.vialPosition[pn]
            hlist = []
            for fn in self.vialMsmts[pn]:
                hlist.append( Hists[self.nameHist(fn)] )
            self.multiPlot(hlist) # overlay multiple hists

            thres = self.setThres(sample,defaultThres = 200.)
            tg,ntg = self.xPoint(hlist,thres=thres) # crossing point from multiple hists vs time
            
            kind = self.getKind( tg.GetTitle() )
            MultiGraphs[ kind ].Add(tg)
            if MultiGraphs[kind].GetTitle()==MultiGraphs[kind].GetName():
                MultiGraphs[kind].SetTitle( MultiGraphs[kind].GetName() + ' threshold='+str(thres) )
            if debugMG: print 'Add graph',tg.GetName(),'to MultiGraphs. kind=',kind
            ngraphs =  MultiGraphs[ kind ].GetListOfGraphs().GetSize()
            self.color(tg,ngraphs)
            Graphs.append( tg )

            kind = 'n' + kind
            MultiGraphs[ kind ].Add(ntg)
            if MultiGraphs[kind].GetTitle()==MultiGraphs[kind].GetName():
                MultiGraphs[kind].SetTitle( MultiGraphs[kind].GetName() + ' threshold='+str(thres) )
            if debugMG: print 'Add graph',ntg.GetName(),'to MultiGraphs. kind=',kind
            self.color(ntg,ngraphs)
            Graphs.append( ntg )


        # output of hists, graphs.
        # processing of multigraphs
        outname = self.histFile
        outfile = TFile(outname,'RECREATE')
        for h in Hists: outfile.WriteTObject( Hists[h] )
        for tg in Graphs: outfile.WriteTObject( tg )
        if debugMG: print 'MultiGraphs',MultiGraphs,'\n'
        for kind in MultiGraphs:
            if debugMG: print 'kind',kind,'MultiGraphs[kind]',MultiGraphs[kind]
            self.multiGraph(MultiGraphs[kind])
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
    def color(self,obj,n):
        '''
        set line color and marker type for obj based on index n
        '''
        LC = len(self.goodColors)
        LM = len(self.goodMarkers)
        c = n%LC
        obj.SetLineColor( self.goodColors[c] )
        if obj.IsA().GetName()=='TGraph':
            m = int(float(n)/float(LC))%LM
            obj.SetMarkerStyle( self.goodMarkers[m] )
        return

    def xPoint(self,hlist,thres=100., maxchan=1000):
        '''
        Return TGraph of crossing-point for multiple hists.
        Return TGraph of crossing-point for multiple hists normalized to first point.
        Determine crossing-point by starting at maxchan channel and descending in
        channel number until the threshold is crossed, then linearly interpolate
        between two neighboring channels to calculate crosssing-point.
        '''
        debugTime = False
        h0 = hlist[0]
        sample = self.setSamName(h0)
        title = sample + ' channel for threshold=' + str(int(thres))
        X,Y,normY = [],[],[]
        for h in hlist:
            s = h.GetTitle().split()
            date = datetime.datetime.strptime(s[2]+' '+s[3],'%Y%m%d %H:%M:%S')
            timestring = date.strftime('%Y-%m-%d %H:%M:%S')
            if debugTime: print 'h.GetTitle()',h.GetTitle(),'timestring',timestring
            tdobj= TDatime( timestring )
            if debugTime: print 'TDatime',tdobj.AsString(),'as MySQL string',tdobj.AsSQLString(),'TDatime.Convert()',tdobj.Convert()

            
            X.append( tdobj.Convert() )
            x = None
            for i in range(maxchan,0,-1):
                y = h.GetBinContent(i)
                if y>thres:
                    x = self.xint(i,y,i+1,h.GetBinContent(i+1),thres)
                    Y.append( x )
                    normY.append( x/Y[0] )
                    break
        tg = self.makeTGraph(X,Y,title,'g'+sample)
        ntg= self.makeTGraph(X,normY,title + ' normed','n'+sample)
        for g in [tg, ntg]:
            g.SetMarkerStyle(20)
            self.fixTimeDisplay(g)
        return tg,ntg
    def fixTimeDisplay(self,g):
        '''
        set time axis to display nicely
        '''
        g.GetXaxis().SetTimeDisplay(1)
        g.GetXaxis().SetTimeFormat("#splitline{%H:%M}{%y/%m/%d}")
        g.GetXaxis().SetNdivisions(-409)
        g.GetXaxis().SetTimeOffset(0,"gmt") # using gmt option gives times that are only off by 1 hour on tgraph
        return
    def setSamName(self,h0):
        '''
        get unique sample name from histogram title
        '''
        w = h0.GetTitle().split()
        sample = w[0]
        if 'EMPTY' in sample: sample += '_' + w[1]
        return sample
    def multiGraph(self,TMG,truncT=True):
        '''
        draw TMultiGraph with legend and output as pdf
        Default is that abscissa is calendar time
        if truncT = True, then truncate title for legend
        '''
        debugMG = False
        if not TMG.GetListOfGraphs(): return  # empty
        title = TMG.GetTitle()
        name  = TMG.GetName()
        if debugMG: print 'ls6500.multiGraph',title,name,'TMG.GetListOfGraphs()',TMG.GetListOfGraphs(),'TMG.GetListOfGraphs().GetSize()',TMG.GetListOfGraphs().GetSize()

        pdf = self.figuresDir + name + '.pdf'
        ps  = self.figuresDir + name + '.ps'
        xsize,ysize = 1100,850 # landscape style
        noPopUp = True
        if noPopUp : gROOT.ProcessLine("gROOT->SetBatch()")
        canvas = TCanvas(pdf,title,xsize,ysize)
        lg = TLegend(.15,.15, .3,.35)
        for g in TMG.GetListOfGraphs():
            t = g.GetTitle()
            if truncT: t = t.split()[0]
            lg.AddEntry(g, t, "l" )
        TMG.Draw("apl")
        if name[0]!='k': self.fixTimeDisplay( TMG )
        lx = TMG.GetXaxis().GetLabelSize()
        TMG.GetXaxis().SetLabelSize(0.75*lx)
        TMG.GetXaxis().SetNdivisions(-409)
        lg.Draw()
        canvas.Draw()
        canvas.SetGrid(1)
        canvas.SetTicks(1)
        canvas.cd()
        canvas.Modified()
        canvas.Update()
        if 0:
            canvas.Print(pdf,'pdf')
        else:
            canvas.Print(ps,'Landscape')
            os.system('ps2pdf ' + ps + ' ' + pdf)
            if os.path.exists(pdf): os.system('rm ' + ps)
        return
    def multiPlot(self,hlist):
        '''
        overlay multiple histograms on same canvas
        '''
        h0 = hlist[0]
        # sample name should include position for EMPTY samples
        sample = self.setSamName(h0)
        # upper limit of 1000. channels only for LS
        xma = 2000.
        if sample[0:4]=='EMPT' : xma = 100.
        if sample[0:3]=='STD'  : xma = 1500.
        if sample[0]=='0': xma = 200.  #WbLS
        if sample[0]=='1': xma = 1000. # LS
        pdf = self.figuresDir  + sample + '.pdf'
        xsize,ysize = 850,1000 # nominally portrait
        noPopUp = True
        if noPopUp : gROOT.ProcessLine("gROOT->SetBatch()")
        canvas = TCanvas(pdf,self.dataDir.split('/')[-2],xsize,ysize)
        canvas.SetLogy(1)
        h0.GetXaxis().SetRangeUser(0.,xma)
        lg = TLegend(.5,.7, .7,.95)
        for i,h in enumerate(hlist):
            #h.SetLineColor(i+1) # 0=white
            self.color(h,i)
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
    def merge(self):
        '''
        merge together the pickled results of multiple directories
        '''
        vP = {}
        vM = {}
        vD = {}
        for dD in self.listOfDataDirs:
            self.dataDir = dD
            #print 'ls6500.merge: dataDir',self.dataDir
            self.putOrGet(mode='get')
            
            # add all {filename:[data]} pairs
            for fn in self.vialData:
                vD[fn] = self.vialData[fn]
            # establish position : sample : list of filenames relations
            # First time, transfer vialPosition,vialMsmts dicts to local dicts
            if len(vP)==0:
                for pn in self.vialPosition:
                    vP[pn] = self.vialPosition[pn]
                    vM[pn] = self.vialMsmts[pn]
            else:
                for pn in self.vialPosition:
                    if pn in vP:
                        # this position already exits. check if same sample is in same position
                        if self.vialPosition[pn]==vP[pn]:
                            # same sample. add list of filenames of measurements
                            vM[pn].extend(self.vialMsmts[pn])
                    else:
                        # new position
                        vP[pn] = self.vialPosition[pn]
                        vM[pn] = self.vialMsmts[pn]
        # done transferring data to local dicts, now clear global dicts
        # and fill them
        self.vialPosition = vP
        self.vialMsmts    = vM
        self.vialData     = vD
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
        if len(kinds)==0: # handles TempVariation
            for pn in self.vialPosition:
                sample = self.vialPosition[pn]
                kind = sample[0:4]
                if kind not in kinds: kinds.append(kind)
        return kinds
    def getKind(self,title):
        '''
        get kind of sample from title
        '''
        kind = title.split()[0][0:4]
        return kind
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
            Normal = self.processHeader(checkPrint=False)
            if Normal:
                # normal processing
                self.matchVialMeas(checkPrint=False)
                for pn,numNoVial in zip(self.vialPositionOrder,self.noVial):
                    if checkPrint: print 'Tray_Position',pn,'Number of `no vial` to this position',numNoVial

                    for fn in self.vialMsmts[pn]:
                        fpath = self.dataParentDir + fn

                        if checkPrint: print 'get measurement from',fpath
                        self.vialData[fn] = date,totalCounts,exposureTime,ADC = self.getMeasurement(fpath,positionNumber=pn,numNoVial=numNoVial)
            else:
                # not normal processing. for temperature variation
                for pn in self.vialPosition:
                    for fn in self.vialMsmts[pn]:
                        fpath = self.dataParentDir + fn
                        self.vialData[fn] = date,totalCounts,exposureTime,ADC = self.getMeasurement(fpath,performChecks=False)
                        
            self.putOrGet(mode=pickMode)
        elif pickMode.lower()=='get':
            self.putOrGet(mode=pickMode)
        elif pickMode.lower()=='merge':
            self.merge()
        self.Analyze()
        return
            
if __name__ == '__main__' :
    print '\n ---------'
    pickMode = 'put' # 'get' 'merge'
    runMode = 'gamma'
    redirect = False
    args = sys.argv
    if len(args)>1: pickMode = str(args[1])
    if len(args)>2: runMode = str(args[2])
    if len(args)>3: redirect = True
    ls = ls6500(mode=runMode,redirect=redirect)
    ls.Main(checkPrint=True,pickMode=pickMode)
