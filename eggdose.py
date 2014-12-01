#!/user/bin/env python
'''
read and process egg counter data for dose per spill for NSRL14C run on 17 Nov
20141119
'''


import os
import datetime
import sys
from ROOT import TGraph, TGraphErrors, TDatime, TFile, TH1D, gROOT, TTree, AddressOf
from array import array

class eggdose():
    def __init__(self):
        self.parentDir = '/Users/djaffe/work/GIT/TECHMAT/'
        self.subDir = 'NSRL14C/jaffe_p200.dat.txt'
        self.histDir = self.parentDir + 'Histograms/'

        gROOT.ProcessLine("struct MyStruct{Double_t dose; Int_t spill; Long_t dt;}:")
        self.outfile = TFile(self.histDir+'eggtree.root',"RECREATE","egg")
        self.outfile.cd()
        from ROOT import MyStruct
        self.struct = MyStruct()
        self.tree   = TTree("egg","NSRL14C egg ctr dose in cGy")
        self.tree.Branch('dose',AddressOf(self.struct,'dose'),'dose/D')
        self.tree.Branch('spill',AddressOf(self.struct,'spill'),'spill/I')
        self.tree.Branch('dt',AddressOf(self.struct,'dt'),'dt/L')
        return
    def readFile(self):
        '''
        read the data file (text format) provided in an email from Mike Sivertz
        November 17, 2014 8:16:04 PM EST
        '''
        fn = self.parentDir + self.subDir
        f = open(fn,'r')
        print 'eggdose.readFile: opened',fn
        convFac = None
        timeStamp = []
        eggData   = []
        for line in f:
            s = line.split()
            if len(s)>0:
                if s[0][0:2]=='11' : # data
                    dt = s[0]
                    tm = s[1]
                    stamp = datetime.datetime.strptime(dt +' '+ tm,'%m/%d/%Y %H:%M:%S')
                    data = float(s[2])/convFac
                    timeStamp.append(stamp)
                    eggData.append(data)
                elif s[0]=='Here' : # conversion factor for data to cGy
                    if convFac is not None:
                        words = 'eggdose.readFile: ERROR convFac=' + str(convFac) + ' already defined!?!?!'
                        sys.exit(words)
                    convFac = float(s[-1][:-1])
        f.close()
        return timeStamp,eggData
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
    def plotData(self,timeStamp,eggData):
        nx,xmi,xma = 1100/4,-1.,10.
        hi1 = TH1D('hi1','Dose(cGy)/spill during irradation#1', nx,xmi,xma)
        hi2 = TH1D('hi2','Dose(cGy)/spill during irradation#2', nx,xmi,xma)
        htun= TH1D('htun','Dose(cGy)/spill during ion chamber tuning', nx,xmi,xma)
        hno = TH1D('hno','Dose(cGy)/spill otherwise', nx,xmi,xma)
        Objs = [hi1,hi2,htun,hno]
        spillRange = [ [40,300], [375,450], [575, 1250] ]
        name = 'doseVtime'
        title = 'egg data: dose(cGy)/spill vs time'
        T = []
        S = []
        for i,date in enumerate(timeStamp):
            tobj = TDatime( date.strftime('%Y-%m-%d %H:%M:%S') ).Convert() 
            T.append( tobj )
            S.append( float(i) )
            h = hno
            if spillRange[0][0]<=i and i<=spillRange[0][1]: h = hi1
            if spillRange[1][0]<=i and i<=spillRange[1][1]: h = htun
            if spillRange[2][0]<=i and i<=spillRange[2][1]: h = hi2
            h.Fill(eggData[i])
            self.struct.dose = eggData[i]
            self.struct.spill = i
            #print 'tobj',tobj,'type(tobj)',type(tobj)
            self.struct.dt    = tobj
            self.tree.Fill()
        gT = self.makeTGraph(T,eggData,title,name)
        gT.GetXaxis().SetTimeDisplay(1)
        gT.GetXaxis().SetTimeOffset(0.,"gmt")
        gT.SetMarkerStyle(20)
        gT.SetMarkerSize(0.5)
        name = 'doseVspill'
        title = 'egg data: dose(cGy)/spill vs spill'
        gS = self.makeTGraph(S,eggData,title,name)
        gS.SetMarkerStyle(20)
        gS.SetMarkerSize(0.5)
        Objs.extend([gT,gS])
        fn = self.histDir + 'eggsalad.root'
        outfile = TFile(fn,'RECREATE')
        for o in Objs: outfile.WriteTObject( o )
        outfile.Close()
        print 'eggdose.plotData: wrote file',fn
        return
    def Main(self):
        timeStamp, eggData = self.readFile()
        self.plotData( timeStamp, eggData)
        self.outfile.cd()
        self.tree.Write()
        self.outfile.Close()
        return
if __name__ == '__main__' :
    ed = eggdose()
    ed.Main()
        
        
