#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Indafoto.hu manipulation library
"""

import re, os, urllib, urllib2, cookielib
import wikipedia as pywikibot

class Session:
	noEmailAddressRegexp = re.compile(r'Ez a felhasználó sajnos nem adott meg értesítési\s+címet így neki nem tudsz üzenetet küldeni.')
	csrfRegexp = re.compile(r'<input type="hidden" name="csrf_token" value="([\d\w-]+)" />')
	sendSuccessRegexp = re.compile(r'<p>Sikeresen elküldve\.</p>')
	
	def __init__(self, user = None):
		self.user = user
		policy = cookielib.DefaultCookiePolicy(allowed_domains = ['indapass.hu', 'indafoto.hu', '.indapass.hu', '.indafoto.hu'])
		self.cookiejar = cookielib.LWPCookieJar(policy = policy)
		self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookiejar))
		if self.user:
			cookie_file = self.getLoginDataFile()
			if os.path.exists(cookie_file):
				self.cookiejar.load(cookie_file, ignore_discard = True, ignore_expires = True)
	
	def decorateFileRead(self, f):
		content = f.read()
		f.read = lambda: content
		return f
	
	def getLoginDataFile(self):
		if not self.user:
			raise IndafotoException('getLoginDataFile() with no user given')
		return 'login-data/indafoto-%s-login.data' % self.user
	
	def login(self):
		url = 'https://daemon.indapass.hu/http/login'
		if self.user:
			pywikibot.output(u'Logging in as Inda user %s...' % self.user)
		else:
			pywikibot.output(u'Logging in to Inda...')
			self.user = pywikibot.input('Email: ')
		password = pywikibot.input('Password: ', password = True)
		data = urllib.urlencode({
			'partner_id': 'indapass',
			'username': self.user,
			'password': password,
			'autologin': '1',
		})
		self.opener.open(url, data)
		self.cookiejar.save(self.getLoginDataFile(), ignore_discard = True, ignore_expires = True)
	
	def getCsrfToken(self, response):
		m = self.csrfRegexp.search(response.read())
		if not m:
			raise NotLoggedInException()
		return m.group(1)
		
	def sendMessage(self, user, message):
		url = 'http://indafoto.hu/%s/details' % user
		f = self.decorateFileRead(self.opener.open(url))
		if self.noEmailAddressRegexp.search(f.read()):
			return False
		try:
			csrf_token = self.getCsrfToken(f)
		except NotLoggedInException:
			self.login()
			f = self.opener.open(url)
			csrf_token = self.getCsrfToken(f)
		data = urllib.urlencode({
			'csrf_token': csrf_token,
			'body': message.encode('utf-8'),
			'submit': 'Mehet',
		})
		f = self.opener.open(url + '/send', data)
		return bool(self.sendSuccessRegexp.search(f.read()))

class IndafotoException(Exception):
	pass

class NotLoggedInException(IndafotoException):
	pass
