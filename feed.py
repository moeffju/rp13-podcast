#!/usr/bin/env python
# -*- coding: utf-8 -*-

import feedparser
import urllib
import re
import sys
import os
import subprocess
import json
from xml.etree.cElementTree import parse, fromstring, tostring
from werkzeug.contrib.atom import AtomFeed
from collections import defaultdict
from datetime import datetime
from glob import glob


base_url = 'https://moeffju.net/data/rp13'
DO_DOWNLOAD = True


def get_schedule():
    if os.path.exists('rp13-schedule.xml'):
        print >>sys.stderr, "Loading rp13 schedule XML…"
        schedule = parse(open('rp13-schedule.xml'))
    else:
        print >>sys.stderr, "Fetching rp13 schedule XML…"
        schedule = fromstring(urllib.urlopen('http://re-publica.de/rp13-schedule.xml').read())
    return schedule


def get_known_videos():
    if os.path.exists('knownvideos.json'):
        print >>sys.stderr, "Loading list of known videos…"
        known_videos = json.load(open('knownvideos.json'))
    else:
        print >>sys.stderr, "Fetching list of known videos…"
        known_videos = json.loads(urllib.urlopen('http://michaelkreil.github.io/republicavideos/data/knownvideos.json').read())
    return known_videos


def get_youtube_feed(num_results=200):
    sys.stderr.write("Fetching YouTube video feed")
    feed_urls = ['https://gdata.youtube.com/feeds/api/users/republica2010/uploads?max-results=50&start-index=%s' %
                 i for i in range(0, num_results, 50)]
    feed_content = ''
    for url in feed_urls:
        feed_content += urllib.urlopen(url).read()
        sys.stderr.write('.')
    ytfeed = feedparser.parse(feed_content)
    sys.stderr.write("\n")
    return ytfeed


def get_youtube_video(video_id):
    # print >>sys.stderr, "[%s] loading video data" % video_id
    video_url = 'http://gdata.youtube.com/feeds/api/videos/%s?v=2' % video_id
    feed = feedparser.parse(urllib.urlopen(video_url).read())
    return feed.entries[0]


def get_session_info(session_id):
    event = schedule.find('.//event[@id="%s"]' % session_id)

    title = authors = summary = description = start = room = track = ''
    try:
        title = event.find('title').text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        start = event.find('start').text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        room = event.find('room').text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        track = event.find('track').text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        authors = [e.text for e in event.findall('.//person') if e.text is not None]
        summary = event.find('abstract').text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        description = re.sub('<img[^>]*>', '(Image removed)', event.find(
            'description').text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&'))
    except AttributeError:
        pass

    return {'description': description, 'summary': summary, 'authors': authors, 'title': title, 'room':room, 'track':track, 'start':start}


def find_files_for_id(video_id):
    return glob('*%s.mp3' % video_id) + glob('*%s.ogg' % video_id)


def get_file_for_id(video_id):
    print >>sys.stderr, "[%s] downloading file" % ytid
    if DO_DOWNLOAD:
        res = subprocess.call(
            'youtube-dl --extract-audio --audio-format mp3 -c -f 18 -- "https://www.youtube.com/watch?v=%s" >&2' % ytid, shell=True)
        return res
    else:
        open('%s.mp3' % video_id, 'w')
        return True


try:
    if sys.argv[1] == '-n':
        DO_DOWNLOAD = False
except IndexError:
    pass

youtube_feed = get_youtube_feed(200)
known_videos = get_known_videos()
schedule = get_schedule()

feed = AtomFeed("re:publica 2013: Audio", feed_url="%s/audio.atom" % base_url,
                subtitle="Audio feed of re:publica 2013 sessions")

for ytid, data in known_videos.items():
    if data == {}:
        # print >>sys.stderr, "%s: no data, skipped" % ytid
        continue
    if data['gesperrt']:
        print >>sys.stderr, "[%s] RESTRICTED, skipping" % ytid
        continue

    event_id = data['eventId']

    files = find_files_for_id(ytid)
    session_info = get_session_info(event_id)

    print >>sys.stderr, "[%s]" % ytid
    print >>sys.stderr, "[%s] %s: %s, %s: \"%s\" - %s" % (ytid, event_id, session_info['start'], session_info['room'], session_info['title'], ', '.join(session_info['authors']))

    try:
        matches = [entry for entry in youtube_feed.entries if entry['id'][-11:] == ytid]
        # print >>sys.stderr, "[%s] %d matches in feed" % (ytid, len(matches))
        video_info = matches[0]
    except IndexError:
        video_info = get_youtube_video(ytid)
        # print >>sys.stderr, "[%s] uploader: '%s'" % (ytid, video_info['author'])

    tag_tst = datetime.strptime(video_info['published'], '%Y-%m-%dT%H:%M:%S.000Z').strftime('%Y-%m-%d')

    if len(files) == 0:
        get_file_for_id(ytid)
        files = find_files_for_id(ytid)
    if len(files) == 0:
        print >>sys.stderr, "[%s] ERROR getting file, skipping" % ytid
        continue

    links = []
    links.append({'href': "https://www.youtube.com/watch?v=%s" % ytid, 'rel': 'alternate', 'type': 'text/html'})
    for fn in files:
        if fn[-3:] == 'ogg':
            links.append({'href': "%s/%s" % (base_url, fn), 'rel': 'enclosure',
                         'type': 'audio/ogg; codecs=vorbis', 'length': os.path.getsize(fn)})
        elif fn[-3:] == 'mp3':
            links.append({'href': "%s/%s" % (base_url, fn), 'rel': 'enclosure',
                         'type': 'audio/mpeg', 'length': os.path.getsize(fn)})

    feed.add(title=session_info['title'],
             title_type='html',
             content=session_info['description'],
             summary=session_info['summary'],
             id="tag:moeffju.net,%s:rp13,audio,%s,%s" % (tag_tst, event_id, ytid),
             author=session_info['authors'],
             rights="Creative Commons Attribution-ShareAlike 3.0 Germany (CC BY-SA 3.0 DE)",
             updated=datetime.strptime(video_info['updated'], '%Y-%m-%dT%H:%M:%S.000Z'),
             published=datetime.strptime(video_info['published'], '%Y-%m-%dT%H:%M:%S.000Z'),
             links=links,
             )

print feed.to_string().encode('utf-8')
