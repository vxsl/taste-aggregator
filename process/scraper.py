#!/usr/bin/env python3	

from bs4 import BeautifulSoup
from bs4 import SoupStrainer
from html.parser import HTMLParser
import requests
import re
#***********************************************************************************************************************************
def getID(title, artist):
	searchPage = requests.get("https://www.allmusic.com/search/albums/" + artist.replace(" ", "+") + "+" + title.replace(" ", "+"), headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36'})

	searchSoup = BeautifulSoup(searchPage.content, "html.parser", parse_only=SoupStrainer("div", class_="title"))

	tooltip = searchSoup.find('a').get('data-tooltip')
	id = re.search("[a-z]+\d+", tooltip)

	return id[0]

def getID(url):
	id = re.search("[a-z]+\d+", url)
	return id[0]

#***********************************************************************************************************************************
def getBasicInfo(title, artist):
	searchPage = requests.get("https://www.allmusic.com/search/albums/" + artist.replace(" ", "+") + "+" + title.replace(" ", "+"), headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36'})

	idTitleSoup = BeautifulSoup(searchPage.content, "html.parser", parse_only=SoupStrainer("div", class_="title"))
	artistSoup = BeautifulSoup(searchPage.content, "html.parser", parse_only=SoupStrainer("div", class_="artist"))

	tooltip = idTitleSoup.find('a').get('data-tooltip')
	idCandidates = re.search("[a-z]+\d+", tooltip)

	titleCandidate = idTitleSoup.find('a').text

	artistCandidate = artistSoup.find('a').text


	result = {'id':idCandidates[0], 'title':titleCandidate, 'artist':artistCandidate}
	return result

def getBasicInfo(id):
	albumPageSoup = BeautifulSoup(getPage(getURL(id)).content, "html.parser", parse_only=SoupStrainer("header"))
	artist = albumPageSoup.find("h2", class_="album-artist").a.text
	title = albumPageSoup.find("h1", class_="album-title").text.strip()
	return [artist, title]

#***********************************************************************************************************************************
def getURL(id):
	albumURL = f'https://www.allmusic.com/album/{id}'
	return albumURL


#***********************************************************************************************************************************
def getPage(url):

	albumPage = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36'})
	return albumPage


#***********************************************************************************************************************************

def getThemes(id, db, themeModel):

	albumSidebarSoup = BeautifulSoup(getPage(getURL(id)).content, "html.parser", parse_only=SoupStrainer("div", class_="sidebar"))

	themeList = []

	for count,theme in enumerate(albumSidebarSoup.find_all("span", class_="theme")):
		
		themeNameCandidate = theme.text.strip()
		r = re.search("(([a-z]+\-)+)[a-z]+\d+", theme.a.get('href'))
		themeIdCandidate = r[0]

		# if the theme doesn't already exist in the Theme model in db, add it and commit.
		if themeModel.query.filter_by(name=themeNameCandidate).one_or_none() == None:
			db.session.add(themeModel(id=themeIdCandidate, name=themeNameCandidate))
			db.session.commit()

		themeList.append([themeNameCandidate, themeIdCandidate])

	return themeList

#***********************************************************************************************************************************

def getMoods(id, db, moodModel):

	albumSidebarSoup = BeautifulSoup(getPage(getURL(id)).content, "html.parser", parse_only=SoupStrainer("div", class_="sidebar"))

	moodList = []

	for count,mood in enumerate(albumSidebarSoup.find_all("span", class_="mood")):
		
		moodNameCandidate = mood.text.strip()
		r = re.search("(([a-z]+\-)+)[a-z]+\d+", mood.a.get('href'))
		moodIdCandidate = r[0]

		# if the mood doesn't already exist in the Theme model in db, add it and commit.
		if moodModel.query.filter_by(name=moodNameCandidate).one_or_none() == None:
			db.session.add(moodModel(id=moodIdCandidate, name=moodNameCandidate))
			db.session.commit()

		moodList.append([moodNameCandidate, moodIdCandidate])

	return moodList


#***********************************************************************************************************************************

def getSimilarAlbums(id, db, albumModel):


	similarAlbumPage = requests.get(getURL(id) + "/similar", headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.111 Safari/537.36'})	
	#print(similarAlbumPage.content)
	similarAlbumSoup = BeautifulSoup(similarAlbumPage.content, "html.parser", parse_only=SoupStrainer("div", class_="album-highlights-container"))


	similarAlbumList = []

	for album in similarAlbumSoup.find_all("a"):
		
		print(f"ARTIST: {album.find('div', class_='info').find('div', class_='artist').text}")

		if albumModel.query.filter_by(id=getID(album.get('href'))).one_or_none() == None:
			#print(album.find("div")).get_text()
			
			#print(album.get('data-hasqtip'))
			
			info = album.find('div', class_='info')


			db.session.add(albumModel(
				id = getID(album.get('href')),
				title = info.find('div', class_='title').text,
				artist = info.find('div', class_='artist').text,

				))
				#artist = {album.find('div', class_='info').find('div', class_='artist').text}))
	return similarAlbumList

#***********************************************************************************************************************************
