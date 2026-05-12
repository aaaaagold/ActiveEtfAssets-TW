#!/bin/python3

import sys
import time
import io
import subprocess
import http.client
from pathlib import Path
import random
import re
import gzip
import html
import json


# consts

HTTP_PORT=80
HTTPS_PORT=443

scheme2port={
"http":HTTP_PORT,
"https":HTTPS_PORT,
}
scheme2conn={
"http":http.client.HTTPConnection,
"https":http.client.HTTPSConnection,
}

rootDataDir=Path('data')/'00403A'
lastQueryTimePath=str(rootDataDir/'_lastQueryTime.txt')
lastEditDatePath=str(rootDataDir/'_lastEditDate.txt')
lastResponsePath=str(rootDataDir/'lastResponse.txt')


# args

isShowingDebugInfos= '--show-debug' in sys.argv or '--debug' in sys.argv 
isShowingHeaders=isShowingDebugInfos or '--show-header' in sys.argv or '--show-headers' in sys.argv 


# internal states

lastQueryTime=0
lastEditDate=''


# funcs

def ParseUrl(url):
	# return host,path,port
	m_scheme=re.search(r'^(https?):',url)
	host,path,port,conn='','',0,None
	if m_scheme:
		scheme=m_scheme.group(1)
		port=scheme2port[scheme]
		conn=scheme2conn[scheme]
		
		idx0=0
		for i in range(len(m_scheme.group(0)),len(url)):
			if url[i]!='/':
				idx0=i
				break
		idx1=url.find('/',idx0)
		host=url[idx0] if idx1<0 else url[idx0:idx1]
		path='' if idx1<0 else url[idx1:]
	
	return host,path,port,conn


def gitProc(fileName):
	gitStatus=['git','status']
	gitFetchMain=['git','fetch','origin','main']
	gitResetMain=['git','reset','origin/main']
	gitRestore=['git','restore','.']
	gitAdd=['git','add','.']
	gitCommit=['git','commit','-m','add 00403A '+fileName.replace("\\","\\\\").replace('"','\\"')+'']
	gitPush=['git','push','-f']
	cmds=[
		gitFetchMain,
		gitResetMain,
		gitRestore,
		gitAdd,
		gitCommit,
		gitPush,
	]
	returncodes=[]
	try:
		res=subprocess.run(gitStatus)
		if res.returncode:
			returncodes.append(res.returncode)
	except Exception as e:
		returncodes.append(e)
		pass
	if len(returncodes):
		try:
			cmdStart=['cmd','/c',]
			res=subprocess.run(cmdStart+gitAdd)
			if res.returncode:
				returncodes.append(res.returncode)
				raise
			for i in range(len(cmds)): cmds[i]=cmdStart+cmds[i]
		except Exception as e:
			returncodes.append(e)
			pass
	try:
		for i in range(len(cmds)): subprocess.run(cmds[i])
	except Exception as e:
		print(e)
		print("git push fail",returncodes)
	pass


def Req(host,port,path,Conn,cookies={}):
	#return
	global lastEditDate
	rtv=None
	headers={
		"Content-type": "application/x-www-form-urlencoded",
		"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
		"Accept-Encoding": "gzip, deflate",
		"Accept-Language": "en",
		"Cache-Control": "max-age=0",
		
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65535.0.8964.64 ChinaOutputVirusInDec/2019 Safari/537.36",
	}
	cookieStr=''
	for k in cookies:
		if cookieStr: cookieStr+='; '
		if cookies[k]==True: cookieStr+=k
		else:
			cookieStr+=k
			cookieStr+='='
			cookieStr+=cookies[k]
	if cookieStr: headers['cookie']=cookieStr
	conn=Conn(host,port)
	conn.request("GET", path, None, headers)
	response=conn.getresponse()
	h=response.getheaders()
	if isShowingHeaders:
		print(response.status,response.reason)
		print(h)
	responseHeaders={}
	for p in h: responseHeaders[p[0]]=p[1]
	
	data=response.read()
	conn.close()
	if 'content-encoding' in responseHeaders and responseHeaders['content-encoding']=='gzip':
		data=gzip.GzipFile(fileobj=io.BytesIO(data)).read()
	if isShowingDebugInfos:
		print(data)
	
	if response.status==301 or response.status==302:
		if 'set-cookie' in responseHeaders:
			newCookieStr=responseHeaders['set-cookie']
			newCookies=re.split(r';[ ]*',newCookieStr)
			for newCookie in newCookies:
				idx=newCookie.find('=')
				if idx<0: cookies[newCookie]=True
				else: cookies[newCookie[0:idx]]=newCookie[idx+1:]
		if 'location' in responseHeaders:
			rtv=responseHeaders['location']
	else:
		try:
			with open(lastResponsePath,'wb') as f:
				f.write(data)
		except:
			pass
		plain=data.decode('utf-8')
		lines=plain.split('\n')
		parser=re.compile(r'^\<div id="DataAsset"')
		for line in lines:
			res=parser.search(line)
			if res:
				pattern0="data-content="
				idx=line.find(pattern0)
				idx0=idx+len(pattern0)
				idx1=0
				if line[idx0]=='"':
					idx0+=1
					idx1=line.find('"',idx0)
				else:
					idx1=line.find(' ',idx0)
				if idx1<0: idx1=len(line)
				data=json.loads(html.unescape(line[idx0:idx1]))
				st=None
				cash=None
				for dat in data:
					if dat['AssetCode']=="ST":
						st=dat
					elif dat['AssetCode']=="CASH":
						cash=dat
				editDate=max([st['EditDate'],cash['EditDate'],])
				if not (lastEditDate<editDate):
					continue
				st=st['Details']
				cash=cash['Value']
				for i in range(len(st)):
					info={
						'stockCode':st[i]['DetailCode'],
						'stockShare':int(st[i]['Share']),
						'stockName':st[i]['DetailName'] if 'DetailName' in st[i] else None,
					}
					st[i]=info
				if True:
					from pprint import pprint
					pprint(st)
					print(cash)
					print(editDate)
				fileName=(editDate[:editDate.find("T")] if "T" in editDate else editDate)+'.json'
				try:
					path=str(rootDataDir/fileName)
					with open(path,'w') as f:
						f.write(json.dumps({
							"editDate":editDate,
							"ST":st,
							"CASH":cash,
						},indent='\t'))
					print("add",path)
				except:
					print("[ERROR] write queried data to file")
					pass
				lastEditDate=editDate
				with open(lastEditDatePath,'wb') as f: f.write(bytes(lastEditDate,'utf-8'))
				print('lastEditDate',lastEditDate)
				gitProc(fileName)
				break
	return rtv



def getCurrentQueryTime(return_unparsed=False):
	# use UTC+8
	t=time.gmtime(time.time()+3600*8)
	return t if return_unparsed else (t.tm_year*100+t.tm_mon)*100+t.tm_mday


def main(argv):
	global lastQueryTime
	global lastEditDate
	
	#url0=argv[1]
	url0='https://www.ezmoney.com.tw/ETF/Fund/Info?fundCode=63YTW'
	rootDataDir.mkdir(parents=True,exist_ok=True)
	# detect writable
	try:
		with open(lastQueryTimePath,'r') as f:
			lastQueryTime=int(f.read())
	except:
		lastQueryTime=0
	with open(lastQueryTimePath,'w') as f: f.write(str(lastQueryTime))
	try:
		with open(lastEditDatePath,'rb') as f:
			lastEditDate=f.read().decode('utf-8')
	except:
		lastEditDate=''
	with open(lastEditDatePath,'wb') as f: f.write(bytes(lastEditDate,'utf-8'))
	
	# start state info
	print('lastQueryTime',lastQueryTime)
	print('lastEditDate',lastEditDate)
	
	# start mainloop
	while True:
		qtm=getCurrentQueryTime()
		if isShowingDebugInfos:
			print('qtm',qtm)
		if lastQueryTime==qtm:
			t=getCurrentQueryTime(True)
			t=3600-(t.tm_min*60+t.tm_sec)+1+random.random()*3e3 # +1 +rnd val
			time.sleep(t)
			continue
		lastQueryTime=qtm
		with open(str(rootDataDir/'_lastQueryTime.txt'),'w') as f: f.write(str(lastQueryTime))
		print('lastQueryTime',lastQueryTime)
		
		url=url0
		cookies={}
		while True:
			parsedUrl=ParseUrl(url)
			host,path,port,conn=parsedUrl
			if isShowingDebugInfos:
				for x in parsedUrl: print(x)
			if port:
				res=None
				try:
					res=Req(host,port,path,conn,cookies)
				except:
					res=None
					print("[ERROR] errors in Req()")
				if not res: break
				url=res
			else:
				print("[ERROR] unknown scheme",url,parsedUrl)
				break
	pass


if __name__=='__main__':
	main(sys.argv)

