#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
WLM 2013 bot to read lists from [[A magyar állam tulajdonában álló műemlékek listája]] and load them into a database
"""

import ConfigParser, json, codecs, unicodedata, sys, pg8000, re
from pg8000 import DBAPI
from decimal import Decimal

import wikipedia as pywikibot

# internal globals for DB access
g_conn, g_cursor = None, None

# normal globals

config = ConfigParser.ConfigParser()
config.readfp(codecs.open('wlm_config.ini', 'r', 'utf-8'))

# DB fields which correspond to template fields
template_based_db_fields = (
    'azonosito', 'kep', 'commonskat', 'megnevezes', 'szocikk', 'regio', 
    'iranyitoszam', 'telepules', 'kerulet', 'cim', 'helyrajzi_szam', 'statusz', 'leiras',
    'szelesseg', 'hosszusag',
)

class NoCoordinateForMonument(Exception):
    pass

class TemplateNotFound(Exception):
    pass

def get_cursor():
    global g_cursor, g_conn
    if g_cursor == None:
        conf = {str(key): str(val) for (key, val) in config.items('database')}
        conf['port'] = int(conf['port'])
        g_conn = DBAPI.connect(**conf)
        g_cursor = g_conn.cursor()
    return g_cursor

def close_connection(commit = True):
    if commit:
        g_conn.commit()
    else:
        g_conn.rollback()
    g_conn.close()

def iterate_lists():
    list_of_lists = pywikibot.Page(pywikibot.Site('hu', 'wikipedia'), config.get('wikipedia', 'list_of_lists'))
    for page in list_of_lists.linkedPages():
        yield page

def iterate_monuments(with_page = False):
    for page in iterate_lists():
        for params in iterate_monuments_on_page(page):
            if (with_page):
                yield params, page
            else:
                yield params

def iterate_monuments_on_page(page):
    for (tpl, params) in pywikibot.extract_templates_and_params(page.get()):
        if tpl != u'műemlék':
            continue
        yield params

def tokenize(s):
    """make template key into db field name"""
    return strip_accents(s.lower())

def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if not unicodedata.combining(c))

def template_data_to_db_data(data):
    return {tokenize(field): value for field, value in data.iteritems() if value and tokenize(field) in template_based_db_fields}

def has_location(db_data):
    return bool(db_data.get('szelesseg') and db_data.get('hosszusag')) # keys exist and not empty string

def replace_location(db_data):
    """replaces lat/long with a single PostGIS value in a dict"""
    if has_location(db_data):
        db_data['loc'] = 'POINT(%f %f)' % (Decimal(db_data['szelesseg']), Decimal(db_data['hosszusag']))
    # delete lat/long
    db_data.pop('szelesseg', None)
    db_data.pop('hosszusag', None)

def create_insert_sql(db_data):
    """insert data iff it is not in there yet"""
    sql = "INSERT INTO monuments2013 (%s) SELECT %s WHERE NOT EXISTS (SELECT 1 FROM monuments2013 WHERE azonosito = %s)"
    sql_fields = []
    sql_values = []
    params = []
    for key, value in db_data.iteritems():
        sql_fields.append(key)
        if key == 'loc':
            sql_values.append('ST_GeomFromText(%s, 4326)')
        else:
            sql_values.append('%s')
        if key == 'azonosito':
            params.append(int(value))
        else:
            params.append(value)
    sql = sql % (', '.join(sql_fields), ', '.join(sql_values), db_data['azonosito'])
    return sql, params

def create_update_sql(db_data):
    sql = "UPDATE monuments2013 SET "
    sql_fields = []
    params = []
    for key, value in db_data.iteritems():
        if key == 'loc':
            sql_fields.append('loc = ST_GeomFromText(%s, 4326)')
        elif key == 'azonosito':
            continue
        else:
            sql_fields.append(key + ' = %s')
        params.append(value)
    sql += ', '.join(sql_fields)
    sql += " WHERE azonosito = %s"
    params.append(int(db_data['azonosito']))
    return sql, params

def execute(sql, params):
    cursor = get_cursor()
    try:
        cursor.execute(sql, params)
    except pg8000.errors.ProgrammingError:
        print sql % tuple(params)
        raise

def show_progress():
    sys.stderr.write('.')
    sys.stderr.flush()

def geo_json_to_lat_long(geo_json):
    try:
        geo = json.loads(geo_json)
    except:
        print 'json decode error', geo_json
        raise
    return geo['coordinates'][0], geo['coordinates'][1]

def iterate_monuments_where_loc_can_be_updated_from_old_data():
    cursor = get_cursor()
    cursor.execute("""
        SELECT uj.azonosito, ST_AsGeoJSON(regi.loc)
        FROM monuments2013 uj JOIN monuments regi ON uj.azonosito = regi.azonosito
        WHERE uj.loc IS NULL AND regi.loc IS NOT NULL
    """)
    azonosito, geo_json = cursor.fetchone()
    szelesseg, hosszusag = geo_json_to_lat_long(geo_json)
    yield azonosito, szelesseg, hosszusag

def get_old_coordinates_for_monument(azonosito):
    cursor = get_cursor()
    cursor.execute("""
        SELECT ST_AsGeoJSON(regi.loc)
        FROM monuments2013 uj LEFT JOIN monuments regi ON uj.azonosito = regi.azonosito
        WHERE uj.azonosito = %s
    """, (int(azonosito),))
    row = cursor.fetchone()
    if row and row[0]:
        geo_json = row[0]
    else:
        raise NoCoordinateForMonument
    return geo_json_to_lat_long(geo_json)

def fill_coordinates_on_page(old_text, azonosito, szelesseg, hosszusag):
    re_monument_template = re.compile(ur"""
        \{\{ \s* műemlék\b
            [^}]*
            \| \s* azonosító \s* = \s* %s
            [^}]*
        \}\}
    """ % (azonosito,), re.IGNORECASE + re.UNICODE + re.VERBOSE)
    match = re_monument_template.search(old_text)
    if not match:
        raise TemplateNotFound
    template_text = match.group(0)
    template_text = re.sub(ur'(\|\s*szélesség\s*=\s?)\s*\n', r'\g<1>%f\n' % szelesseg, template_text)
    template_text = re.sub(ur'(\|\s*hosszúság\s*=\s?)\s*\n', r'\g<1>%f\n' % hosszusag, template_text)
    new_text = old_text[:match.start()] + template_text + old_text[match.end():]
    return new_text

#################
# main functions#
#################

def save_template_data():
    for data in iterate_monuments():
        db_data = template_data_to_db_data(data)
        replace_location(db_data)
        try:
            execute(*create_insert_sql(db_data))
            execute(*create_update_sql(db_data))
        except pg8000.errors.ProgrammingError:
            raise
        except:
            print db_data
            raise
        show_progress()
    close_connection()

def update_template_coordinates():
    for page in iterate_lists():
        old_text = page.get()
        new_text = old_text
        for data in iterate_monuments_on_page(page):
            old_text = new_text
            try:
                db_data = template_data_to_db_data(data)
                if not has_location(db_data):
                    #szelesseg, hosszusag = get_old_coordinates_for_monument(db_data['azonosito'])
                    hosszusag, szelesseg = get_old_coordinates_for_monument(db_data['azonosito']) # FIXME forditva vannak a DB-ben?
                    pywikibot.output(
                        "adding coordinates: \03{lightyellow}%s\03{default} - %s -> (\03{lightyellow}%s\03{default}, \03{lightyellow}%s\03{default})" 
                        % (db_data['azonosito'], page.title(), szelesseg, hosszusag)
                    )
                    new_text = fill_coordinates_on_page(old_text, db_data['azonosito'], szelesseg, hosszusag)
                    pywikibot.showDiff(old_text, new_text)
            except NoCoordinateForMonument:
                pass
            except pg8000.errors.ProgrammingError:
                raise
            except:
                print db_data
                raise
        page.put(new_text, comment = u'Koordináták beszúrása', botflag=False)

def main(*args):
    save_template_data()
    #update_template_coordinates()

if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()
