# Copyright @ 2023, Adrian Blakey. All rights reserved
# Runs the microdot webserver
# Reads the BT files that accumulate on the sserver, displays them in
# multiple blocks of the browser
# 1 input = as is
# 2 inputs split top and bottom
# 3 inputs split in half with top 1, bottom left 2, bottom right 3
# 4 input quadrants
# 5 inputs 2 at top, 3 at bottom
# 6 input 3 top, 3 bottom
# 7 inputs 3 top, 4 bottom
# 8 inputs 4 and 4
# GPS
#    Several ways to get GPS
#    Use the python ip method - very inaccurate
#    USB dongle
#    Chrome selenium web driver - pain in the neck
#    Prompt and web form to input it once and save it
#    Collect transmit it over BT from a phone

import os
from microdot_asyncio import Microdot, Response, send_file
from microdot_utemplate import render_template
from microdot_asyncio_websocket import with_websocket

import asyncio
import logging
import requests
import base64

import geocoder
import json
import jsonpickle
from json import JSONEncoder
import time
from geopy.distance import lonlat, distance
import socket
import requests

# Set up logging
logging.basicConfig()
logging.root.setLevel(logging.NOTSET)
logging.basicConfig(level=logging.NOTSET)
log = logging.getLogger("web_bt")

GPS_LOC: str = 'mygps.json'
TRACK: str = 'track-castle.json'
TRACK: str = 't.json'#

class Geo(object):
    def __init__(self, lat, long):
        self.lat: float = lat
        self.long: float = long


class Record(object):
    def __init__(self, car, datestamp, owner, time):
        self.car = car
        self.datestamp = datestamp
        self.owner = owner
        self.time = time


class Segment(object):
    def __init__(self, id: int, interval, acum, tulip):
        self.id: int = id
        self.interval: int = interval
        self.acum: int = acum
        self.tulip: str = tulip


class T(object):
    def __init__(self, name: str):
        self.name: str = name

class Track(object):
    def __init__(self, name, address, geo, lanes, rotations, svgfile, direction, laneseparation, records, length, segments):
        self.name: str = name
        self.address: str = address
        self.geo: Geo = geo
        self.lanes: list[str] = lanes
        self.rotations: list[str] = rotations
        self.svgfile: str = svgfile
        self.direction: str = direction
        self.laneseparation: float = laneseparation
        self.records: list[Record] = records
        self.length: float = length
        self.segments: list[Segment] = segments

    def geo(self) -> Geo:
        return self.geo


def internet_connection():
    # Determine if we have an internet connection
    # TODO get my ip address - if I have one also find the router address - might be locally connected
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(("www.google.com", 80))
        return True
    except socket.error:
        return False
    finally:
        sock.close()


def gps_location() -> (str, str):
    # Obtain my gps coordinates
    if os.path.isfile(GPS_LOC):
        with open(GPS_LOC) as f:
            gps = json.load(f)
            return gps['lat'], gps['long']
    else:
        # If you have an ip connection use the lame-ass python ip to populate the
        if internet_connection():
            g = geocoder.ip('me')
            return g.latlng[0], g.latlng[1]
        else:
            # TODO See if we have a BT connection to something other than a logger and ask it?
            # TODO put a prompt on the web page
            return '0.0', '0.0'


def saved_track():
    # TODO Refresh it if we have a connection
    log.debug('Saved track')
    """
    t = T('foo')
    frozen = jsonpickle.encode(t)     # unpicklable=False
    log.debug('frozen %s', frozen)
    """
    if os.path.isfile(TRACK):
        with open(TRACK) as f:
            log.debug('Saved track found')
            j = f.read()
            a_track = jsonpickle.decode(j, classes=[T])  #  classes='Track'
            log.debug(a_track, type(a_track))
            return a_track


def download_track():
    # Get the track db, if we already know who we are
    url = 'https://api.github.com/repos/adrianblakey/slot-car-tracks/contents/tracks.json'
    req = requests.get(url)
    if req.status_code == requests.codes.ok:
        req = req.json()  # the response is a JSON
        # req is now a dict with keys: name, encoding, url, size ...
        # and content. But it is encoded with base64.
        # log.debug(req['name'], req['content'])
        content = base64.b64decode(req['content'])
        tracks = json.loads(content)
        # log.debug(tracks)
        # log.debug(tracks[0]['name'])
        for key in tracks:
            lat: float = float(key['geo']['lat'])
            long: float = float(key['geo']['long'])
            thisloc = (lat, long)
            #dist = distance(lonlat(*myloc), lonlat(*thisloc)).miles
            #log.debug('key %s distance %s', key, dist)
            #if (dist <= 5):
            #    log.debug('key %s close', key['name'])
    else:
        print('Content was not found.')


def track() -> Track:
    # See if we have the track saved locally already
    # If not use our gps to get it
    #
    log.debug('Get track data')
    track = saved_track()  # we know who we are
    if not track:
        download_track()
    else:
        return track


my_track = track()

global server
server: Microdot = Microdot()
Response.default_content_type = 'text/html'


# root route
@server.route('/')
async def index(request):
    # return microdot_utemplate.render_template('index.html')
    return render_template('index_p.html')

"""
@server.route('/ws')
@with_websocket
async def send_data(request, ws):
    while True:
        # log.debug('Logging state %s', the_foo.state())
        # TODO apply some smoothing by capturing say 1 every ms and emitting the smoothed value
        await ws.send('12.0,12.0,12.0')
        time.sleep(0.0010)  # 10ms same as collection frequency
"""

# Static CSS/JSS
@server.route("/static/<path:path>")
def static(request, path):
    if ".." in path:
        # directory traversal is not allowed
        return "Not found", 404
    return send_file("static/" + path)


# shutdown
@server.get('/shutdown')
def shutdown(request):
    request.app.shutdown()
    return 'The server is shutting down...'


async def main():
    tasks = list()
    tasks.append(asyncio.create_task(server.start_server(host='0.0.0.0', port=80, debug=True, ssl=None)))
    res = await asyncio.gather(*tasks)


try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()