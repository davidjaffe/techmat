#!/user/bin/env python
'''
read/process xls files 
'''

import sys
import xlrd
import datetime

class spreadsheetReader():

    filename = None
    workbook = None
    nsheet   = None
    sheet    = None
    fmt      = '%d %b %Y %H:%M:%S'

    def __init__(self):
        print "initialize spreadsheetReader"
        return

    def open(self,fn):
        self.filename = fn
        self.workbook =  xlrd.open_workbook(fn)
        self.nsheet = self.workbook.nsheets
        return self.workbook

    def getSheet(self,isheet):
        if isheet>=0 and isheet<self.nsheet:
            return self.workbook.sheet_by_index(isheet)
        else:
            print "getSheet: Invalid sheet number",isheet,'nsheet',self.nsheet
            return None
    def listSheets(self):
        if self.workbook is None:
            print 'spreadsheetReader.listSheets ERROR no workbook open'
            return False
        print '{0:3} {1}'.format('#','Sheet Name')
        for js in range(self.nsheet):
            s = self.getSheet(js)
            print '{0:3} {1}'.format(js,s.name)
        return True

    def printSheet(self,isheet):
        '''
        print sheet given either sheet number or sheet object
        '''
        if type(isheet) is xlrd.sheet.Sheet:
            s = isheet
        else:
            s = self.getSheet(isheet)
        for r in range( s.nrows ):
            print r, s.row_values(r)
        return True
    def findNamedSheet(self,sheetName=None):
        '''
        return sheet number corresponding to input sheetName
        case is ignored
        '''
        if sheetName is None :
            sys.exit('spreadsheetReader.findNameSheet ERROR No input sheet name')
        for js in range(self.nsheet):
            s = self.getSheet(js)
            if s.name.lower()==sheetName.lower() :
                return s
        # did not get an exact match. see if sheetName is a unique string among all sheets
        n = 0
        unique = None
        for js in range(self.nsheet):
            s = self.getSheet(js)
            if sheetName.lower() in s.name.lower() :
                unique = s
                n += 1
        if n==1 : return unique
        return None
    def getDate(self, sheet, daterow = 1, titlecol = 0, datecol = 4):
        '''
        return title with date and date for this sheet
        '''
        title = None
        date  = None
        if daterow<sheet.nrows:
            r = sheet.row_values(daterow)
            if titlecol<len(r):
                title = r[titlecol]
            if datecol<len(r): 
                date  = r[datecol]
        return title,date
    def getDateInName(self, sheet, daterow = 0, datecol = 1):
        '''
        return title and date for a certain row in this sheet
        for titles with encoded dates
        '''
        title = None
        date  = None
        if daterow<sheet.nrows:
            r = sheet.row_values(daterow)
            val = r[datecol][-6:]
            date = unicode(val).encode('utf8')
            val = r[datecol][:-7]
            title = unicode(val).encode('utf8')
        return title,date
    def getRowColContents(self,sheet, row = None, col = None):
        '''
        return contents of row,column in sheet
        '''
        contents = None
        if row<sheet.nrows:
            r = sheet.row_values(row)
            if col<len(r):
                contents = r[col]
        return contents
    def getTotalCounts(self, sheet, totalrow = 11, totalcountscol = 5):
        '''
        return total counts from sheet
        20141027 Position of total counts varies. Use column 0 to override default
        '''
        col = totalcountscol
        if self.getRowColContents(sheet,row=totalrow,col=0)==u'Total Counts:' : col = 4
        totalCounts =  self.getRowColContents(sheet, row=totalrow, col=col)
        return totalCounts
    def getChannelContents(self, sheet, headrow = 14, chanCol = 0, countsCol = 1):
        '''
        return channel # and counts from sheet
        '''
        channum,counts = [],[]
        firstrow = None
        #print 'sheet=',sheet
        if headrow<sheet.nrows:
            r = sheet.row_values(headrow)
            if chanCol<len(r) and countsCol<len(r):
                if 'Channel' in r[chanCol] and 'Counts' in r[countsCol]:
                    firstrow = headrow+2

        if firstrow is not None:
            for irow in range(firstrow,sheet.nrows):
                r = sheet.row_values(irow)
                channum.append( r[chanCol] )
                counts.append( r[countsCol] )
        return zip(channum, counts)
    def unpackSheet(self, isheet):
        '''
        get name, time and adc content (channel#,counts) from sheet
        '''
        name,dt,totalCounts,ADC = None,None,None,None
        
        s = self.getSheet(isheet)
        if s is None:
            print 'FAIL'
            return name, dt, totalCounts, ADC
        name = s.name
        title,date = self.getDate(s)
        if title is None and date is None:
            title,date = self.getDateInName(s)
        totalCounts= self.getTotalCounts(s)
        ADC = self.getChannelContents(s)
        # convert date extracted from file into datetime object
        dt = None
        if date is not None:
            dt = datetime.datetime.strptime(date,self.fmt)
            
        return name, dt, totalCounts, ADC
if __name__ == '__main__' :
    ssr = spreadsheetReader()
    args = sys.argv
    print 'args', args
    if len(args)>1:
        filename = args[1]
        wb = ssr.open(filename)
        ssr.listSheets()
        mysheet = ssr.findNamedSheet(sheetName='LS Measurement arrangement')
        if mysheet is not None:
            ssr.printSheet(mysheet)
