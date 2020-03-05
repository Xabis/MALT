# Copyright (c) 2017, Carl Lewis
#
# This source code is released under the MIT license
# https://opensource.org/licenses/MIT

from base import AnimeService
from ..database import AnimeItem, AnimeDatabase
import os, urllib, urllib2
import xml.etree.cElementTree as ET
import base64

# Note about the state of MAL API:
#    As of this writing, the myanimelist API is dead. This is left for historical purposes, or if the api comes back
#    online sometime in the future. It is possible that MAL will make changes to the endpoints if so.

#MAL
_FETCH_URL = "http://myanimelist.net/malappinfo.php?u={0}&status=all"
_PUSH_URL = "https://myanimelist.net/api/animelist/update/{0}.xml"
_ASYNC_URL = "https://myanimelist.net/api/anime/search.xml?{0}"

#Mock
#_FETCH_URL = "http://localhost:3000/malappinfo.php?u={0}&status=all"
#_PUSH_URL = "http://localhost:3000/api/animelist/update/{0}.xml"
#_ASYNC_URL = "http://localhost:3000/api/anime/search.xml?{0}"

def getnodetext(node, tag):
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text

def getnodeint(node, tag):
    child = node.find(tag)
    if child is None or child.text is None:
        return 0
    try:
        return int(child.text)
    except ValueError:
        return 0

class MALService(AnimeService):
    def __init__(self, addon):
        self.Addon = addon
        self._user = self.getsetting("maltMalUser")
        self._pass = self.getsetting("maltMalPass")
        self._badauth = False

    @property
    def relationship_index(self):
        return 0

    @property
    def id(self):
        return "mal"

    @property
    def cansync(self):
        return self.user and self.password and not self.badauth

    @property
    def hasAsyncInfo(self):
        return True

    @property
    def user(self):
        return self._user
    
    @user.setter
    def user(self, value):
        if self._user != value:
            self._user = value
            self._badauth = False

    @property
    def password(self):
        return self._pass
    
    @password.setter
    def password(self, value):
        if self._pass != value:
            self._pass = value
            self._badauth = False

    @property
    def authchanged(self):
        ischanged = False

        # Check if the user has been changed
        user = self.getsetting("maltMalUser")
        if user != self.user:
            self.user = user
            ischanged = True

        # Check if the password has been changed
        password = self.getsetting("maltMalPass")
        if password != self.password:
            self.password = password
            ischanged = True

        return ischanged

    def fetch(self, db, progress):
        """Fetch the current state of the list from MAL"""

        # Sample fetch payload
        # <anime>
        #     <series_animedb_id>21</series_animedb_id>
        #     <series_title>One Piece</series_title>
        #     <series_synonyms>; One Piece</series_synonyms>
        #     <series_type>1</series_type>
        #     <series_episodes>0</series_episodes>
        #     <series_status>1</series_status>
        #     <series_start>1999-10-20</series_start>
        #     <series_end>0000-00-00</series_end>
        #     <series_image>https://myanimelist.cdn-dena.com/images/anime/6/73245.jpg</series_image>
        #     <my_id>0</my_id>
        #     <my_watched_episodes>770</my_watched_episodes>
        #     <my_start_date>0000-00-00</my_start_date>
        #     <my_finish_date>0000-00-00</my_finish_date>
        #     <my_score>0</my_score>
        #     <my_status>1</my_status>
        #     <my_rewatching>0</my_rewatching>
        #     <my_rewatching_ep>0</my_rewatching_ep>
        #     <my_last_updated>1487768892</my_last_updated>
        #     <my_tags></my_tags>
        # </anime>

        if not self.cansync or not isinstance(db, AnimeDatabase):
            return False

        response = urllib2.urlopen(_FETCH_URL.format(self._user)).read()
        root = ET.fromstring(response)

        # load the nodes into the database
        nodes = root.findall("anime")
        for node in nodes:
            animeid = getnodetext(node, "series_animedb_id")

            if animeid in db:
                anime = db[animeid]
                anime.state = getnodetext(node, "series_status")
                anime.episodes = getnodetext(node, "series_episodes")
                anime.datestart = getnodetext(node, "series_start")
                anime.dateend = getnodetext(node, "series_end")
                anime.status = getnodetext(node, "my_status")
                anime.updated = getnodeint(node, "my_last_updated")
                anime.watched_server = getnodetext(node, "my_watched_episodes")

            else:
                anime = AnimeItem(self)
                anime._id = animeid
                anime._art = getnodetext(node, "series_image")
                anime.title = getnodetext(node, "series_title")
                anime.type = getnodetext(node, "series_type")
                anime.state = getnodetext(node, "series_status")
                anime.synonyms = getnodetext(node, "series_synonyms")
                anime.episodes = getnodetext(node, "series_episodes")
                anime.datestart = getnodetext(node, "series_start")
                anime.dateend = getnodetext(node, "series_end")
                anime.status = getnodetext(node, "my_status")
                anime.updated = getnodeint(node, "my_last_updated")
                anime.synopsis = getnodetext(node, "synopsis")
                anime.score = getnodetext(node, "score")
                anime.watched = getnodetext(node, "my_watched_episodes")
                anime.watched_server = anime.watched
                db.add_anime(anime)

        progress(1)
        return True

    def requiresAsyncFetch(self, anime):
        return not anime.synopsis

    def fetchAsyncInfo(self, db, anime):
        # Do not fetch if the required info is already downloaded
        if not self.requiresAsyncFetch(anime):
            return

        try:
            # Make the request to MAL. This function is not throttled, so care must be taken
            encodedauth = base64.encodestring('%s:%s' % (self.user, self.password)).replace('\n', '')
            headers = {'Content-Type': 'application/x-www-form-urlencoded',
                       'Authorization': 'Basic %s' % encodedauth}

            req = urllib2.Request(_ASYNC_URL.format(urllib.urlencode({'q': anime.title.encode('utf8')})), headers=headers)
            response = urllib2.urlopen(req)
            output = response.read()

            # MAL will return an empty string if there are no results
            if output:
                # Thanks to a terrible API, we are forced to do a search rather than just resolving using the id
                #   as a result, multiple results can be returned. May as well update all we can!
                #   Note that it is possible that some shows wont return the data we were after as a result of this.
                root = ET.fromstring(output)
                nodes = root.findall("entry")
                for node in nodes:
                    child = node.find("id")
                    if child is None:
                        continue
                    key = child.text

                    # If item already exists, then simply update it, otherwise create and add it
                    if key in db:
                        dbitem = db[key]
                        dbitem.synopsis = getnodetext(node, "synopsis")
                        dbitem.score = getnodetext(node, "score")

                # Return whether the search yielded info for the entry that was passed in
                if anime.synopsis:
                    return True

        except urllib2.HTTPError, e:
            if e.code == 401:
                self._badauth = True
            raise e

        return False

    def push(self, anime):
        """Push the update to MAL, if enabled"""
        if self.cansync:
            encodedauth = base64.encodestring('%s:%s' % (self._user, self._pass)).replace('\n', '')
            headers = {'Content-Type': 'application/x-www-form-urlencoded',
                        'Authorization': 'Basic %s' % encodedauth}
            data = urllib.urlencode(
                {'data': '<entry><status>{0}</status><episode>{1}</episode></entry>'.format(anime.status, anime.watched)})

            try:
                req = urllib2.Request(_PUSH_URL.format(anime.id), data, headers)
                response = urllib2.urlopen(req)
                output = response.read()
                if output == "Updated":
                    # Flag the item as synced then finalize
                    anime.synced()
                    return True

                raise Exception(
                    "MAL update failed: Authentication was successful, but API did not return 'Updated'",
                    "MAL response: {0}".format(output)
                )

            except urllib2.HTTPError, e:
                if e.code == 401:
                    self._badauth = True
                raise e

        return False