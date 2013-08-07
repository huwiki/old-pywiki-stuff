#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Wikipedia Loves Monuments helper script, notifies indafoto users with wrong image metadata.
"""

inda_user = 'email@example.com'
mail_id = 1
delay = 5

import codecs, time
from pg8000 import DBAPI
import wikipedia as pywikibot
import indafoto

def db_gen(cursor, sql, limit = None):
	cursor.execute(sql)
	rows = cursor.fetchall()
	i = 1
	for row in rows:
		if limit and i > limit:
			break
		yield row
		i = i + 1

def main():
	global inda_user, mail_id, delay
	inda = indafoto.Session(inda_user)
	conn = DBAPI.connect(host='1.2.3.4', port=12345, database='wikiloves', user='wlm_web', password='XXX')
	cursor = conn.cursor()
	text = codecs.open('wlm_mail.txt', 'rt', 'utf-8').read()
	for (name, page) in db_gen(cursor, 'SELECT DISTINCT inda.author_name, inda.author_url FROM inda JOIN inda_mail ON inda.author_url = inda_mail.author_url AND mail_id = %d WHERE status = 2 AND NOT sent' % mail_id):
		username = page[19:]
		if inda.sendMessage(username, text.format(user = name)):
			pywikibot.output('%s (%s) - OK' % (page, name))
			cursor.execute('UPDATE inda_mail SET sent = true WHERE author_url = %s AND mail_id = %s', (page, mail_id))
			conn.commit()
		else:
			pywikibot.output('%s (%s) - error' % (page, name))
		time.sleep(delay)

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()
