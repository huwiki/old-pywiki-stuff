#!/usr/bin/python
# -*- coding: utf-8 -*-

import codecs
from pg8000 import DBAPI
import wikipedia as pywikibot
from pywikibot import i18n
import category

# FIXME code overlap with wlm_up, shoul be refactored into indafoto
title_template_first = u'%(desc)s (%(koh_id)d. számú műemlék)'
title_template = u'%(desc)s (%(koh_id)d. számú műemlék) %(num)d'
def get_title(row):
	row = {
		'koh_id': row[0],
		'num': row[1],
		'desc': row[2],
	}
	if row['num'] == 1:
		title = title_template_first % row
	else:
		title = title_template % row
	return title + '.jpg'

def write_titles():
	infile = open('wlm_secession_id.txt', 'rt')
	outfile = codecs.open('wlm_secession_title.txt', 'wt', 'utf-8')
	conn = DBAPI.connect(host='1.2.3.4', port=12345, database='wikiloves', user='wlm_web', password='XXX')
	cursor = conn.cursor()
	for id in infile:
		id = id.strip().partition('.')[0]
		cursor.execute('SELECT i.koh_id, i.num, m.description FROM inda i JOIN monuments m ON i.koh_id = m.azonosito WHERE i.id = %s', (id,))
		row = cursor.fetchall()[0]
		title = get_title(row)
		title = title[0].upper() + title[1:]
		outfile.write(title + '\n')

def secession_page_gen():
	file = codecs.open('wlm_secession_title.txt', 'rt', 'utf-8')
	site = pywikibot.Site('commons', 'commons')
	for line in file:
		title = 'File:' + line.strip()
		page = pywikibot.Page(site, title)
		yield page

def check_page_exists():
	for page in secession_page_gen():
		try:
			page.get()
		except pywikibot.NoPage:
			pywikibot.output(title)
			
def add_category():
	category = u'Art nouveau images from Wiki Loves Monuments 2011'
	bot = AddCategory(secession_page_gen())
	bot.run(category)

class AddCategory(category.AddCategory):
	def run(self, cat):
		self.newcatTitle = cat
		if not self.site.nocapitalize:
			self.newcatTitle = self.newcatTitle[:1].upper() + \
							   self.newcatTitle[1:]
		if not self.editSummary:
			self.editSummary = i18n.twtranslate(self.site, 'category-adding',
												{'newcat': self.newcatTitle})
		counter = 0
		for page in self.generator:
			self.treat(page)
			counter += 1
		pywikibot.output(u"%d page(s) processed." % counter)

add_category()