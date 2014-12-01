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
import Logger
import math
from ROOT import TH1D, TFile, gROOT, TCanvas, TLegend, TGraph, TDatime, TMultiGraph, gStyle, TGraphErrors, TLine
from array import array

class ls6500():
    def __init__(self,mode='NSRL',redirect=False):
        self.headerFileName = '/Users/djaffe/work/GIT/LINDSEY/TechMaturation2014/SampleInfo.xls'
        self.headerSheetName = 'LS Measurement arrangement' #OLD. See below
        self.headerSheet = None

        # this avoids the annoying TCanvas::Print Info messages
        ROOT.gErrorIgnoreLevel = ROOT.kWarning
        gStyle.SetOptStat(1001111) # title,entries,mean,rms,integral

        # logging to terminal and to file
        if redirect:
            unique = '_{0}'.format(datetime.datetime.now().strftime("%Y%m%d%H%M_%f"))
            lfn = 'Log/' + mode + unique + '.log'
            print 'ls6500: direct stdout to',lfn
            sys.stdout = Logger.Logger(fn=lfn)
            print 'ls6500: Output directed to terminal and',lfn

        # default is no irradiation. Set to arbitrary date in future
        self.irradDate = '2020/04/01 01:23:45'
        self.irradInterval = ['2020/04/01 01:23:44', '2020/04/01 01:23:46']  # time when irradiation occurred
        self.irradNearby   = ['2029/03/31 12:34:56', '2020/04/02 02:46:42']  # interval near irrad period
        self.irradIntervalTDatime = None
        self.irradNearbyTDatime   = None

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
        self.listOfDataDirs = [ ]
        self.mergeType = None
        Merge = 'merge' in ml
        if Merge:
            if ml=='mergegamma':
                firstWord = ['Gamma']
                self.mergeType = 'Gamma_1'
                self.irradDate = '2014/10/20 16:00:00'
                self.irradInterval = ['2014/10/20 16:00:00', '2014/10/21 10:00:00']
                self.irradNearby   = ['2014/10/18 08:00:00', '2014/10/23 18:00:00']
            if ml=='mergensrl':
                firstWord = ['Pre-irrad_','Post-irrad']
                self.mergeType = 'NSRL_1'
                self.irradDate = '2014/11/17 18:00:00'
                self.irradInterval = ['2014/11/17 18:54:00', '2014/11/17 20:11:00']
                self.irradNearby   = ['2014/11/10 00:00:01', '2014/11/24 23:59:59']
            for d in dD:
                suffix = d.split('/')[-2]
                for fw in firstWord:
                    if fw==suffix[:len(fw)]:
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


        # convert irradiation date to datetime and TDatime objects
        #self.irradDate_datetime = datetime.datetime.strptime(self.irradDate,'%Y/%m/%d %H:%M:%S')
        #self.irradDate_TDatime  = TDatime( self.irradDate_datetime.strftime('%Y-%m-%d %H:%M:%S') ).Convert()
        self.irradDate_datetime = self.getdatetime(self.irradDate,fmt='%Y/%m/%d %H:%M:%S')
        self.irradDate_TDatime  = self.getTDatime( self.irradDate,fmt='%Y/%m/%d %H:%M:%S' )
        print 'ls6500: Irradiation date is',self.irradDate,'irradiation interval is',self.irradInterval[0],self.irradInterval[1]


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
        self.badFileAdjustment = {} # map(key=filename,value=adjustment=non-negative integer)
        # initialized in Main
        self.vialData  = {} # map(filename, value = [data])

        # introduce map from sample to list of measurements
        self.sampleMsmts = {} # map(key=sample, value=[list of filenames of measurements])

        # filled in defineMatchingSamples
        self.matchingSamples = {} # map(key=common sample name, value=[list of sample names])

        # intialized in setNSRL14Cdoses
        # campaign = e.g. 'Irr1_Front', 'Irr2_Rear', etc.
        self.NSRL14Cdoses = {} # map(key = sample, value = dose in gray)
        self.NSRL14Ccampaign = {} # map(key = campaign, value = list of samples)
        
        # use in color()
        self.goodColors = [x for x in range(1,10)]
        self.goodColors.extend( [11, 12, 18] )
        self.goodColors.extend( [x for x in range(28,50)] )
        self.goodMarkers = [x for x in range(20,31) ]

        # set threshold in isSummaryFile (determined empirically using rudimentary.py)
        self.maxSizeForSummaryFile = 190000

        if Merge:
            print 'ls6500: initialization',mode,'. Merging',
            print ', '.join([d for d in self.listOfDataDirs])
        else:
            print "ls6500: initialization ls6500\ndataDir",self.dataDir,'\ndataSubDir',self.dataSubDir
            self.ssr = spreadsheetReader.spreadsheetReader()
        return
    def getTDatime(self,dt,fmt='%Y/%m/%d %H:%M:%S'):
        '''
        convert date/time text to TDatime object
        '''
        datetimeObj = self.getdatetime(dt,fmt)
        return TDatime( datetimeObj.strftime('%Y-%m-%d %H:%M:%S') ).Convert()
    def getdatetime(self,dt,fmt='%Y/%m/%d %H:%M:%S'):
        return datetime.datetime.strptime(dt,fmt)
    
    def setNSRL14Cdoses(self):
        '''
        set doses for samples from NSRL run 14C
        '''
        # irradiation#1 Front
        nomDose = 20.05 
        frontTop = ['0050_1F11', '0050_3F11', '0050_1F13', '0050_3F13', '0100_1F15', '0050_1F16', 'F_3R24']
        frontMid = ['0100_3F22', '0100_1F22', '0140_1F23', 'F_1F24'   , '0100_3F15', '0050_3F16', '0100_1F27']
        frontBot = ['0140_1F31', '1000_3F37', '0140_3F23', '1000_1F34', '1000_3F34', '1000_1F36', '1000_1F37']
        all = []
        all.extend(frontTop)
        all.extend(frontMid)
        all.extend(frontBot)
        self.NSRL14Ccampaign['Irr1_Front'] = all
        for x in all:
            self.NSRL14Cdoses[x] = nomDose
        
        # irradiation#1 Rear
        nomDose = 20.05 * 2.4
        rearTop  = ['0050_1R11', '0050_3R11', '0050_1R13', '0050_3R13', '0100_1R15', '0050_1R16', 'F_3F24']
        rearMid  = ['0100_3R22', '0100_1R22', '0140_1R23', 'F_1R24'   , '0100_3R15', '0050_3R16', '0100_1R27']
        rearBot  = ['0140_1R31', '1000_3R37', '0140_3R23', '1000_1R34', '1000_3R34', '1000_3R36', '1000_1R37']
        all = []
        all.extend(rearTop)
        all.extend(rearMid)
        all.extend(rearBot)
        self.NSRL14Ccampaign['Irr1_Rear'] = all
        for x in all:
            if x in self.NSRL14Cdoses:
                words = 'ls6500.setNSRL14Cdoses: ERROR ' + x + ' already exists in dict with dose ' + str(self.NSRL14Cdoses[x])
                sys.exit(words)
            self.NSRL14Cdoses[x] = nomDose

        # irradiation#2 Front
        nomDose = 48.01
        frontTop = ['0050_2F11', '0050_4F11', '0050_2F13', '0050_4F13', '0100_2F15', '0050_2F16', 'F_4F24']
        frontMid = ['0100_4F22', '0100_2F22', '0140_2F23', 'F_2F24'   , '0100_4F15', '0050_4F16', '0100_2F27']
        frontBot = ['0140_2F31', '1000_4F37', '0140_4F23', '1000_2F34', '1000_4F34', '1000_2F36', '1000_2F37']
        all = []
        all.extend(frontTop)
        all.extend(frontMid)
        all.extend(frontBot)
        self.NSRL14Ccampaign['Irr2_Front'] = all
        for x in all:
            if x in self.NSRL14Cdoses:
                words = 'ls6500.setNSRL14Cdoses: ERROR ' + x + ' already exists in dict with dose ' + str(self.NSRL14Cdoses[x])
                sys.exit(words)
            self.NSRL14Cdoses[x] = nomDose
        
        # irradiation#2 Rear
        nomDose = 48.01 * 2.4
        rearTop  = ['0500_2R11', '0050_4R11', '0050_2R13', '0050_4R13', '0100_2R15', '0050_2R16', 'F_4R24']
        rearMid  = ['0100_4R22', '0100_2R22', '0140_2R23', 'F_2R24'   , '0100_4R15', '0050_4R16', '0100_2R27']
        rearBot  = ['0140_2R31', '1000_4R37', '0140_4R23', '1000_2R34', '1000_4R34', '1000_2R36', '1000_2R37']
        all = []
        all.extend(rearTop)
        all.extend(rearMid)
        all.extend(rearBot)
        self.NSRL14Ccampaign['Irr2_Rear'] = all
        for x in all:
            if x in self.NSRL14Cdoses:
                words = 'ls6500.setNSRL14Cdoses: ERROR ' + x + ' already exists in dict with dose ' + str(self.NSRL14Cdoses[x])
                sys.exit(words)
            self.NSRL14Cdoses[x] = nomDose
        print 'ls6500.setNSRL14Cdoses: Initialization complete'
        return 
    def matchNSRL14C(self,sample1,sample2):
        '''
        determine if two samples have same WbLS formulation and if they have the same
        nominal dose in NSRL14C
        '''
        if len(self.NSRL14Cdoses)<1: self.setNSRL14Cdoses()
        suffix = ''
        nMatch = sample1[:4]==sample2[:4]
        if not nMatch: return nMatch,suffix
        for suffix in self.NSRL14Ccampaign:
            nMatch = (sample1 in self.NSRL14Ccampaign[suffix]) and (sample2 in self.NSRL14Ccampaign[suffix])
            if nMatch:
                if 0: print 'ls6500.matchNSRL14C: sample1,sample2',sample1,sample2,'suffix',suffix,'NSRL14Ccampaign[suffix]',self.NSRL14Ccampaign[suffix]
                return nMatch,suffix
        suffix = ''
        return nMatch,suffix
    def matchSamples(self,sample1,sample2):
        '''
        return True and common sample name, if sample1 and sample2 are a good match;
        that is, if they are the same composition exposed to the same dose.
        Gamma_1 : XXXA_DDDD_n or GLASS_DDDD_n or PP_DDDD_n or HDPE_DDDD_n
        NSRL_1  : XXXA_SPrc or XXXA_REFn or EMPTY_....
        XXX = LS concentration in percent
        A = antioxidant concentration
        DDDD = gamma dose in Gray (variable length string)
        n = sample number
        S = NSRL irradiation session
        P = F or R for Front or Rear
        rc = row,column in HDPE holder
        REF = reference sample
        Samples match if they share the same capitialized letters and underscores in same place
        '''
        s = None
        if self.mergeType=='Gamma_1':
            u1 = sample1.find('_')
            s = 'XXXA_'
            if u1>-1 : s = sample1[:u1+1]
        if self.mergeType=='NSRL_1' : s = 'XXXA_SP'
        if s is None: return False,''
        
        n = len(s)
        u = s.find('_')
        suffix = ''
        nMatch = False
        if self.mergeType=='NSRL_1':
            nMatch,suffix = self.matchNSRL14C(sample1,sample2)
        if suffix=='' and not nMatch: 
            nMatch = sample1[:n]==sample2[:n]
        uMatch = sample1[u]==sample2[u]
            
        # define common sample name, taking into account special treatment
        # for different exposures.
        # Deal with variable length string in gamma exposure sample names
        commonSampleName = None
        dMatch = False
        d1 = d2 = None
        if nMatch and uMatch:
            if self.mergeType=='NSRL_1':
                commonSampleName = sample1[:n]
                if suffix!='': commonSampleName = sample1[:4] + '_'+suffix
                dMatch = True
                if sample1[5:8]=='REF' : commonSampleName = sample1[:8]
                if sample1[:5]=='EMPTY': commonSampleName = 'EMPTY'
            if self.mergeType=='Gamma_1':
                if sample1[:5]==sample2[:5]=='EMPTY':
                    commonSampleName = 'EMPTY'
                    dMatch = True
                else:
                    d1 = sample1.split('_')[1]
                    d2 = sample2.split('_')[1]
                    dMatch = d1==d2
                    commonSampleName = sample1[:n] + d1
        if 0: print 'ls6500.matchSamples: sample1,sample2',sample1,sample2,\
           'nMatch,uMatch',nMatch,uMatch,dMatch,'d1,d2',d1,d2,'commonSampleName',commonSampleName,'mergeType',self.mergeType
        return (nMatch and uMatch and dMatch),commonSampleName
    def defineMatchingSamples(self):
        '''
        define map of common samples with key=common sample name and values=list of sample names
        '''
        debugDMS = True
        listOfSamples = sorted( self.sampleMsmts.keys() )

        for i1,sample1 in enumerate(listOfSamples):
            i2 = i1+1
            while i2<len(listOfSamples):
                sample2 = listOfSamples[i2]
                ok,name = self.matchSamples(sample1,sample2)
                if ok:
                    if name not in self.matchingSamples: self.matchingSamples[name] = []
                    if sample1 not in self.matchingSamples[name]: self.matchingSamples[name].append(sample1)
                    if sample2 not in self.matchingSamples[name]: self.matchingSamples[name].append(sample2)
                i2 += 1
        if debugDMS:
            print 'ls6500.defineMatchingSamples','\nName : Samples'
            namesOfSamples = sorted( self.matchingSamples.keys() )
            for name in namesOfSamples:
                l = self.matchingSamples[name]
                print name,':',','.join(x for x in l)
        return
    def fillSampleMsmts(self):
        '''
        fill sampleMsmts = map of samples to list of measurements
        Special treatment for empty vials
        '''
        l0 = len(self.sampleMsmts)
        for pn in self.vialPosition:
            sample = samName = self.vialPosition[pn]
            if samName.upper()=='EMPTY' : sample = samName + '_' + pn.replace(' ','_')
            #print 'ls6500.fillSampleMsmts: pn',pn,'samName',samName,'sample',sample
            if pn in self.vialMsmts:
                lfm    = self.vialMsmts[pn]
                if sample not in self.sampleMsmts:
                    self.sampleMsmts[sample] = []
                self.sampleMsmts[sample].extend( lfm )
        l1 = len(self.sampleMsmts)
        print 'ls6500.fillSampleMsmts: initial,final sampleMsmts length',l0,',',l1
        if l1>0:
            print 'ls6500.fillSampleMsmts: Samples in fillSampleMsmts',
            for sample in sorted( self.sampleMsmts.keys() ): print sample,
            print ''
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
            if checkPrint: print 'ls6500.processHeader: row',row
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
        '''
        True if file is summary file.
        Check filesize as a quick proxy.
        Verify by opening and reading files below max size for summary file
        '''
        explanation = ''
        sz = os.path.getsize(fn)
        if sz>self.maxSizeForSummaryFile: return False, explanation

        explanation = 'zero-length'
        if sz==0: return True, explanation

        explanation = 'summary'
        self.ssr.open(fn)
        s = self.ssr.getSheet(0)
        words = self.ssr.getRowColContents(s,row=0,col=0)
        #print 'fn',fn,'words',words
        if u'Instrument Type'==words: return True, explanation
        explanation = 'unknown'
        return False, explanation
        
    def matchVialMeas(self,checkPrint=False):
        '''
        fill map(key=position,value= list of files with measurements of position)
        reject non-.xls files
        reject .xls files that are summary files
        reject and tally `bad` .xls files (bad = zero-length)
        '''
        dataFileNames = os.listdir(self.dataDir)
        goodFiles = [] # temporary list
        badFiles  = []
        for fn in dataFileNames:
            #print 'fn',fn
            if '.xls' in fn:
                isSF, explanation = self.isSummaryFile(self.dataParentDir + self.dataSubDir + fn)
                if isSF :
                    print 'ls6500.matchVialMeas: remove',explanation,'file',fn,'from list'
                    if explanation.lower()=='zero-length': badFiles.append(self.dataSubDir + fn)
                else:
                    goodFiles.append(self.dataSubDir + fn)
        dataFileNames = goodFiles 
        dataFileNames.sort()
        # assign file(s) to vial position
        j = 0
        for fn in dataFileNames:
            j = j%len(self.vialPositionOrder)
            pn = self.vialPositionOrder[j]
            if pn in self.vialMsmts:
                self.vialMsmts[pn].append(fn)
            else:
                self.vialMsmts[pn] = [fn]
            j += 1
        # compute adjustment for bad files
        badFiles.sort()
        badFilesMeasNo = []
        for bfn in badFiles: badFilesMeasNo.append( self.getMeasNo(bfn) )
        for fn in dataFileNames:
            measNo = self.getMeasNo(fn)
            nbad = 0
            for bmn in badFilesMeasNo:
                if bmn<measNo: nbad += 1
            self.badFileAdjustment[fn] = nbad
        # check what we did
        print 'ls6500.matchVialMeas: number of bad files found',len(badFiles)
        for nBad in range(len(badFiles)):
            nAdj = nBad + 1
            if nAdj>0:
                fnList = []
                for fn in self.badFileAdjustment:
                    if self.badFileAdjustment[fn]==nAdj: fnList.append(fn)
                print 'ls6500.matchVialMeas: adjustment=',nAdj,'for files',', '.join(map('{0}'.format,[a for a in fnList]))
        if checkPrint:
            print '{0:>20} {1:>15} {2}'.format('Position','Sample','Measurements')
            for pn in self.vialPositionOrder:
                sn = self.vialPosition[pn]
                dfn = []
                if pn in self.vialMsmts: dfn = self.vialMsmts[pn]
                print '{0:>20} {1:>15} {2}'.format(pn,sn,dfn)
        return
    def getMeasNo(self,fn):
        return int(fn.split('MeasurementNo')[1].replace('.xls',''))
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
        
    def getMeasurement(self,fn,positionNumber=None,numNoVial=0,performChecks=True,badFileAdj=0):
        '''
        return header info and list of bin,contents from sheet 0 in file name fn
        perform checks on sheet contents, file name and positionNumber
        '''
        isheet = 0
        debug = False
        
        self.ssr.open(fn)
        name,date,totalCounts,ADC = self.ssr.unpackSheet(isheet)
        if debug: print 'ls6500.getMeasurement: name',name,'date',date,'totalCounts',totalCounts
        if name is None:
            w = 'ls6500.getMeasurement: ERROR Failure with file ' + fn
            sys.exit(w)
            
        s = self.ssr.getSheet(isheet)
        samnum, rackpos, exposuretime = self.getSRpT(s)
        if debug: print 'ls6500.getMeasurement: samnum',samnum,'rackpos',rackpos,'exposuretime',exposuretime
        if performChecks:
            # check measurement number in file name against sample number
            # an adjustment is made for the existence of a summary file for each lap
            # an adjustment may be made for bad files
            measNo = int(fn.split('MeasurementNo')[1].replace('.xls',''))
            L = len(self.vialOrder)
            if samnum!=((measNo-badFileAdj)%(L+1))+numNoVial :
                w = 'ls6500.getMeasurement: ERROR Msmt# ' + str(measNo-badFileAdj) \
                    + '%(' + str(L+1) + ')' \
                    + ' in filename not equal to samplenumber in file ' + str(samnum) \
                    + ' for numNoVial ' + str(numNoVial) + ' for badFileAdj ' + str(badFileAdj)
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
        if sample[0:3] in ['005','010','014']: thres = 1000.
        if sample[0:3]=='STD': thres = 2000.
        return thres
    def Analyze(self):
        '''
        produce histograms for each measurement.
        20141103 Change from position to sample name as index
        g = graph of crossing-point vs time for each sample
        n = normed cross-point vs time (norm to 1st entry in time)
        c = counts vs time for each sample
        k = K-S test wrt earliest entry vs time for each sample
        a = averaged crossing-point vs time (norm to average of all entries)
        Q = average(in time) of combination of `matching` samples vs time
        D = average(in time) of combination of matching samples vs dose
        R = normed average(in time) of combination of matching samples vs time (norm to 1st averaged entry)
        X = ratio of average(in time) of combination of matching samples to reference sample vs time
        '''
        debugMG = False
        doKS    = False
        plotKS  = False
        
        print 'ls6500.Analyze'
        Hists = {}
        Graphs= []
        MultiGraphs = {}
        kinds = self.kindsOfSamples()
        if 1 or debugMG: print 'ls.Analyze: kinds',kinds
        part1, part2 = ['', 'n', 'c', 'a','Q','D','R','X'], ['g', 'n', 'c', 'a','Q','D','R', 'X']
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
                if debugMG: print 'MultiGraphs make map for kind',kind,'p1',p1,'p2',p2

        self.dtHist = TH1D('dtHist','Time between common sample measurements in hours',1000,0.,1000.)
        self.dtNear = TH1D('dtNear','Nearest time between common sample measurements in hours',100,0.,100.)

        # make histograms of raw data (counts vs channel #) for each measurement
        # and graphs of total counts vs time for each sample.
        # (datetime object 'date' must be converted to root-happy object)
        print 'histogramming samples',
        for sample in self.sampleMsmts:
            print sample,
            T,C = [],[]
            for fn in self.sampleMsmts[sample]:
                date,totalCounts,exposureTime,ADC = self.vialData[fn]
                T.append ( TDatime( date.strftime('%Y-%m-%d %H:%M:%S') ).Convert() )
                C.append( float(totalCounts) )
                title = sample + ' ' + date.strftime('%Y%m%d %H:%M:%S')
                name = self.nameHist(fn)
                #print 'title',title,'name',name
                nx = len(ADC)
                xmi = -0.5
                xma = xmi + float(nx)
                Hists[name] = TH1D(name,title,nx,xmi,xma)
                for x,y in ADC: Hists[name].Fill(x,y)
            title = sample + ' total counts'
            name = 'c' + sample
            g = self.makeTGraph(T,C,title,name)
            kind = 'c' + self.getKind(title)
            self.addNewGraph(g,Graphs,kind,MultiGraphs,' total counts')
        print ''
                
        # perform root's KS test to compare first msmt with others of same sample
        # optionally plot results vs time difference
        if doKS:
            for sample in self.sampleMsmts:
                i = 0
                fn1 = self.sampleMsmts[sample][i]
                name1 = self.nameHist(fn1)
                date1 = self.getTimeOfMeasurement(fn1)
                h1 = Hists[name1]
                print sample,name1.split('_')[0],
                T, KS = [], []
                for j in range(i+1,len(self.sampleMsmts[sample])):
                    fn2 = self.sampleMsmts[sample][j]
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
                    title = sample + ' KS test vs time difference in hours'
                    g = self.makeTGraph(T,KS,title,name)
                    kind = 'k' + self.getKind(title)
                    self.addNewGraph(g,Graphs,kind,MultiGraphs,' KS test vs time diff in hrs')
                                
        # plot data from multiple hists or tgraphs
        for sample in self.sampleMsmts:
            hlist = []
            for fn in self.sampleMsmts[sample]:
                hlist.append( Hists[self.nameHist(fn)] )
            self.multiPlot(hlist) # overlay multiple hists

            thres = self.setThres(sample,defaultThres = 200.)
            tg,ntg,atg = self.xPoint(hlist,thres=thres) # crossing point from multiple hists vs time
            htg = self.histGraph(tg)  # histogram of crossing points
            Hists[htg.GetName()] = htg
            
            kind = self.getKind( tg.GetTitle() )
            self.addNewGraph(tg,Graphs,kind,MultiGraphs,' thres='+str(thres))

            kind = 'n' + kind
            self.addNewGraph(ntg,Graphs,kind,MultiGraphs,' thres='+str(thres))

            if atg is not None:
                kind = 'a' + self.getKind( atg.GetTitle() )
                self.addNewGraph(atg,Graphs,kind,MultiGraphs,' thres='+str(thres))
                
        self.combineCommonSamples(Graphs, MultiGraphs)
        self.plotSampleVsDose(Graphs)
        self.doseGraphs(Graphs, MultiGraphs) # only for gamma
        self.ratioToRef(Graphs, MultiGraphs,keyBlah='_Irr') # ratio of each (time-averaged) sample to approprate reference sample

        # output of hists, graphs.
        # processing of multigraphs
        outname = self.histFile
        outfile = TFile(outname,'RECREATE')
        outfile.WriteTObject( self.dtHist )
        outfile.WriteTObject( self.dtNear )
        for h in Hists: outfile.WriteTObject( Hists[h] )
        for tg in Graphs: outfile.WriteTObject( tg )
        if debugMG: print 'MultiGraphs',MultiGraphs,'\n'
        for kind in MultiGraphs:
            if debugMG: print 'kind',kind,'MultiGraphs[kind]',MultiGraphs[kind]
            if MultiGraphs[kind].GetListOfGraphs():  # not empty
                self.multiGraph(MultiGraphs[kind])
                self.multiGraph(MultiGraphs[kind],restrictAbscissa=True)
                if kind[0] in ['n','R']:
                    self.multiGraph(MultiGraphs[kind],ordinateRange=0.1)
                    self.multiGraph(MultiGraphs[kind],ordinateRange=0.1,restrictAbscissa=True)
                outfile.WriteTObject( MultiGraphs[kind] )
        outfile.Close()
        print 'ls6500.Analyze: Wrote hists to',outname
        return
    def getGraph(self,name,gList):
        '''
        return graph from gList given name
        '''
        for g in gList:
            if name==g.GetName(): return g
        return None
    def doseGraphs(self,Graphs,MultiGraphs):
        '''
        Compare normed dose of liquid samples with normed dose of PP vials
        `D` =  prefix of multigraphs 
        `e` = prefix for dose graphs
        Only valid for Gamma_1 merged analysis
        '''
        if self.mergeType != 'Gamma_1' : return

        sList = ['0050', '0052', '0100', '0102','GLASS']
        A = ['PP']
        A.extend(sList)
        for i,sample in enumerate(A):
            gname  = 'e' + sample
            g = self.getGraph(gname,Graphs)
            self.color(g,i)
            c = g.GetLineColor()
            g.SetMarkerColor(c)
        # compare all dose graphs to PP
        gpp = self.getGraph('ePP',Graphs)
        for sample in sList:
            mgname = 'D' + sample
            mg = MultiGraphs[mgname]
            mg.Add(gpp)
            mg.Add(self.getGraph('e'+sample,Graphs))
        return
    def getDose(self,name):
        '''
        return nominal dose in Gray given sample name
        '''
        if self.mergeType == 'Gamma_1':
            dose = name.split('_')[1]
        elif self.mergeType =='NSRL_1':
            # initialize if necessary
            if len(self.NSRL14Cdoses)<1: self.setNSRL14Cdoses()
            dose = 0.
            if name in self.NSRL14Cdoses:
                dose = self.NSRL14Cdoses[name]
        else:
            dose = None
        print 'ls6500.getDose:name',name,'dose',dose
        return dose
    def plotSampleVsDose(self,Graphs):
        '''
        plot sample light yield vs dose taking into account the irradiation date for
        combined, average measurements
        Treat measurements of samples prior to irradiation date as having received no dose
        '''
        for cSN in self.matchingSamples:
            sam = self.parseSam(cSN)
            kind = 'D' + sam
            gSN = 'A' + sam
            lgk = len(gSN)
            if 0: print 'ls6500.plotSampleVsDose: cSN',cSN,'sam',sam,'kind',kind,'gSN',gSN
            x,y,dx,dy = [],[],[],[]
            z,dz = [],[] # zero dose data
            for g in Graphs:
                if 0: print 'ls6500.plotSampleVsDose: g.GetName()',g.GetName()
                if gSN==g.GetName()[:lgk] and ('_' in g.GetName()):
                    d = self.getDose(g.GetName()) # g.GetName().split('_')[1]
                    try:
                        dose = float(d)
                        u,v,du,dv = self.getPoints(g,getErrors=True)
                        for i,t in enumerate(u):
                            d = dose
                            if t<self.irradDate_TDatime or dose<0.1:
                                d = 0.
                                z.append(v[i])
                                dz.append(dv[i])
                            x.append(d)
                            dx.append(0.) # no uncertainty on dose
                            y.append(v[i])
                            dy.append(dv[i])
                    except ValueError:
                        print 'ls6500.plotSampleVsDose: WARNING No dose for graph',g.GetName()
            if len(x)>0:
                wtd_avg = self.getWeightedAvg(z,dz)
                reorder = [a for b,a in sorted(zip(x,range(len(x))))] # sort by dose
                u,v,du,dv = [],[],[],[]
                vN,dvN = [],[]
                R = float(len(reorder))
                for j in reorder:
                    d = max(1.,x[j])
                    abit = (float(j)/R-0.5)*.05*d # displace points slightly
                    u.append(x[j]+abit)
                    du.append(dx[j])
                    v.append(y[j])
                    dv.append(dy[j])
                    if wtd_avg>0:
                        vN.append(y[j]/wtd_avg)
                        dvN.append(dy[j]/wtd_avg)
                name = 'd'+sam
                newg = self.makeTGraph(u,v,sam+' vs dose',name,ex=du,ey=dv)
                newg.SetMarkerStyle(20)
                Graphs.append(newg)
                name = 'e'+sam
                if len(vN)>0:
                    #print 'name',name,'#points',len(u)
                    newg = self.makeTGraph(u,vN,sam+' vs dose (normed to 0 dose)',name,ex=du,ey=dvN)
                    newg.SetMarkerStyle(20)
                    Graphs.append(newg)
            
                
        return
    def getWeightedAvg(self,x,dx):
        wsum,wxsum = 0., 0.
        for a,da in zip(x,dx):
            w = 1.
            if da>0.: w = 1./da/da
            wsum += w
            wxsum += w*a
        if wsum>0.: wxsum = wxsum/wsum
        return wxsum
    def ratioToRef(self,Graphs,MultiGraphs,keyBlah=''):
        '''
        take ratio of averaged sample response to appropriate reference sample
        First make list of reference graphs for averaged response
        Then, for each reference graph, take the ratio with the appropriate samples.
        The name of the appropriate samples must contain the string keyBlah
        '''
        refGraphs = []
        for g in Graphs:
            name = g.GetName()
            if name[0]=='A':  # averages
                if 'REF' in name:
                    if g in refGraphs:
                        print 'ls.ratioToRef: WARNING Found same reference graph to graph named',name
                    else:
                        refGraphs.append(g)
        for refG in refGraphs:
            refName = refG.GetName()
            kind = 'X' + refName[1:5]
            xref,yref,dxref,dyref = self.getPoints(refG,getErrors=True)
            for g in Graphs:
                name = g.GetName()
                if g!=refG and name[:5]==refName[:5] and (keyBlah in name):
                    x,y,dx,dy = self.getPoints(g,getErrors=True)
                    hours = 6.
                    u,v,du,dv = self.makeRatio(xref,yref,dxref,dyref, x,y,dx,dy, maxSep=hours*60.*60.)
                    if 0: print 'ls6500.ratioToRef: ref,pts=',refName,len(xref),'graph,pts=',name,len(x),'ratio pts',len(u)
                    if len(u)>0:
                        newName = name.replace('A','N')
                        newTitle= 'Ratio of ' + name + ' to ' + refName + ' max time diff ' + str(hours) + ' hrs'
                        newg = self.makeTGraph(u,v,newTitle,newName,ex=du,ey=dv)
                        self.addNewGraph(newg,Graphs,kind,MultiGraphs,'Ratio of avg over time to REF. Max time diff '+str(hours)+' hrs')
        return
    def makeRatio(self,xref,yref,dxref,dyref, x,y,dx,dy, maxSep=6.*60.*60.):
        '''
        return ratio between a sample and reference sample for all measurements
        within maxSep seconds
        '''
        u,v,du,dv = [],[],[],[]
        #print 'xref:',self.pList(xref,xref[0],c=60.*60.)
        #print 'x   :',self.pList(x,xref[0],c=60.*60.)
        for i,a in enumerate(x):
            val = min(xref, key=lambda q : abs(a-q))
            #print 'i,a,val,maxSep',i,a,val,maxSep
            if abs(val-a)<=maxSep:
                j = xref.index(val)
                q = 0.5*(val+a)
                dq= 0.5*abs(val-a)
                r = y[i]/yref[j]
                dr= r*math.sqrt( dy[i]*dy[i]/y[i]/y[i] + dyref[j]*dyref[j]/yref[j]/yref[j])
                u.append(q)
                du.append(dq)
                v.append(r)
                dv.append(dr)
        return u,v,du,dv
    def combineCommonSamples(self,Graphs, MultiGraphs):
        '''
        make new graphs of averaged crossing point data from input list of
        graphs.
        also make new graphs of averaged crossing point data normed to earliest averaged entry.
        The new graphs are appended to the end of the input list.
        New graphs are also added to multigraphs
        '''
        debug = False
        oneHour = 60.*60. 


        for cSN in self.matchingSamples:
            gList = []
            pS = self.parseSam(cSN)
            kind = 'Q' + pS
            rkind= 'R' + pS
            for SN in self.matchingSamples[cSN]:
                #print 'SN',SN
                gSN = 'g'+SN
                lgSN = len(gSN)
                for tg in Graphs:
                    #print 'tg.GetName()',tg.GetName()
                    if tg.GetName()[:lgSN]==gSN:
                        gList.append(tg)
                        break
            if len(gList)!=len(self.matchingSamples[cSN]):
                print 'ls6500.combineCommonSamples: Could not find all graphs for',cSN,\
                      '#graphs=',len(gList),'#samples',len(self.matchingSamples[cSN])
            if len(gList)==0:
                print 'ls6500.combineCommonSamples: No graphs found for',cSN,'samples are',', '.join([x for x in self.matchingSamples[cSN]])
            else:
                print 'ls6500.combineCommonSamples:',cSN,'graphs',', '.join([g.GetName() for g in gList])
                # extract data points for all graphs, then sort them in time order
                x,y = [],[]
                for g in gList:
                    u,v = self.getPoints(g)
                    x.extend(u)
                    y.extend(v)

                Q = sorted(zip(x,y))
                u = [a for a,b in Q]
                v = [b for a,b in Q]
                for i in range(len(u)-1):
                    dt = u[i+1]-u[i]
                    self.dtHist.Fill(dt/oneHour)  # hours between measurements
                    if i>0: dt = min(dt,u[i]-u[i-1])
                    self.dtNear.Fill(dt/oneHour)  # smallest time (hours) between neighboring measurements
                hours = 24.
                x,dx,y,dy = self.averagePoints(u,v,deltaT=hours*oneHour)
                if 0: print 'ls6500.combineCommonSamples: \nu-x[0](hours)=',self.pList(u,x[0],c=oneHour),'v=',self.pList(v,0.),\
                   '\nx-x[0](hours)=',self.pList(x,x[0],c=oneHour),'dx=',self.pList(dx,0.,c=oneHour),\
                   '\ny=',self.pList(y,0.),'dy=',self.pList(dy,0.)
                newg = self.makeTGraph(x,y,cSN + ' ' + str(hours)+ ' hour avg','A'+cSN,ex=dx,ey=dy)
                self.addNewGraph(newg, Graphs, kind,MultiGraphs,' ave over '+str(hours)+' hrs')

                # average normed to earliest entry
                y0 = y[0]
                y = [float(a)/float(y0) for a in y]
                dy= [float(a)/float(y0) for a in dy]
                newg = self.makeTGraph(x,y,cSN + ' normed ' + str(hours) + ' hr avg','B'+cSN,ex=dx,ey=dy)
                self.addNewGraph(newg,Graphs,rkind,MultiGraphs,' normed avg over '+str(hours)+' hrs')
                 
        return
    def addNewGraph(self,g,Graphs,kind,MultiGraphs,titleSuffix,fixTime=True):
        '''
        for input graph g:
        set marker style, fix time display (optional), append to list of Graphs, set line color
        add to multigraph, set multigraph title, 
        '''
        debug = False
        
        g.SetMarkerStyle(20)
        if fixTime: self.fixTimeDisplay(g)
        Graphs.append(g)
        if kind is not None:
            if kind in MultiGraphs:
                MGs = MultiGraphs[kind]
                MGs.Add(g)
                if MGs.GetTitle()==MGs.GetName():
                    MGs.SetTitle( MGs.GetName() + titleSuffix)
                ng = MGs.GetListOfGraphs().GetSize()
                self.color(g,ng)

        if debug:
            words = 'ls6500.addNewGraph: '+g.GetName()
            if kind is not None: words += ' kind '+kind+' titleSuffix '+titleSuffix +' fixTime='+str(fixTime)
            print words

        return
    def pList(self,u,u0,c=1.):
        '''
        compact format for printing list of floats with respect to reference with optional normalization
        '''
        return ', '.join(map('{0:.2f}'.format,[(a-u0)/c for a in u]))
    def averagePoints(self,u,v,deltaT=24.*60.*60.):
        '''
        return average,RMS of ordinate and average,halfwidth of abscissa
        given time-ordered abscissa in intervals of deltaT
        '''
        debug = False
        x,dx,y,dy = [],[],[],[]
        i1 = 0
        t2 = u[0]+deltaT
        ay,sy,ax = 0.,0.,0.
        n = 0
        for i in range(len(u)):
            t = u[i]
            if t>t2 or i==len(u)-1:
                if n>0:
                    ay = ay/float(n)
                    ax = ax/float(n)
                    if n>1: sy = math.sqrt(float(n)/float(n-1)*(sy/float(n) - ay*ay))
                    else:   sy = 0.
                    sx = (u[i2]-u[i1])/2.
                    x.append(ax)
                    dx.append(sx)
                    y.append(ay)
                    dy.append(sy)
                    if debug : print 'ls6500.averagePoints:i,n,ax,ay',i,n,ax,ay,'sx,i1,i2',sx,i1,i2
                    ay,sy,ax = v[i],v[i]*v[i],u[i]
                    i1 = i2 = i
                    n = 1
                t2 = t+deltaT
            else:
                ax += u[i]
                ay += v[i]
                sy += v[i]*v[i]
                n  += 1
                i2 = i
        return x,dx,y,dy
    def getPoints(self,g,getErrors=False):
        '''
        return abscissa,ordinate values of input graph g
        also return errors if getErrors is True
        '''
        x,y = [],[]
        if getErrors: dx,dy = [],[]
        for i in range(g.GetN()):
            a,b = ROOT.Double(0),ROOT.Double(0)
            OK = g.GetPoint(i,a,b)
            if OK!=-1:
                x.append(a)
                y.append(b)
                if getErrors:
                    dx.append(g.GetErrorX(i))
                    dy.append(g.GetErrorY(i))
        if getErrors: return x,y,dx,dy
        return x,y
    def histGraph(self,g):
        '''
        return gaussian-fitted histogram from ordinate values from graph g
        '''
        name = g.GetName()
        title= g.GetTitle()
        np   = g.GetN()
        y = []
        for i in range(np):
            a,b = ROOT.Double(0),ROOT.Double(0)
            OK = g.GetPoint(i,a,b)
            if OK!=-1 : y.append(b)
        if len(y)!=np: print 'ls.histGraph: WARNING length of obtained points',len(y),'not equal number of points',np,'for graph name',name,'title',title
        ymi = min(y)
        yma = max(y)
        dy = (yma-ymi)/2
        #print 'ymi',ymi,'yma',yma,'dy',dy,'y',y
        ymi -= dy
        yma += dy
        n = max(10,int(len(y)/4))
        #print 'ymi',ymi,'yma',yma,'n',n
        name = 'H' + name
        title= 'Hist of ordinate of ' + title
        h = TH1D(name,title,n,ymi,yma)
        for b in y: h.Fill(b)
        h.Fit("gaus","LQ")
        return h
    def xint(self,x1,y1,x2,y2,yt):
        dx = x2-x1
        if dx==0. : return x1
        m = (y2-y1)/dx
        if m==0. : return (y1+y2)/2.
        b = y2 - m*x2
        return (yt-b)/m
    def makeTGraph(self,u,v,title,name,ex=None,ey=None):
        if ex is None:
            g = TGraph(len(u),array('d',u), array('d',v))
        else:
            dy = ey
            if ey is None: dy = [0. for x in range(len(ex))]
            g = TGraphErrors(len(u),array('d',u),array('d',v),array('d',ex),array('d',dy))
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
    def getDateFromTitle(self,title):
        s = title.split()
        for i,e in enumerate(s):
            if e.count(':')==2:
                return datetime.datetime.strptime(s[i-1] + ' ' + s[i],'%Y%m%d %H:%M:%S')
        return None
    def xPoint(self,hlist,thres=100., maxchan=1000):
        '''
        Return TGraph of crossing-point for multiple hists.
        Return TGraph of crossing-point for multiple hists normalized to first point.
        Return Tgraph of crossing-point for multiple hists normalized by average.
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
            #s = h.GetTitle().split()
            date = self.getDateFromTitle(h.GetTitle()) #datetime.datetime.strptime(s[2]+' '+s[3],'%Y%m%d %H:%M:%S')
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
        atg= None
        if len(Y)>0:
            ave = float(sum(Y))/float(len(Y))
            if ave!=0.:
                aY = [q/ave for q in Y]
                atg = self.makeTGraph(X,aY,title + ' wrt average','a'+sample)
        for g in [tg, ntg, atg]:
            if g is not None:
                g.SetMarkerStyle(20)
                self.fixTimeDisplay(g)
        return tg,ntg,atg
    def fixTimeDisplay(self,g):
        '''
        set time axis to display nicely
        Add vertical dashed lines showing irradiation interval
        '''
        if g:
            g.GetXaxis().SetTimeDisplay(1)
            g.GetXaxis().SetTimeFormat("#splitline{%H:%M}{%y/%m/%d}")
            g.GetXaxis().SetNdivisions(-409)
            #lx = g.GetXaxis().GetLabelSize()
            g.GetXaxis().SetLabelSize(0.025) #0.5*lx)
            g.GetXaxis().SetTimeOffset(0,"gmt") # using gmt option gives times that are only off by 1 hour on tgraph
            self.drawIrradInterval(g)
        else:
            print 'ls6500.fixTimeDisplay: WARNING Null pointer passed to fixTimeDisplay?????'
        return
    def setSamName(self,h0):
        '''
        get unique sample name from histogram title
        '''
        w = h0.GetTitle().split()
        sample = w[0]
        if 'EMPTY' in sample: sample += '_' + w[1]
        return sample
    def multiGraph(self,TMG,truncT=30,ordinateRange=None,restrictAbscissa=False):
        '''
        draw TMultiGraph with legend and output as pdf
        Default is that abscissa is calendar time.
        truncT is the number of initial characters in title to use in legend
        if ordinateRange is a float, then set ordinate range to 1+-ordinateRange.
        if restrictAbscissa is True, restrict abscissa range to nearby times
        
        '''
        debugMG = False
        if not TMG.GetListOfGraphs(): return  # empty
        title = TMG.GetTitle()
        name  = TMG.GetName()
        if debugMG: print 'ls6500.multiGraph',title,name,'TMG.GetListOfGraphs()',TMG.GetListOfGraphs(),'TMG.GetListOfGraphs().GetSize()',TMG.GetListOfGraphs().GetSize()

        abscissaIsTime = True
        if name[0] in ['k','D'] : abscissaIsTime = False

        suffix = ''
        if type(ordinateRange) is float: suffix += '_ordRange_'+str(ordinateRange).replace('.','_')
        if restrictAbscissa and abscissaIsTime: suffix += '_restrictTime'

        pdf = self.figuresDir + name + suffix + '.pdf'
        ps  = self.figuresDir + name + suffix + '.ps'
        xsize,ysize = 1100,850 # landscape style
        noPopUp = True
        if noPopUp : gROOT.ProcessLine("gROOT->SetBatch()")
        canvas = TCanvas(pdf,title,xsize,ysize)
        x1 = 0.90
        x2 = x1 + 0.1
        y1 = 0.12
        y2 = y1 + 0.5
        lg = TLegend(x1,y1,x2,y2) #.15,.15, .3,.35)
        for g in TMG.GetListOfGraphs():
            t = g.GetTitle()
            if truncT>0: t = t[:min(len(t),truncT)]
            lg.AddEntry(g, t, "l" )
            if abscissaIsTime : self.fixTimeDisplay(g)
        dOption = "apl"
        if name[0]=='D': dOption = "ap"
        TMG.Draw(dOption)
        if type(ordinateRange) is float:
            ymi = 1. - abs(ordinateRange)
            yma = 1. + abs(ordinateRange)
            TMG.GetYaxis().SetRangeUser(ymi,yma)
        if restrictAbscissa:
            XMI,XMA = TMG.GetXaxis().GetXmin(), TMG.GetXaxis().GetXmax()
            if self.irradNearbyTDatime is None:
                self.irradNearbyTDatime = [self.getTDatime(self.irradNearby[0]), self.getTDatime(self.irradNearby[1])]
            xmi,xma = self.irradNearbyTDatime
            TMG.GetXaxis().SetRangeUser(xmi,xma)
        self.fitLegend(TMG)
        if abscissaIsTime : self.fixTimeDisplay(TMG)
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
        if restrictAbscissa: TMG.GetXaxis().SetRangeUser(XMI,XMA) # restore abscissa. is this needed?
        return
    def fitLegend(self,graph,f=0.10):
        '''
        stretch x-axis on graph to make room for legend
        '''
        if not graph: return
        xaxis = graph.GetXaxis()
        if not xaxis: return
        xmi,xma = xaxis.GetXmin(),xaxis.GetXmax()
        vmi = xmi
        vma = xma + f*(xma-xmi)
        xaxis.SetRangeUser(vmi,vma)
        return
        
    def drawIrradInterval(self,graph):
        '''
        indicate when irradiation was done on graph of quantity (e.g. light yield) vs time
        Does not work.....Why?
        '''
        if 0: print 'ls6500.drawIrradInterval: graph',graph
        if not graph: return # no graph
        xaxis = graph.GetXaxis()
        if not xaxis: return # no axis defined
        xmi = xaxis.GetXmin()
        xma = xaxis.GetXmax()
        if self.irradIntervalTDatime is None:
            self.irradIntervalTDatime = [self.getTDatime(self.irradInterval[0]), self.getTDatime(self.irradInterval[1])]
        tmi = self.irradIntervalTDatime[0]
        tma = self.irradIntervalTDatime[1]
        if 0: print 'ls6500.drawIrradInterval: tmi,tma',tmi,tma,'xmi,xma',xmi,xma
        if (xmi<=tmi and tmi<=xma) or (xmi<=tma and tma<=xma) : # interval within limits
            ymi = graph.GetYaxis().GetXmin()
            yma = graph.GetYaxis().GetXmax()
            lmi = TLine(tmi,ymi,tmi,yma)
            lma = TLine(tma,ymi,tma,yma)
            lmi.SetLineStyle(2) # dashed
            lma.SetLineStyle(2) # dashed
            lmi.SetLineColor(2) # red
            lma.SetLineColor(4) # blue
            lmi.Draw()
            lma.Draw()
            if 0: print 'ls6500.drawIrradInterval: graph,tmi,ymi,tma,yma=',graph,tmi,ymi,tma,yma,'lmi,lma',lmi,lma
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
            ##print 'keyTitle:', t,
            d = h.GetTitle()
            if len(t)>=4:
                d = t[2] + ' ' + t[3]
            ##print d
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
                            if pn in self.vialMsmts: vM[pn].extend(self.vialMsmts[pn])
                    else:
                        # new position. add to maps if measurements were actually made
                        if pn in self.vialMsmts: 
                            vP[pn] = self.vialPosition[pn]
                            vM[pn] = self.vialMsmts[pn]
        # done transferring data to local dicts, now clear global dicts
        # and fill them
        self.vialPosition = vP
        self.vialMsmts    = vM
        self.vialData     = vD
        print '\n *** merge complete *** \n'
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
            print 'ls6500.putOrGet: unpickling...be patient. file',fn
            obj = pickle.load(f)
            self.vialPosition, self.vialOrder, self.vialPositionOrder, self.vialMsmts, self.vialData = obj
            self.fillSampleMsmts()
            f.close()
            print 'ls6500.putOrGet: pickled data read from',fn
        else:
            w = 'ls6500.putOrGet: ERROR Invalid mode ' + str(mode)
            sys.exit(mode)
        return
    def parseSam(self,sample):
        '''
        parse sample name to extract type of sample.
        deal with non-numerical sample names eg. `GLASS`
        '''
        s = sample[:4]
        try:
            j = int(s)
        except ValueError:
            i = sample.find('_')
            if i<0: i = 4
            s = sample[:i]
        return s
    def kindsOfSamples(self):
        '''
        fill list with kinds of samples
        '''
        kinds = []
        for sample in self.sampleMsmts: #self.vialOrder:
            kind = self.parseSam(sample)
            #print 'ls6500.kindsOfSamples: sample',sample,'kind',kind
            if kind not in kinds:
                kinds.append(kind)
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
        kind = self.parseSam(title.split()[0])
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
                self.fillSampleMsmts()
                for pn,numNoVial in zip(self.vialPositionOrder,self.noVial):
                    if checkPrint: print 'Tray_Position',pn,'Number of `no vial` to this position',numNoVial

                    if pn in self.vialMsmts:  # protect against case where vial was never measured
                        for fn in self.vialMsmts[pn]:
                            fpath = self.dataParentDir + fn
                            badFileAdj = self.badFileAdjustment[fn]
                            if checkPrint: print 'ls6500.Main: get measurement from',fpath
                            self.vialData[fn] = date,totalCounts,exposureTime,ADC = self.getMeasurement(fpath,positionNumber=pn,numNoVial=numNoVial,badFileAdj=badFileAdj)
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
        
        self.defineMatchingSamples()
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
