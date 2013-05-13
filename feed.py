#!/usr/bin/env python
# -*- coding: utf-8 -*-

import feedparser
import urllib
import re
import sys
import os
import subprocess
from xml.etree.cElementTree import parse, tostring
from werkzeug.contrib.atom import AtomFeed
from datetime import datetime
from glob import glob


base_url = 'https://moeffju.net/data/rp13'

schedule = parse('rp13-schedule.xml')

feed_urls = ['https://gdata.youtube.com/feeds/api/users/republica2010/uploads?max-results=50&start-index=%s' %
             i for i in range(0, 300, 50)]
feed_content = ''
for url in feed_urls:
    print >>sys.stderr, url
    feed_content += urllib.urlopen(url).read()
ytfeed = feedparser.parse(feed_content)

feed = AtomFeed("re:publica 2013: Audio", feed_url="%s/audio.atom" % base_url,
                subtitle="Audio feed of re:publica 2013 sessions")

for entry in ytfeed.entries:
    try:
        event_id = re.search('Find out more at: http://13.re-publica.de/node/(\d+)', entry['summary']).group(1)
        ytid = re.search('http://gdata.youtube.com/feeds/api/videos/(.*)', entry['id']).group(1)
    except AttributeError as e:
        print >>sys.stderr, "Skipping entry: %s" % entry['title']
        continue
    print >>sys.stderr, "ID %s / YTID %s: %s" % (event_id, ytid, entry['title'])

    event = schedule.find('.//event[@id="%s"]' % event_id)
    fns = glob('*%s.mp3' % ytid) + glob('*%s.ogg' % ytid)
    if len(fns) > 0:
        print >>sys.stderr, "Matched: %s" % ', '.join(fns)
    else:
        print >>sys.stderr, "Downloading: %s" % ytid
        subprocess.call('youtube-dl --extract-audio --audio-format mp3 -c -f 18 -- "https://www.youtube.com/watch?v=%s" >&2' % ytid, shell=True)
        fns = glob('*%s.mp3' % ytid) + glob('*%s.ogg' % ytid)
    links = []
    links.append({'href': "https://www.youtube.com/watch?v=%s" % ytid, 'rel': 'alternate', 'type': 'text/html'})
    for fn in fns:
        if fn[-3:] == 'ogg':
            links.append({'href': "%s/%s" % (base_url, fn), 'rel': 'enclosure',
                         'type': 'audio/ogg; codecs=vorbis', 'length': os.path.getsize(fn)})
        elif fn[-3:] == 'mp3':
            links.append({'href': "%s/%s" % (base_url, fn), 'rel': 'enclosure',
                         'type': 'audio/mpeg', 'length': os.path.getsize(fn)})

    try:
        content = event.find('description').text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        content = re.sub('<img[^>]*>', '(Image removed)', content)
    except:
        content = ''

    try:
        summary = event.find('abstract').text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    except:
        summary = ''

    feed.add(title=event.find('title').text,
             title_type='html',
             content=content,
             summary=summary,
             id="tag:moeffju.net,%s:rp13,audio,%s,%s" % (datetime.strptime(entry['published'], '%Y-%m-%dT%H:%M:%S.000Z').strftime('%Y-%m-%d'), event_id, ytid),
             author=[e.text for e in event.findall('.//person')],
             rights="Creative Commons Attribution-ShareAlike 3.0 Germany (CC BY-SA 3.0 DE)",
             updated=datetime.strptime(entry['updated'], '%Y-%m-%dT%H:%M:%S.000Z'),
             published=datetime.strptime(entry['published'], '%Y-%m-%dT%H:%M:%S.000Z'),
             links=links,
             )

print feed.to_string().encode('utf-8')
