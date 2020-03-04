from flask import Flask, render_template, url_for, request, redirect

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils.functions import database_exists

from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from datetime import datetime

import process.scraper
import process.updateThemesDb
import process.updateMoodsDb

from collections import defaultdict

from sqlalchemy.ext.associationproxy import association_proxy

#****************************************************
# init config:

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SECRET_KEY'] = 'alpine'
app.config['SQLALCHEMY_ECHO'] = False

db = SQLAlchemy(app)
admin = Admin(app)

#****************************************************
# Define a ModelView extension that has visible primary keys, for /admin view.

class FullModel(ModelView):
	column_display_pk = True

#****************************************************
# Define association tables and models for theme-album and mood-album relations.
# The table allows for db.relationship.secondary
# The model allows for /admin view

class ThemeAssociation(db.Model):
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

class SimilarRelation(db.Model):
	__tablename__='similar_album_associations'
	parent_id = db.Column(db.String(), db.ForeignKey('album.id'), primary_key=True)
	child_id = db.Column(db.String(), db.ForeignKey('album.id'), primary_key=True)

class Album(db.Model):
	__tablename__ = 'album'
	id = db.Column(db.String(),  db.ForeignKey('album.id'), primary_key=True)
	artist = 		db.Column(db.String())
	title = 		db.Column(db.String())
	date_added = 	db.Column(db.DateTime, default=datetime.utcnow)

	themes = db.relationship('Theme', secondary=theme_associations, backref=(db.backref('participants', lazy = 'dynamic')))

	moods = db.relationship('Mood', secondary=mood_associations, backref=(db.backref('participants', lazy = 'dynamic')))

	children = db.relationship('SimilarRelation', backref='children', primaryjoin=id==SimilarRelation.child_id)
	parents = db.relationship('SimilarRelation', backref='parents', primaryjoin=id==SimilarRelation.parent_id)

	def __repr__(self):
		return '<Album %r>' % self.id

	def __init__(self, id):
		result.artist = process.scraper.getBasicInfo(id)[0]


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

admin.add_view(FullModel(Album, db.session))

admin.add_view(FullModel(Theme, db.session))
admin.add_view(FullModel(Mood, db.session))

admin.add_view(FullModel(ThemeAssociation, db.session))
admin.add_view(FullModel(MoodAssociation, db.session))

admin.add_view(FullModel(SimilarRelation, db.session))

#****************************************************
# Render HTML: 

@app.route('/', methods=['POST', 'GET'])
def index():

	if database_exists(app.config['SQLALCHEMY_DATABASE_URI']) == False:
		db.create_all()
		process.updateMoodsDb.update(db, Mood)
		process.updateThemesDb.update(db, Theme)

	if request.method == 'POST':

		artistInput = request.form['artist']
		titleInput = request.form['title']

		albumInfo = process.scraper.getBasicInfo(titleInput, artistInput)

		newAlbumEntry = Album(id=albumInfo['id'], artist=albumInfo['artist'], title=albumInfo['title'])
		
		for n,i in process.scraper.getThemes(albumInfo['id'], db, Theme):
			themeTemp = Theme.query.filter_by(name=f'{n}').first()
			themeTemp.participants.append(newAlbumEntry)
	
		for n,i in process.scraper.getMoods(albumInfo['id'], db, Mood):
			moodTemp = Mood.query.filter_by(name=f'{n}').first()
			moodTemp.participants.append(newAlbumEntry)
		
		for n,i in process.scraper.getSimilarAlbums(albumInfo['id'], db, Album):
			print(f"SIMILAR ALBUM:\n\n\n{n}\n\n\n")
			newAlbumEntry.children.append(Album(id=i, title=n))

		try:
			db.session.add(newAlbumEntry)
			db.session.commit()
			return redirect('/')
		except:
			return "There was an error adding your album"
	else:
		albumlist = Album.query.order_by(Album.date_added).all()

		themeDict = defaultdict(list)
		moodDict = defaultdict(list)
		
		for album in albumlist:
			for association in ThemeAssociation.query.filter_by(album_id=album.id).all():
				themeDataPair = [Theme.query.filter_by(name=association.theme_name).one().id, association.theme_name]
				themeDict[album.title].append(themeDataPair)
			for association in MoodAssociation.query.filter_by(album_id=album.id).all():
				moodDataPair = [Mood.query.filter_by(name=association.mood_name).one().id, association.mood_name]
				moodDict[album.title].append(moodDataPair)

		return render_template('index.html', albumlist=albumlist, themeDict=themeDict, moodDict=moodDict)		
	

#****************************************************
if __name__ == "__main__":
	app.run(debug=True)

 