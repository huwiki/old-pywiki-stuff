#!/usr/bin/python
# -*- coding: utf-8  -*-
#TODO: force, külön csak egy nap, külön csak a gallery, csak a nemlétezők, osztály, hiányzó cikkek nem bot módban, {{napképe-galéria}}, notify-textben az egyes piros linkekhez dátum és link a képre (vagy a galériára?), nemlétező Commons lapoknál ne dobjon hibát, fordított irány
"""
A huwiki nap képéhez másolja át a szükséges allapokat a Commonsból,
és legyártja a havi archívum galériát.
v0.20
forrás: http://hu.wikipedia.org/wiki/Szerkesztő:SamatBot/napkepe.py
Használat: napkepe.py --január
"""
import sys, string, re, datetime, calendar
import wikipedia

# debug/testing helper (replace page.put with page_put)
def page_put(text, summary, botflag = False, minorEdit=False):
  wikipedia.output(text)
  wikipedia.output('--------------------------------------------------------')
  wikipedia.output(summary)
  wikipedia.output('=====================================================')
  wikipedia.output('=====================================================')

# where it makes sense, the following mapping keys will be replaced using the % operator:
# filename, desc, year, month, day, lang, monthname
potd_filename_page = {
    'hu': u'Sablon:Napképe/%(year)d-%(month)02d-%(day)02d',
}
potd_desc_page = {
    'hu': u'Sablon:Napképe/%(year)d-%(month)02d-%(day)02d (hu)',
}
potd_filename_text = {
    'hu': u'%(filename)s<noinclude>[[Kategória:Napképe sablonok|{{SUBPAGENAME}}]]</noinclude>',
}
potd_desc_text = {
    'hu': u'%(desc)s<noinclude>[[Kategória:Napképe sablonok|{{SUBPAGENAME}}]]</noinclude>',
}
potd_summary = {
    'hu': u'allap másolása a Commonsból',
}
archive_page = {
    'hu': u'Wikipédia:A nap képe/%(year)d-%(month)02d'
}
archive_text = { # "records" will be replaced with list of records
    'hu': u'== %(monthname)si képek archívuma ==\n\n<gallery perrow="6">\n%(records)s</gallery>',
}
archive_record = { # filename and desc will also be replaced
    'hu': u'Fájl:%(filename)s|%(day)d. {{napképe/%(year)d-%(month)02d-%(day)02d (hu)}}' \
        + u' {{szerkeszt|Sablon:Napképe/%(year)d-%(month)02d-%(day)02d (hu)|<sub>(javít)</sub>}}\n',
}
archive_summary = {
    'hu': u'%(monthname)si archívum galéria',
}
redlink_notify_page = {
    'hu': u'Wikipédia:Kocsmafal (egyéb)',
}
redlink_notify_title = {
    'hu': u'Piros linkek a %(monthnamei)si napok képeiben',
}
redlink_notify_text = { # "redlinks" will be replaced with a list
    'hu': u'%(redlinks)s\n--~~~~',
}

# regexps to obtain filename/description from the commons subpages
# expected filename template format: <filename> or {{Potd filename|<filename>|<year>|<month>|<day>}} 
commons_filename_re = re.compile(r"\{\{Potd filename\|(?P<filename>[^|]+)\|(?P<year>\d+)\|(?P<month>\d+)\|(?P<day>\d+)\}\}")
# expected description template format: <description> or {{Potd description|1=<description>|2=<lang>|3=<year>|4=<month>|5=<day>}}
commons_desc_re = re.compile(r"\{\{Potd (description|page)\|1=(?P<desc>.+)\|2=(?P<lang>\w+)\|3=(?P<year>\d+)\|4=(?P<month>\d+)\|5=(?P<day>\d+)\}\}")
# this was used before the Potd templates, checked for backwards compatibility
oldcat_re = re.compile(r'\s*<noinclude>\[\[Category:Potd templates\]\]</noinclude>', re.S)

commons = wikipedia.getSite(code='commons', fam='commons')
homeWiki = wikipedia.getSite()

# XXX: should link to wikipedia, not home wiki?
def fix_links(text, lang):
    """turns [[:hu:blah|blah]] and similar into [[blah]]"""
    text = re.sub(r"\[\[(?::w)?:?" + lang + r":(?P<page>[^|\]]+)\|(?P<text>.*?)\]\]", r"[[\g<page>|\g<text>]]", text)
    text = re.sub(r"\[\[(?::w)?:?" + lang + r":(?P<page>[^|\]]+)\]\]", r"[[\g<page>]]", text)
    text = re.sub(r"\{\{wh\|(.*?)\}\}", r"[[\1]]", text) # {{wh}} is sometimes used for hu: links
    text = re.sub(r"\[\[(?P<page>[^|]+)\|(?P=page)\]\]", r"[[\g<page>]]", text)
    return text

def translate(text):
    return wikipedia.translate(homeWiki, text) % translate_dict

# FIXME
honapok = [u'január', u'február', u'március', u'április', u'május', u'június', u'július',
           u'augusztus', u'szeptember', u'október', u'november', u'december']

#XXX wikipedia.stopme()?
arg = wikipedia.handleArgs()
if len(arg) == 0:
    wikipedia.output(u'Nem kaptam paramétert! Honnan tudjam melyik havi adagot másoljam?')
    sys.exit()
elif not (arg[0][0:2] == u'--' and honapok.count(arg[0][2:]) == 1):
    wikipedia.output(u'Hibás paraméter!')
    sys.exit()

date = datetime.date.today()
if True: # XXX month argument required for now
  date = datetime.date(date.year, honapok.index(arg[0][2:]) + 1, 1)
elif date > date.replace(day = 15): # probably intended for next month
  date += datetime.timedelta(days = calendar.monthrange(year, month)[1])

#XXX
monthname = arg[0][2:].capitalize()

# XXX hogy kéne ezt normálisan?
# dict used for the l10n substitutions
translate_dict  = {
    'year':      date.year,
    'month':     date.month,
    'monthname': monthname,
    'monthnamei':monthname.lower(),
    'lang':      homeWiki.language(),
    'filename':  None,
    'desc':      None,
}
 
try:
    records = ''
    links = []

    for day in range(1, calendar.monthrange(date.year, date.month)[1] + 1):
        date = date.replace(day=day)
        translate_dict['day'] = day
        del translate_dict['filename']
        del translate_dict['desc']
        
        # get image name
        page = wikipedia.Page(commons, 'Template:Potd/%s' % date.isoformat())
        text = page.get()
        m = commons_filename_re.match(text)
        translate_dict['filename'] = m.group('filename') if m else oldcat_re.sub('', text)        
        
        # get description
        page = wikipedia.Page(commons, 'Template:Potd/%s (%s)' % (date.isoformat(), homeWiki.language()))
        text = page.get()
        m = commons_desc_re.match(text)
        desc = m.group('desc') if m else oldcat_re.sub('', text)
        translate_dict['desc'] = fix_links(desc, homeWiki.language())
        
        # copy stuff
        page = wikipedia.Page(homeWiki, translate(potd_filename_page))
        page.put(translate(potd_filename_text), translate(potd_summary))
        page = wikipedia.Page(homeWiki, translate(potd_desc_page))
        page.put(translate(potd_desc_text), translate(potd_summary))
 
        # get links
        page = wikipedia.Page(homeWiki, translate(potd_desc_page)) # required because put doesn't refresh internal cache
        links.extend(page.linkedPages())
 
        records += translate(archive_record)

    translate_dict['records'] = records
    page = wikipedia.Page(homeWiki, translate(archive_page))
    page.put(translate(archive_text), translate(archive_summary))
    
    redlinks = u''
    for page in links:
      if page.exists():
        continue
      redlinks += u'* [[%s]]\n' % page.title()
    translate_dict['redlinks'] = redlinks
    page = wikipedia.Page(homeWiki, translate(redlink_notify_page))
    section_header = u'\n\n== %s ==\n\n' % translate(redlink_notify_title)
    page.put(page.get() + section_header + translate(redlink_notify_text), translate(redlink_notify_title), botflag = False, minorEdit = False) # TODO még így is bot módban van

finally:
    wikipedia.stopme()
