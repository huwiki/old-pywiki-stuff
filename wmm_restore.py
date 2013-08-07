#!/usr/bin/python
# -*- coding: utf-8 -*-

import mysql.connector
import wikipedia as pywikibot
import codecs

def db_gen(cursor, query):
    cursor.execute(query)
    while True:
        try:
            row = cursor.fetchone()
        except TypeError:
            return
        if row == None:
            return
        else:
            yield row

db = mysql.connector.Connect(host='localhost', user='wmm_public', passwd='******', database='recovery')
revisions = []
cursor = db.cursor()
for row in db_gen(cursor, 'SELECT page_id, max(rev_id) FROM page JOIN revision ON page_id = rev_page JOIN text ON old_id = rev_text_id GROUP BY page_id'):
    revisions.append(row[1])
for revision in revisions:
    cursor.execute('SELECT page_title, page_namespace, old_text FROM page JOIN revision ON page_id = rev_page JOIN text ON old_id = rev_text_id WHERE rev_id = %(rev)s', {'rev': revision})
    article = cursor.fetchone()
    page = pywikibot.Page(pywikibot.Site('hu', 'wmhuint'), codecs.decode(article[0], 'utf-8'), defaultNamespace = article[1])
    page.put(codecs.decode(article[2], 'utf-8'));
    # print page.title().encode('utf-8');
