from flask import Flask, render_template, request, redirect

from flask_sqlalchemy import SQLAlchemy

from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from datetime import datetime

import os

from collections import defaultdict

from sqlalchemy import Table, Column, Integer, String, Boolean, ForeignKey, UniqueConstraint, DateTime, MetaData
from sqlalchemy.orm import relationship, backref, sessionmaker 
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy import create_engine

import process.scraper
import process.updateThemesDb	
import process.updateMoodsDb

import pymysql

#****************************************************
# init config:

app = Flask(__name__)

app.config['SQLALCHEMY_ECHO'] = True
app.config['SECRET_KEY'] = 'alpine'

hostname = '10.200.114.4'
username = 'voxsol_helpr4'
password = 'kGr1m$ruDM@nZ'
database = 'voxsol_helpr4'


db = create_engine(f'mysql+pymysql://{username}:{password}@{hostname}:3306/{database}').connect()
Base = declarative_base()
meta = MetaData(bind=db)
DBSession = sessionmaker(bind=db)
session = DBSession()

admin = Admin(app)

#****************************************************
# Define a ModelView extension that has visible primary keys, for /admin view.

class FullModel(ModelView):
	column_display_pk = True
	column_hide_backrefs = False

#****************************************************
# Define Theme model. Meant to be accessed by AllMusic id string, ex. 'introspection-ma0000006318'
# Attributes: id, name

class Theme(Base):
	__tablename__ = 'theme'
	id = Column(String(50), primary_key=True)
	name = Column(String(50))


#****************************************************
# Define Mood model. Meant to be accessed by AllMusic id string, ex. 'detached-xa0000000707'
# Attributes: id, name

class Mood(Base):
	__tablename__ = 'mood'
	id = Column(String(50), primary_key=True)
	name = Column(String(50))

#****************************************************
# Define association tables and models for theme-album and mood-album relations.
# The table allows for db.relationship.secondary
# The model allows for /admin view

class ThemeAssociation(Base):
	__tablename__ = 'theme_associations'
	album_id = Column(String(50), primary_key=True,)
	theme_name = Column(String(50), primary_key=True)


theme_associations = Table('theme_associations', Base.metadata,
	Column('album_id', String(50), ForeignKey('album.id'), primary_key=True),	
	Column('theme_name', String(50), ForeignKey('theme.name'), primary_key=True),
	extend_existing=True
)


class MoodAssociation(Base):
	__tablename__ = 'mood_associations'
	album_id = Column(String(50), primary_key=True)
	mood_name = Column(String(50), primary_key=True)

mood_associations = Table('mood_associations', Base.metadata,
	Column('album_id', String(50), ForeignKey('album.id'), primary_key=True),
	Column('mood_name', String(50), ForeignKey('mood.name'), primary_key=True),
	extend_existing=True
)

#****************************************************
# Define association table for similar albums -- parents and children.

similar_album_association = Table(
	'similar_album_associations', Base.metadata,
	Column('parent_id', String(50), ForeignKey('album.id'), index=True),
	Column('child_id', String(50), ForeignKey('album.id')),
	UniqueConstraint('parent_id', 'child_id', name='unique_similarRelations')
	)

#****************************************************
# Define Album model.	
# Attributes: id, artist, title, date_added, parent (bool)
# Relationships: themes, moods, children
# 
class Album(Base):
	__tablename__ = 'album'
	id = 			Column(String(50), primary_key=True)
	artist = 		Column(String(50))
	title = 		Column(String(50))
	date_added = 	Column(DateTime, default=datetime.utcnow)
	parent = 		Column(Boolean, default=True)
	themes = 		relationship('Theme', secondary=theme_associations, backref=(backref('participants', lazy = 'dynamic')))
	moods = 		relationship('Mood', secondary=mood_associations, backref=(backref('participants', lazy = 'dynamic')))
	
	children = relationship('Album',
							secondary=similar_album_association,
							primaryjoin=id==similar_album_association.c.parent_id,
							secondaryjoin=id==similar_album_association.c.child_id)
	
	def __repr__(self):
		return '<Album %r>' % self.id

	def __init__(self, id):
		print(f"Album constructor: {id}")
		self.id = id.lower()
		self.artist, self.title = process.scraper.getBasicInfo(id)
		associateThemes(self)
		associateMoods(self)

#****************************************************
# misc. functions:

def associateThemes(album):

	for n,i in process.scraper.getThemes(album.id, session, Theme):
				themeTemp = session.query(Theme).filter_by(name=f'{n}').first()
				themeTemp.participants.append(album)

def associateMoods(album):
	for n,i in process.scraper.getMoods(album.id, session, Mood):
				moodTemp = session.query(Mood).filter_by(name=f'{n}').first()
				moodTemp.participants.append(album)
			
def associateSimilar(album):
	for newAlbum in process.scraper.getSimilarAlbums(album.id, session, Album):
			print(f"SIMILAR ALBUM:{newAlbum}")
			album.children.append(newAlbum)
			#newAlbum.parents.append(album)
			
#****************************************************
# populate the database:
"""
Base.metadata.create_all(bind=db)
process.updateMoodsDb.update(session, Mood)
process.updateThemesDb.update(session, Theme)
session.commit()
"""

#****************************************************
# create /admin views:
#
admin.add_view(FullModel(Album, session))

admin.add_view(FullModel(Theme, session))
admin.add_view(FullModel(Mood, session))

admin.add_view(FullModel(ThemeAssociation, session))
admin.add_view(FullModel(MoodAssociation, session))

#****************************************************
# Render HTML: 

@app.route('/', methods=['POST', 'GET'])
def index():
	
	if request.args.get('reset') == 1:
		if os.path.exists('test.db'):
			os.remove('test.db')

	if request.method == 'POST':
		print('hereeeeeeeeeeeeee now')
		entryID = process.scraper.getIDFromInfo(request.form['artist'], request.form['title'])

		existing = session.query(Album).filter_by(id=entryID).one_or_none()

		if existing != None:
			if existing.parent == 0:
				existing.parent = 1
				#associateThemes(existing)
				#associateMoods(existing) 
				associateSimilar(existing)
			else:
				print("This album already exists as a parent in the database.")			
		else:
			newAlbumEntry = Album(process.scraper.getIDFromInfo(request.form['artist'], request.form['title']))
			#associateThemes(newAlbumEntry)	
			#associateMoods(newAlbumEntry) 
			associateSimilar(newAlbumEntry)
			try:
				session.add(newAlbumEntry)
				session.commit()
			except:
				return "There was an error adding your album"
		return redirect('/helpr4')
			
	else:
		print("Regular GET page load.")
		albumlist = session.query(Album).filter_by(parent=True).order_by(Album.date_added).all()
		themeDict = defaultdict(list)
		moodDict = defaultdict(list)
		similarCountDict = {}
		
		for album in albumlist:
			for association in session.query(ThemeAssociation).filter_by(album_id=album.id).all():
				themeDataPair = [session.query(Theme).filter_by(name=association.theme_name).one().id, association.theme_name]
				themeDict[album.title].append(themeDataPair)
			for association in session.query(MoodAssociation).filter_by(album_id=album.id).all():
				moodDataPair =[ session.query(Mood).filter_by(name=association.mood_name).one().id, association.mood_name]
				moodDict[album.title].append(moodDataPair)
			similarCountDict[album.id] = len(album.children)

		return render_template('index.html', albumlist=albumlist, themeDict=themeDict, moodDict=moodDict, similarCountDict=similarCountDict)		
	

#****************************************************
if __name__ == "__main__":
	app.run(debug=True)
