from flask import Flask, render_template, url_for, request, redirect

from flask_sqlalchemy import SQLAlchemy

from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from datetime import datetime

import process.scraper
import process.updateThemesDb

from collections import defaultdict


#****************************************************
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SECRET_KEY'] = 'alpine'
app.config['SQLALCHEMY_ECHO'] = True

db = SQLAlchemy(app)
#theme_db = SQLAlchemy(app)

admin = Admin(app)

#****************************************************
#class User(db.Model):
#	__tablename__ = 'user'
#	id = db.Column('id', db.String(), primary_key=True)
	#password = db.Column(db.String())

#****************************************************

class ImprovedModel(ModelView):
	column_display_pk = True

#****************************************************
# Album-Theme ASSOCIATION TABLE:

"""class ThemeAssociation(db.Model):
	__tablename__='theme_associations'
	album_id = db.Column(db.String(), db.ForeignKey('album.id'))
	theme_name = db.Column(db.String(), db.ForeignKey('theme.name'), primary_key = True)"""


"""
class ThemeAssociation(db.Model):
	__tablename__ = 'theme_associations'
	album_id = db.Column(db.String())
	theme_name = db.Column(db.String(), primary_key=True)
"""


class ThemeAssociation(db.Model):
	__tablename__ = 'theme_associations'
	album_id = db.Column(db.String(), primary_key=True)
	theme_name = db.Column(db.String(), primary_key=True)


theme_associations = db.Table('theme_associations',
	db.Column('album_id', db.String(), db.ForeignKey('album.id'), primary_key=True),
	#db.Column('theme_name', db.String(), db.ForeignKey('theme.name'), primary_key=True),
	
	db.Column('theme_name', db.String(), db.ForeignKey('theme.name'), primary_key=True),
	extend_existing=True
)
#****************************************************

class Album(db.Model):
	__tablename__ = 'album'
	id = db.Column(db.String(), primary_key=True)
	artist = 		db.Column(db.String())
	title = 		db.Column(db.String())
	date_added = 	db.Column(db.DateTime, default=datetime.utcnow)

	
	#themes = db.relationship('Theme', secondary=theme_associations, back_populates='participants')

	themes = db.relationship('Theme', secondary=theme_associations, backref=(db.backref('participants', lazy = 'dynamic')))

	def __repr__(self):
		return '<Album %r>' % self.id

#****************************************************

class Theme(db.Model):
	__tablename__ = 'theme'
	id = db.Column(db.String(), primary_key=True)
	name = db.Column(db.String())
	#participants = db.relationship('Album', secondary=theme_associations, back_populates='themes')


#****************************************************


#process.updateMoodsDb.update(db, Mood)
#process.updateThemesDb.update(db, Theme)


#db.create_all(

admin.add_view(ImprovedModel(Album, db.session))
admin.add_view(ImprovedModel(Theme, db.session))
admin.add_view(ImprovedModel(ThemeAssociation, db.session))

#themeTemp = Theme.query.filter_by(name='Angry').first()
#albumTemp = Album.query.filter_by(id='mw0000042674').first()

#themeTemp.participants.append(albumTemp)
#db.session.commit()


#****************************************************

@app.route('/', methods=['POST', 'GET'])
def index():
	if request.method == 'POST':

		artistInput = request.form['artist']
		titleInput = request.form['title']

		albumInfo = process.scraper.getBasicInfo(titleInput, artistInput)

		newAlbumEntry = Album(id=albumInfo['id'], artist=albumInfo['artist'], title=albumInfo['title'])

		
		for n,i in process.scraper.getThemes(albumInfo['id'], db, Theme):
			print(f'\n\n\n{n}\n\n\n')
			themeTemp = Theme.query.filter_by(name=f'{n}').first()
			themeTemp.participants.append(newAlbumEntry)
	
		try:
			db.session.add(newAlbumEntry)
			db.session.commit()
			return redirect('/')
		except:
			return "There was an error adding your album"
	else:
		albumlist = Album.query.order_by(Album.date_added).all()

		#themeDict = {}
		themeDict = defaultdict(list)
		
		for album in albumlist:
			for association in ThemeAssociation.query.filter_by(album_id=album.id).all():
				themename = association.theme_name

				#if album.title in themeDict:
				themeDict[album.title].append(themename)
				#else:
					#themeDict[album.title] = themename


		return render_template('index.html', albumlist=albumlist, themeDict=themeDict)		
	

if __name__ == "__main__":
	app.run(debug=True)

 