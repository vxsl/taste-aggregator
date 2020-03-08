from flask import Flask, render_template, url_for, request, redirect, Response

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils.functions import database_exists

from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from datetime import datetime

import process.scraper
import process.updateThemesDb
import process.updateMoodsDb

from collections import defaultdict

import sqlalchemy
from sqlalchemy.ext.associationproxy import association_proxy

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from sqlalchemy.engine.url import URL

import sys
import os


#****************************************************
# init config:

app = Flask(__name__)
"""
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SECRET_KEY'] = 'alpine'
app.config['SQLALCHEMY_ECHO'] = False
"""

#db = SQLAlchemy(app)

# The SQLAlchemy engine will help manage interactions, including automatically
# managing a pool of connections to your database
db = sqlalchemy.create_engine(
    # Equivalent URL:
    # postgres+pg8000://<db_user>:<db_pass>@/<db_name>?unix_sock=/cloudsql/<cloud_sql_instance_name>/.s.PGSQL.5432
   sqlalchemy.engine.url.URL(
        drivername='postgres+pg8000',
        username=os.getenv('DB_USER'),
        password=os.getenv('DB_PASS'),
        database=os.getenv('DB_NAME'),
        query={
            'unix_sock': '/cloudsql/{}/.s.PGSQL.5432'.format(
                os.getenv('CLOUD_SQL_CONNECTION_NAME'))
        }
    ),
     # ... Specify additional properties here.
    # [START_EXCLUDE]

    # [START cloud_sql_postgres_sqlalchemy_limit]
    # Pool size is the maximum number of permanent connections to keep.
    pool_size=5,
    # Temporarily exceeds the set pool_size if no connections are available.
    max_overflow=2,
    # The total number of concurrent connections for your application will be
    # a total of pool_size and max_overflow.
    # [END cloud_sql_postgres_sqlalchemy_limit]

    # [START cloud_sql_postgres_sqlalchemy_backoff]
    # SQLAlchemy automatically uses delays between failed connection attempts,
    # but provides no arguments for configuration.
    # [END cloud_sql_postgres_sqlalchemy_backoff]

    # [START cloud_sql_postgres_sqlalchemy_timeout]
    # 'pool_timeout' is the maximum number of seconds to wait when retrieving a
    # new connection from the pool. After the specified amount of time, an
    # exception will be thrown.
    pool_timeout=30,  # 30 seconds
    # [END cloud_sql_postgres_sqlalchemy_timeout]

    # [START cloud_sql_postgres_sqlalchemy_lifetime]
    # 'pool_recycle' is the maximum number of seconds a connection can persist.
    # Connections that live longer than the specified amount of time will be
    # reestablished
    pool_recycle=1800,  # 30 minutes
    # [END cloud_sql_postgres_sqlalchemy_lifetime]

    # [END_EXCLUDE]
)
# [END cloud_sql_postgres_sqlalchemy_create]

admin = Admin(app)

#****************************************************
# for development:
if (len(sys.argv) == 2 and sys.argv[1] == 'reset'):
	if os.path.exists('test.db'):
		os.remove('test.db')

#****************************************************
# Define a ModelView extension that has visible primary keys, for /admin view.

class FullModel(ModelView):
	column_display_pk = True
	column_hide_backrefs = False

#****************************************************
# Define association tables and models for theme-album and mood-album relations.
# The table allows for db.relationship.secondary
# The model allows for /admin view

class ThemeAssociation(db.Session.Model):
	__tablename__ = 'theme_associations'
	album_id = db.Column(db.String(), primary_key=True)
	theme_name = db.Column(db.String(), primary_key=True)
theme_associations = db.Table('theme_associations',
	db.Column('album_id', db.String(), db.ForeignKey('album.id'), primary_key=True),	
	db.Column('theme_name', db.String(), db.ForeignKey('theme.name'), primary_key=True),
	extend_existing=True
)

class MoodAssociation(db.Model):
	__tablename__ = 'mood_associations'
	album_id = db.Column(db.String(), primary_key=True)
	mood_name = db.Column(db.String(), primary_key=True)
mood_associations = db.Table('mood_associations',
	db.Column('album_id', db.String(), db.ForeignKey('album.id'), primary_key=True),
	db.Column('mood_name', db.String(), db.ForeignKey('mood.name'), primary_key=True),
	extend_existing=True
)

#****************************************************
# Define Album model.	
# Attributes: id, artist, title, date_added
# Relationships: themes, moods

similar_album_association = db.Table(
	'similar_album_associations',
	db.Column('parent_id', db.String(), db.ForeignKey('album.id'), index=True),
	db.Column('child_id', db.String(), db.ForeignKey('album.id')),
	db.UniqueConstraint('parent_id', 'child_id', name='unique_similarRelations')
	)

class Album(db.Model):
	__tablename__ = 'album'
	id = 			db.Column(db.String(), primary_key=True)
	artist = 		db.Column(db.String())
	title = 		db.Column(db.String())
	date_added = 	db.Column(db.DateTime, default=datetime.utcnow)
	parent = 		db.Column(db.Boolean, default=True)
	themes = 		db.relationship('Theme', secondary=theme_associations, backref=(db.backref('participants', lazy = 'dynamic')))
	moods = 		db.relationship('Mood', secondary=mood_associations, backref=(db.backref('participants', lazy = 'dynamic')))

	children = db.relationship('Album',
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
# Define Theme model. Meant to be accessed by AllMusic id string, ex. 'introspection-ma0000006318'
# Attributes: id, name

class Theme(db.Model):
	__tablename__ = 'theme'
	id = db.Column(db.String(), primary_key=True)
	name = db.Column(db.String())


#****************************************************
# Define Mood model. Meant to be accessed by AllMusic id string, ex. 'detached-xa0000000707'
# Attributes: id, name

class Mood(db.Model):
	__tablename__ = 'mood'
	id = db.Column(db.String(), primary_key=True)
	name = db.Column(db.String())

#****************************************************
# create /admin views:

if database_exists(app.config['SQLALCHEMY_DATABASE_URI']) == False:
		
		db.create_all()
		process.updateMoodsDb.update(db, Mood)
		process.updateThemesDb.update(db, Theme)

admin.add_view(FullModel(Album, db.session))

admin.add_view(FullModel(Theme, db.session))
admin.add_view(FullModel(Mood, db.session))

admin.add_view(FullModel(ThemeAssociation, db.session))
admin.add_view(FullModel(MoodAssociation, db.session))

#****************************************************
# misc. functions:

def associateThemes(album):

	for n,i in process.scraper.getThemes(album.id, db, Theme):
				themeTemp = Theme.query.filter_by(name=f'{n}').first()
				themeTemp.participants.append(album)

def associateMoods(album):
	for n,i in process.scraper.getMoods(album.id, db, Mood):
				moodTemp = Mood.query.filter_by(name=f'{n}').first()
				moodTemp.participants.append(album)
			
def associateSimilar(album):
	for newAlbum in process.scraper.getSimilarAlbums(album.id, db, Album):
			print(f"SIMILAR ALBUM:{newAlbum}")
			album.children.append(newAlbum)
			#newAlbum.parents.append(album)


	db.session.commit()

#****************************************************
# Render HTML: 

@app.route('/', methods=['POST', 'GET'])
def index():
	
	if request.args.get('reset') == 1:
		if os.path.exists('test.db'):
			os.remove('test.db')

	if request.method == 'POST':

		newAlbumEntry = Album(process.scraper.getIDFromInfo(request.form['artist'], request.form['title']))
		
		#associateThemes(newAlbumEntry)
		#associateMoods(newAlbumEntry)
		associateSimilar(newAlbumEntry)

		try:
			db.session.add(newAlbumEntry)
			db.session.commit()
			return redirect('/')
		except:
			return "There was an error adding your album"

	else:
		albumlist = Album.query.filter_by(parent=True).order_by(Album.date_added).all()
		themeDict = defaultdict(list)
		moodDict = defaultdict(list)
		similarCountDict = {}
		
		for album in albumlist:
			for association in ThemeAssociation.query.filter_by(album_id=album.id).all():
				themeDataPair = [Theme.query.filter_by(name=association.theme_name).one().id, association.theme_name]
				themeDict[album.title].append(themeDataPair)
			for association in MoodAssociation.query.filter_by(album_id=album.id).all():
				moodDataPair = [Mood.query.filter_by(name=association.mood_name).one().id, association.mood_name]
				moodDict[album.title].append(moodDataPair)
			similarCountDict[album.id] = len(album.children)

		return render_template('index.html', albumlist=albumlist, themeDict=themeDict, moodDict=moodDict, similarCountDict=similarCountDict)		
	

#****************************************************
if __name__ == "__main__":
	app.run(debug=True)

 
