#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Wikipedia Loves Monuments helper script, donwloads images from Indafoto.
"""

# image status codes:
# 0: metadata downloaded, 1: image downloaded, 2: uploaded to commons, -1: invalid license

image_dir = '/home/tgr/wlm-img/'

import re, feedparser, urllib, urllib2, pg8000
from time import mktime
from datetime import datetime
import wikipedia as pywikibot
from pg8000 import DBAPI

re_license = re.compile(r'<a href="http://creativecommons.org/licenses/(by|by-sa)/2.5/hu/" rel="external">')
re_id = re.compile(r'<a href="/tag/koh(\d+)" class="global-tag"')
re_date = re.compile('<p>k\xe9sz\xfclt: ([\d .:]+)</p>')

def inda_generator():
	global re_license, re_id
	inda = feedparser.parse('http://feed.indafoto.hu/tag/wikilovesmonuments/feed')
	while inda:
		for entry in inda.entries:
			data = {}
			data['desc_url'] = entry.id
			data['date'] = data['last_modified_date'] = datetime.fromtimestamp(mktime(entry.updated_parsed))
			data['author'] = entry.author_detail.name
			data['author_url'] = entry.author_detail.href
			m = re.search(re_date,  inda['entries'][0]['content'][0]['value'])
			if m:
				try:
					date = datetime.strptime(m.group(1), '%Y.%m.%d %H:%M')
				except ValueError:
					date = None
				if date:
					data['date'] = date
			# links are ordered ascending by size, so we need the last one 
			for link in entry.links:
				if not 'title' in link or link.title not in ('xs', 's', 'm', 'l', 'xl'):
					continue
				img = {}
				img['url'] = link.href
				img['size'] = int(link.length)
				img['width'] = int(link.width)
				img['height'] = int(link.height)
				data['img'] = img
			desc = urllib2.urlopen(data['desc_url']).read()
			m = re.search(re_license, desc)
			if m:
				data['license'] = m.group(1)
			else:
				data['license'] = None
			m = re.search(re_id, desc)
			if m:
				data['id'] = int(m.group(1))
			else:
				data['id'] = None		
			yield data
		if 'next' in inda.feed:
			print inda.feed.next
			inda = feedparser.parse(inda.feed.next)
		else:
			inda = None

def count(id, license, nu, cnt = {'i': 0, 'no_id': 0, 'no_license':0, 'by':0, 'by_sa': 0, 'inserted': 0, 'updated': 0}):
	cnt['i'] = cnt['i'] + 1
	if not id:
		cnt['no_id'] = cnt['no_id'] + 1
	if not license:
		cnt['no_license'] = cnt['no_license'] + 1
	elif license == 'by':
		cnt['by'] = cnt['by'] + 1
	elif license == 'by-sa':
		cnt['by_sa'] = cnt['by_sa'] + 1
	if nu == 'insert':
		cnt['inserted'] = cnt['inserted'] + 1
	elif nu == 'update':
		cnt['updated'] = cnt['updated'] + 1
	return cnt

def needs_update(id, entry, cursor):
	"""Returns two flags: the first is 'insert' if the entry is missing from the database, 'update' if it is there but the new entry is better (larger resolution, more metadata, better license), None if it can be skipped; the second is true if the koh_id changed (and thus the num column needs update)"""
	cursor.execute('SELECT status, img_size, koh_id, license FROM inda WHERE id = %s', (id,))
	row = cursor.fetchone()
	if row == None:
		return ('insert', False)
	(status, size, koh_id, license) = row
	if status == 2:
		return (None, False)
	if not license and not entry['license']:
		return (None, False)
	if entry['id'] and not koh_id:
		return ('update', True)
	if entry['license'] and not license:
		return ('update', False)
	if entry['img']['size'] > size:
		return ('update', False)
	return (None, False)

def find_next_free_num(koh_id, cursor):
	num = 1
	while True:
		cursor.execute('SELECT count(*) num_taken FROM inda WHERE koh_id = %s AND num = %s', (koh_id, num))
		num_taken = cursor.fetchone()[0]
		if num_taken == 0:
			break
		num = num + 1
	# print "%s: %s" % (koh_id, num)
	return num
	
def main(*args):
	global image_dir
	conn = DBAPI.connect(host='1.2.3.4', port=12345, database='wikiloves', user='wlm_web', password='XXX')
	cursor = conn.cursor()
	for entry in inda_generator():
		if entry['author'] == 'samat78': # images imported from commons
			continue
		if entry['date'] >= datetime(2011, 10, 22):
			continue
		id = entry['desc_url'].split('/')[-1]
		(nu, renumber) = needs_update(id, entry, cursor)
		cnt = count(entry['id'], entry['license'], nu)
		if not nu:
			continue
		if not entry['id'] or not entry['license']: # invalid entry
			status = 0
		else:
			status = 1
			urllib.urlretrieve(entry['img']['url'], image_dir + id + '.jpg')
		if nu == 'insert':
			try:
				num = find_next_free_num(entry['id'], cursor)
				cursor.execute('INSERT INTO inda(id, koh_id, num, desc_url, date, author_name, author_url, license, img_url, img_size, img_width, img_height, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)', (id, entry['id'], num, entry['desc_url'], entry['date'], entry['author'], entry['author_url'], entry['license'], entry['img']['url'], entry['img']['size'], entry['img']['width'], entry['img']['height'], status))
			except pg8000.errors.ProgrammingError:
				raise
		else:
			if renumber:
				num = find_next_free_num(entry['id'], cursor)
				cursor.execute('UPDATE inda SET koh_id = %s, num = %s, license = %s, img_size = %s, img_width = %s, img_height = %s, status = %s WHERE id = %s', (entry['id'], num, entry['license'], entry['img']['size'], entry['img']['width'], entry['img']['height'], status, id))
			else:
				cursor.execute('UPDATE inda SET koh_id = %s, license = %s, img_size = %s, img_width = %s, img_height = %s, status = %s WHERE id = %s', (entry['id'], entry['license'], entry['img']['size'], entry['img']['width'], entry['img']['height'], status, id))
	conn.commit()
	conn.close()
	print '%(i)d images, no id: %(no_id)d, no license: %(no_license)d, by: %(by)d, by-sa: %(by_sa)d, inserted: %(inserted)d, updated: %(updated)d' % cnt

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()
