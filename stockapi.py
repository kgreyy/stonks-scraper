import requests
from bs4 import BeautifulSoup
import re
from datetime import date,timedelta,datetime
import os
import json

def getPageCount(page):
    '''parses page using bs4 for page count'''
    pageText = page.select_one('span.count').text
    return int(pageText[pageText.find('/')+1:pageText.find(']')])

def getAll(getter,parser,options):
    '''decorator to unify getter and parser in getting pages'''
    pageCount, page = tryGet(getter)
    data = parser(page)
    if options['cons']: # conservative stopper to return first page only
        print("Conservative mode detected. Stopping now!")
        return data
    return iterAll(getter,parser,data,pageCount)

def iterAll(getter,parser,data,pageCount):
    '''iterates over getter and parser functions called from getAll'''
    curPageNo = 2
    while curPageNo <= pageCount:
        page = getter(curPageNo)
        data.extend(parser(page))
        curPageNo+=1
    return data

def tryGet(getter):
    '''tester for getAll to catch possible errors'''
    try:
        page = getter(1)
        pageCount = getPageCount(page)
    except Exception as e:
        print('Error with init: \n'+str(e))
    else:
        print('Initialization success...\nPage count: '+str(pageCount))
    return pageCount, page

def parsePairedRows(page):
    '''parses dyad rows into tuple'''
    rows = page.select('tr')
    entries = []
    for row in rows:
        pos,name = map(lambda x: x.text.strip(), row.select('td'))
        entries.append((pos,name))
    return entries

def getPage(url):
    '''sends a get request to a url and returns BS4 object'''
    r = getResponse(url)
    return BeautifulSoup(r.content, features="html.parser")

def testGet(url):
    '''sends get request to obtain stock ticker'''
    r = getPage(url)
    try:
        return r.select_one('form > textarea').text
    except:
        return "Success!"

def makeDirs(path):
    '''makes a directory given path'''
    try:
        os.makedirs(path)
        print("Directory " +path+" created ")
    except FileExistsError:
        pass

def processConfig(varsDict):
    '''converts dictionary into URL string to configure request parameters'''
    return '?'+'&'.join([x+'='+str(y) for x,y in varsDict])

def reverseProcess(varsString):
    '''function for testing - unused but could help when debugging request URLs'''
    dictz = {}
    for x in varsString.split('&'):
        if x!='':
            a,b = x.split('=')
            dictz[a]=b
    return dictz

def dateToString(date):
    return date.strftime("%m-%d-%Y")

def stringToDate(strdate):
    return datetime.strptime(strdate,"%m-%d-%Y")

def subtractDays(date,interval):
    return date-timedelta(days=interval)

def searchReturn(strToFind,tupleList,searchIndex=None,returnIndex=None,multipleMatch=False):
    '''returns search index from list of tuples'''
    if searchIndex and returnIndex:
        print('Error: both indexes are needed!')
        return None
    if oneMatch:
        return [x for x in tupleList if x[searchIndex]==strToFind]
    for x in tupleList:
        if x[searchIndex]==strToFind:
            return x[returnIndex]
    return False

def getResponse(url):
    return requests.get(url)

class CompanyDir():
    URL = "https://edge.pse.com.ph/companyDirectory/search.ax"
    config = {'pageNo': '', 'companyId': '', 'keyword': '', 'sortType': '', 'dateSortType': 'ASC',
                  'cmpySortType': 'ASC', 'symbolSortType': 'ASC', 'sector': 'ALL', 'subsector': 'ALL'}
    options = {'cons':False}

    def __init__(self,**kwargs):
        options = kwargs.get('options',{})
        for x in options.keys():
            self.options[x]=options[x]

        print('Running with: '+str(kwargs))

        config = kwargs.get('config',self.config)
        for x in config.keys():
            self.config[x]=config[x]

        self.listing = getAll(self.getPageByNum,self.parsePage,self.options)

    def __repr__(self):
        return 'PSE Listing'

    def getPageByNum(self,num):
        self.config['pageNo']=str(num)
        print(self.config['pageNo'])
        return getPage(self.URL+processConfig(self.config.items()))

    def parsePage(self,page):
        htmlRows = page.select('tbody > tr')
        rowContents = []
        for row in htmlRows:
            rowContents.append(self.parseRow(row))
        return rowContents

    def parseRow(self,row):
        columns = row.select('td')
        hyperlink = columns[0].select_one('a')
        compID, _ = re.findall("\d+",hyperlink['onclick'])
        return {'company': hyperlink.text, 'stockSymbol': columns[1].select_one('a').text,
                    'sector': columns[2].text, 'subsector': columns[3].text,
                     'listingDate': columns[4].text, 'companyID': compID}


class Company():

    default = {'cons':False, 'only':''}

    def __init__(self,compID,**kwargs):
        self.ROOT_URL = "https://edge.pse.com.ph"
        self.MANAGEMENT_URL = "https://edge.pse.com.ph/companyPage/directors_and_management_list.do?cmpy_id="
        self.DISCLOSURE_URL = "https://edge.pse.com.ph/companyDisclosures/search.ax"
        self.STOCK_URL = "https://edge.pse.com.ph/companyPage/stockData.do?cmpy_id="
        self.DOWNLOAD_URL = "https://edge.pse.com.ph/downloadFile.do?file_id="
        self.VIEWER_URL = "https://edge.pse.com.ph/openDiscViewer.do?edge_no="

        self.options = {}
        self.officers = None
        self.compID = str(compID)
        self.name = kwargs.pop('name',self.compID)

        print('Getting '+ self.compID +' with: '+str(kwargs))

        for x in self.default.keys():
            self.options[x] = kwargs.get(x,self.default[x])

        self.MANAGEMENT_URL+=self.compID
        self.STOCK_URL+=self.compID
        self.disclosures = []
        self.fileIDs = [] # stack of files to download

        print(testGet(self.STOCK_URL))

        INIT = {'d':self.getDisclosures,'o':self.getOfficers,'s':self.getSecurities}
        for x in self.options['only']:
            INIT[x]()

    def __repr__(self):
        return self.name

    def initializeAll(self):
        self.getDisclosures()
        self.getOfficers()
        self.getSecurities()

    def getOfficers(self):
        print('\nGetting officers...')
        page = getPage(self.MANAGEMENT_URL)
        board,management = map(parsePairedRows,page.select('table.list > tbody'))
        self.officers = [*board,*management]
        self.board,self.management = board,management
        return self.officers

    def getManagement(self):
        if self.officers is None:
            self.getOfficers()
        return self.management

    def getBoard(self):
        if self.officers is None:
            self.getOfficers()
        return self.board

    def getDisclosures(self):
        print('\nGetting disclosures...')
        self.disclosures = getAll(self.getDisclosureByPageNum,self.parseDisclosures,self.options)
        return self.disclosures

    def getSecuritiesInfo(self):
        page = getPage(self.STOCK_URL)
        self.secInfo = list(map(lambda x: (x['value'],x.text), page.select('select > option')))
        return self.secInfo

    def getSecurities(self,**kwargs):
        print('\nGetting securities...')
        self.getSecuritiesInfo()
        self.sec = {x:Security(self.compID,x,ticker=y,**kwargs) for x,y in self.secInfo}
        return self.sec

    def parseDisclosures(self,page):
        rows = page.select('tbody > tr')
        entries = []
        for row in rows:
            entries.append(self.parseDisclosureRow(row))
        return entries

    def parseDisclosureRow(self,row):
        cols = row.select('td')
        hyperlink = cols[0].select_one('a')
        try:
            edgeNo = re.search("'(.+)'",hyperlink['onclick']).group(1)
            return {'template': hyperlink.text, 'dateAnnounced':cols[1].text, 'formNumber':cols[2].text, 'circularNum':cols[3].text.strip(), 'edge_no': edgeNo}
        except:
            return {'template': None, 'dateAnnounced':None, 'formNumber':None, 'circularNum':None, 'edge_no': None}

    def getDisclosureByPageNum(self,num):
        r = requests.get(self.DISCLOSURE_URL+"?pageNo="+str(num)+"&keyword="+self.compID+"&tmplNm=&sortType=date&dateSortType=DESC&cmpySortType=ASC")
        return BeautifulSoup(r.content, features="html.parser")

    def isOfficer(self,officer):
        if self.officers is None:
            self.getOfficers()
        return searchReturn(officer,self.officers,1,0)

    def exportDisclosureList(self, fn=None):
        try:
            if fn is None:
                fn = self.name + ".json"
            else:
                makeDirs('/'.join(fn.split('/')[0:-1]))
            if not self.disclosures:
                self.getDisclosures()
            with open(fn,'w+',encoding='utf-8') as f:
                json.dump({"Disclosures":self.disclosures},f, indent=4, sort_keys=True)
            print("Exported successfully!")
        except Exception as e:
            print('Unsuccessful:',e)
            return False
        return True

    def findFileID(self, edgeCode):
        page = getPage(self.VIEWER_URL+edgeCode)
        attachments = page.select("#file_list > option")
        count = len(attachments)
        if count > 2:
            print("More than one file was found.")
        elif count < 1:
            print("No attachments were found.")
        for x in attachments[1:]:
            self.fileIDs.append(x['value'])

    def downloadDisclosure(self, edgeCode, fn=None):
        self.findFileID(edgeCode)
        out = []
        for file in self.fileIDs:
            try:
                if fn is None:
                    fn = "disclosure/" + self.name + "/"
                makeDirs('/'.join(fn.split('/')))
                res = getResponse(self.DOWNLOAD_URL+file)
                ifn = re.search("\"(.+)\"\;",res.headers['content-disposition']).group(1)
                with open(fn+ifn,'wb+') as f:
                    f.write(res.content)
                print("Downloaded " + ifn + " successfully!")
                out.append(fn+ifn)
            except Exception as e:
                print('Unsuccessful with ' + ifn + " due to ",e)
                return None
        return out

    def findViewerID(self,edgeCode):
        page = getPage(self.VIEWER_URL+edgeCode)
        return page.select_one("iframe")["src"]

    def downloadViewer(self, edgeCode, fn=None):
        viewerID = self.findViewerID(edgeCode)
        try:
            if fn is None:
                fn = "disclosures/" + self.name + "/"
            makeDirs('/'.join(fn.split('/')))
            res = getResponse(self.ROOT_URL + viewerID)
            with open(fn+viewerID[-6:]+".html",'w+',encoding='utf-8') as f:
                f.write(res.text)
            print("Downloaded " + viewerID + " successfully!")
        except Exception as e:
            print('Unsuccessful with ' + viewerID + " due to ",e)

class Security():
    LANDING_URL = "https://edge.pse.com.ph/companyPage/stockData.do"
    DATA_URL = "https://edge.pse.com.ph/common/DisclosureCht.ax"

    interval = 366 # in days
    ticker = None
    history = None

    def __init__(self,compID,secID,**kwargs):
        self.compID,self.secID = str(compID),str(secID)
        self.token = {'cmpy_id': '', 'security_id': ''}
        self.date = {'startDate': '','endDate': ''}

        self.ticker = kwargs.get('ticker',None)
        self.interval = int(kwargs.get('interval',366))
        self.date['endDate'] = kwargs.get('endDate',dateToString(date.today()))
        self.date['startDate'] = kwargs.get('startDate',dateToString(subtractDays(stringToDate(self.date['endDate']),self.interval)))

        self.LANDING_URL+=processConfig(tuple(self.token.items()))
        #self.getTicker()
        self.makeToken(self.compID,self.secID)

    def __repr__(self):
        return self.ticker

    def getHistory(self):
        response = requests.post(self.DATA_URL,json={**self.token,**self.date})
        self.history = response.json()
        self.histPrice, self.histDisc = self.history['chartData'],self.history['tableData']
        return self.history

    def getHistPrice(self):
        if self.history is None:
            self.getHistory()
        return self.history['chartData']

    def getHistDisc(self):
        if self.history is None:
            self.getHistory()
        return self.history['tableData']

    def getTicker(self):
        if self.ticker is None:
            page = getPage(self.LANDING_URL)
            self.ticker = page.select_one('option', selected=True).text
        return self.ticker

    def exportPrice(self,fn=None):
        try:
            if fn is None:
                fn = 'hist_price/'+self.ticker+'.json'
            makeDirs('/'.join(fn.split('/')[0:-1]))
            with open(fn,'w+',encoding='utf-8') as f:
                f.write('{"chartData" : \n'+str(self.getHistPrice())+'\n}')
        except Exception as e:
            print('Unsuccessful:',e)
            return False
        return True

    def makeToken(self,compID,secID):
        self.token['cmpy_id'],self.token['security_id'] = compID,secID
        return self.token
