#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Wikipedia Loves Monuments helper script, uploads images to Commons.
"""

# image status codes:
# 0: metadata downloaded, 1: image downloaded, 2: uploaded to commons, -1: invalid license, -2: duplicate

# create image numbers for same monument:
# UPDATE inda SET num = i.r FROM (SELECT *, DENSE_RANK() OVER (PARTITION BY koh_id ORDER BY id) r FROM inda) AS i WHERE inda.id=i.id;

image_dir = '/home/tgr/wlm-img/'

title_template_first = u'%(desc)s (%(koh_id)d. számú műemlék)'
title_template = u'%(desc)s (%(koh_id)d. számú műemlék) %(num)d'
text_template = u"""=={{int:filedesc}}==
{{Information
|Description = {{hu|1=%(desc)s (%(address)s)}}{{Monument Hungary|%(koh_id)d}}
|Source = [%(desc_url)s Indafotó]
|Date= %(date)s
|Author= [%(author_url)s %(author)s]
|Permission=
|other_versions=
|other_fields=
}}

=={{int:license-header}}==
{{cc-%(license)s-2.5-hu}}
{{Indafotó review}}
{{Wiki Loves Monuments 2011-hu}}

[[Category:Cultural heritage monuments in Hungary]]
[[Category:Files from Indafotó]]
"""

import pg8000, EXIF
from pg8000 import DBAPI
from datetime import datetime
import wikipedia as pywikibot
import upload

def db_gen(cursor):
	f = open('samat-files.txt', 'rt')
	for row in f:
		filename = row.strip()
		id = filename[:-4]
		cursor.execute('SELECT i.id, i.desc_url, i.author_name, i.author_url, i.koh_id, i.num, i.date, i.license, m.address, m.description FROM inda i JOIN monuments m on i.koh_id = m.azonosito WHERE i.id = %s', (id,))
		try:
			(id, desc_url, author, author_url, koh_id, num, date, license, address, desc) = cursor.fetchone()
		except TypeError:
			print '%s: <span style="color:red">missing</span><br />' % id
			continue
		yield {
			'id': id,
			'desc_url': desc_url,
			'author': author, 
			'author_url': author_url, 
			'koh_id': koh_id, 
			'num': num,
			'date': date.date(), 
			'license': license, 
			'address': address, 
			'desc': desc.replace('[', '(').replace(']', ')'),
		}

def process(img, row):
	if row['num'] == 1:
		title = title_template_first % row
	else:
		title = title_template % row
	row['title'] = title
	text = text_template % row
	filename = title + '.jpg'
	# bot = upload.UploadRobot(url = img, description = text, targetSite = pywikibot.Site('commons', 'commons'), useFilename = filename, keepFilename = True, verifyDescription = False)
	# if not bot.urlOK():
		# wikipedia.output('wrong filename: %s' % filename)
		# return
	# return bot.upload_image()
	page = pywikibot.Page(pywikibot.Site('commons', 'commons'), 'File:'+title+'.jpg')
	if not page.exists():
		style = 'style="color: red"'
	else:
		style = ''
	print (u'%s: <a %s href="http://commons.wikimedia.org/wiki/%s">%s</a><br />' % (row['id'], style, page.urlname(), title)).encode('utf-8')

def main(*args):
	global image_dir
	conn = DBAPI.connect(host='1.2.3.4', port=12345, database='wikiloves', user='wlm_web', password='XXX')
	cursor = conn.cursor()
	i = 0
	for row in db_gen(cursor):
		i = i + 1
		img = image_dir + row['id'] + '.jpg'
		f = open(img, 'rb')
		try:
			exif = EXIF.process_file(f)
			for key in exif.keys():
				if 'exif datetime' in key.lower():
					try:
						row['date'] = datetime.strptime(str(exif[key]), '%Y:%m:%d %H:%M:%S').date()
						break
					except ValueError:
						pass
		except Exception:
			print 'exif processing for %s skipped because of errors' % img
		f.close()
		try:
			if process(img, row):
				# cursor.execute('UPDATE inda SET status = 2 WHERE id = %s', (row['id'],))
				# conn.commit()
				pass
		except upload.UploadException as e: # dupe - needs patched upload.py
			if e.type != 'duplicate':
				raise
			pywikibot.output('%s is duplicate of %s' % (row['id'], e.param))
			# cursor.execute('UPDATE inda SET status = -2 WHERE id = %s', (row['id'],))
			# conn.commit()
		except Exception as e:
			raise
		# if i >= 3:
			# break
	conn.commit()
	conn.close()
	

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()
