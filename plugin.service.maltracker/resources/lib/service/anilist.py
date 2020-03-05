# Copyright (c) 2017, Carl Lewis
#
# This source code is released under the MIT license
# https://opensource.org/licenses/MIT

import xbmc, xbmcgui
from base import AnimeService
from ..database import AnimeItem, AnimeDatabase
import os, urllib2
import json
from datetime import datetime
import webbrowser

_API_URL = "https://graphql.anilist.co/"
#_API_URL = "http://localhost:3000/graphql" # mock server
_OAUTH_URL = "https://anilist.co/api/v2/oauth/authorize?client_id=3155&response_type=token"

_format_lookup = {
    "TV": 1,
    "TV_SHORT": 1,
    "OVA": 2,
    "MOVIE": 3,
    "SPECIAL": 4,
    "ONA": 5,
    "MUSIC": 6
}

_state_lookup = {
    "RELEASING": 1,
    "FINISHED": 2,
    "NOT_YET_RELEASED": 3,
    "CANCELLED": 4,
}

_status_lookup = {
    "CURRENT": 1,
    "REPEATING": 1,
    "COMPLETED": 2,
    "PAUSED": 3,
    "DROPPED": 4,
    "PLANNING": 6,
    1: "CURRENT",
    2: "COMPLETED",
    3: "PAUSED",
    4: "DROPPED",
    6: "PLANNING"
}

#deep object getter
def getDeep(dictionary, keys, default=""):
    try:
        def comp(glob, key):
            if isinstance(glob, dict):
                return glob.get(key, default)
            if isinstance(glob, list):
                return glob[int(key)]
            return default
        return reduce(comp, keys.split("."), dictionary)
    except Exception:
        return default

class ALService(AnimeService):
    def __init__(self, addon):
        self.Addon = addon
        self._user = self.getsetting("maltAnilistUser")
        self._token = self.getsetting("maltAnilistToken")
        self._badauth = False

    @property
    def relationship_index(self):
        return 2

    @property
    def id(self):
        return "anilist"
    
    @property
    def cansync(self):
        return self.user and self.token and not self.badauth

    @property
    def hasAsyncInfo(self):
        return False

    @property
    def user(self):
        return self._user
    
    @user.setter
    def user(self, value):
        if self._user != value:
            self._user = value
            self._badauth = False

    @property
    def token(self):
        return self._token
    
    @token.setter
    def token(self, value):
        if self._token != value:
            self._token = value
            self._badauth = False

    @property
    def authchanged(self):
        ischanged = False

        # Check if the user has been changed
        user = self.getsetting("maltAnilistUser")
        if user != self.user:
            self.user = user
            ischanged = True

        # Check if the password has been changed
        token = self.getsetting("maltAnilistToken")
        if token != self.token:
            self.token = token
            ischanged = True

        return ischanged

    @staticmethod
    def FuzzyDate(obj):
        if obj and obj.get("year"):
            return datetime(obj.get("year"), obj.get("month") or 1, obj.get("day") or 1)
        return None

    def fetch(self, db, progress):
        """Fetch the current state of the list from MAL"""
        if not self.cansync or not isinstance(db, AnimeDatabase):
            return False

        query = """
            query ($id: String, $listType: MediaType, $page: Int) {
                Page(page: $page) {
                    pageInfo {
                        currentPage
                        lastPage
                        hasNextPage
                    }
                    mediaList(userName: $id, type: $listType) {
                        status
                        progress
                        score(format: POINT_100)
                        startedAt {
                            year
                            month
                            day
                        }
                        completedAt {
                            year
                            month
                            day
                        }
                        updatedAt
                        media {
                            id
                            format
                            title {
                                userPreferred
                                romaji
                            }
                            status
                            description
                            episodes
                            coverImage {
                                medium
                            }
                            synonyms
                            startDate {
                                year
                                month
                                day
                            }
                            endDate {
                                year
                                month
                                day
                            }
                            nextAiringEpisode {
                                airingAt
                                episode
                            }
                        }
                    }
                }
            }
        """

        variables = {
            'id': self.user,
            'listType': "ANIME"
        }

        headers = {
            'Content-Type' : 'application/json',
            'Accept'       : 'application/json',
            'User-Agent'   : 'MALT/1.0',               #required by cloudflare
            'Authorization': 'Bearer %s' % self.token  #required for private lists, so just sending regardless
        }

        try:
            count = 0
            while True:
                # Build Request
                req = urllib2.Request(_API_URL, headers=headers)
                response = urllib2.urlopen(req, data=json.dumps({
                    "query": query,
                    "variables": variables
                }))

                # Process Response
                respdata = json.loads(response.read())
                pageInfo = getDeep(respdata, "data.Page.pageInfo", None)
                if not pageInfo:
                    raise Exception("Bad response from server")

                for mediaList in getDeep(respdata, "data.Page.mediaList", None):
                    mediaItem = mediaList.get("media")
                    animeid = mediaItem.get("id")
                    if not animeid:
                        continue

                    #force id to a string due to command ipc marshalling and relationship rule processing
                    #   anilist will send back empty data as nulls, which dict.get will return as None instead of the default
                    #   instead, use a boolean op to force defaults
                    animeid = str(animeid)
                    if animeid in db:
                        # Item exists in the db, update
                        anime = db[animeid]
                        anime.state = _state_lookup.get(mediaItem.get("status") or "NOT_YET_RELEASED", 3)
                        anime.episodes = mediaItem.get("episodes") or 0
                        anime.synonyms = mediaItem.get("synonyms") or []
                        anime.synopsis = mediaItem.get("description")
                        anime.datestart = ALService.FuzzyDate(mediaItem.get("startDate"))
                        anime.dateend = ALService.FuzzyDate(mediaItem.get("endDate"))
                        anime.datenextair = getDeep(mediaItem, "nextAiringEpisode.airingAt")
                        anime.nextairepisode = getDeep(mediaItem, "nextAiringEpisode.episode")
                        anime.status = _status_lookup.get(mediaList.get("status") or "CURRENT", 1)
                        anime.updated = mediaList.get("updatedAt")
                        anime.watched_server = mediaList.get("progress") or 0
                    else:
                        # Item is new, add
                        anime = AnimeItem(self)
                        anime._id = animeid
                        anime._art = getDeep(mediaItem, "coverImage.medium", "")
                        anime.title = getDeep(mediaItem, "title.userPreferred") or "Unknown Title"
                        anime.type = _format_lookup.get(mediaItem.get("format") or "TV", 1)
                        anime.state = _state_lookup.get(mediaItem.get("status") or "NOT_YET_RELEASED", 3)
                        anime.synonyms = mediaItem.get("synonyms") or []
                        anime.episodes = mediaItem.get("episodes") or 0
                        anime.datestart = ALService.FuzzyDate(mediaItem.get("startDate"))
                        anime.dateend = ALService.FuzzyDate(mediaItem.get("endDate"))
                        anime.datenextair = getDeep(mediaItem, "nextAiringEpisode.airingAt")
                        anime.nextairepisode = getDeep(mediaItem, "nextAiringEpisode.episode")
                        anime.status = _status_lookup.get(mediaList.get("status") or "CURRENT", 1)
                        anime.updated = mediaList.get("updatedAt")
                        anime.synopsis = mediaItem.get("description")
                        anime.score = mediaList.get("score") or 0
                        anime.watched = mediaList.get("progress") or 0
                        anime.watched_server = anime.watched
                        db.add_anime(anime)

                # Set fetch progress
                current = pageInfo.get("currentPage", 1)
                last = pageInfo.get("lastPage", 0)
                progress(float(current) / last)

                # If there are more pages, then loop
                if not pageInfo.get("hasNextPage", False):
                    break
                variables["page"] = current + 1
                
                # Runaway failsafe
                count += 1
                if count >= last:
                    break

        except urllib2.HTTPError, e:
            if e.code == 401 or e.code == 404:
                self._badauth = True

            if e.headers.subtype == "json":
                respdata = json.loads(e.read())
                errors = respdata.get("errors")
                if errors:
                    norm = [item["message"] for item in errors]
                    raise Exception("Service returned code {0}".format(e.code), *norm)
            raise e

        except Exception, e:
            raise e

        return True

    def push(self, anime):
        """Push updates to Anilist"""
        if self.cansync:
            query = """
                mutation ($id: Int, $progress: Int, $status: MediaListStatus) {
                    SaveMediaListEntry (mediaId: $id, progress: $progress, status: $status) {
                        mediaId
                        progress
                        status
                    }
                }
            """

            iid = int(anime.id) #will be a critical error if this doesnt convert. i.e: bad data.
            variables = {
                'id': iid,
                'progress': anime.watched,
                'status': _status_lookup.get(anime.status, "CURRENT")
            }

            headers = {
                'Content-Type' : 'application/json',
                'Accept'       : 'application/json',
                'User-Agent'   : 'MALT/1.0',               #required by cloudflare
                'Authorization': 'Bearer %s' % self.token  #required for private lists, so just sending regardless
            }

            try:
                # Build Request
                req = urllib2.Request(_API_URL, headers=headers)
                response = urllib2.urlopen(req, data=json.dumps({
                    "query": query,
                    "variables": variables
                }))

                # Process Response
                respdata = json.loads(response.read())
                updateInfo = getDeep(respdata, "data.SaveMediaListEntry", None)
                if not updateInfo:
                    raise Exception("Bad response from service")

                # Check update status
                if updateInfo.get("mediaId") == iid and updateInfo.get("progress") == anime.watched:
                    anime.status = _status_lookup.get(updateInfo.get("status") or "CURRENT", 1)
                    anime.synced()
                    return True
                raise Exception("Service update did not return expected update confirmation")

            except urllib2.HTTPError, e:
                if e.code == 401 or e.code == 404:
                    self._badauth = True

                if e.headers.subtype == "json":
                    respdata = json.loads(e.read())
                    errors = respdata.get("errors")

                    if errors:
                        norm = [item["message"] for item in errors]
                        raise Exception("Service returned code {0}".format(e.code), *norm)
                raise e

            except Exception, e:
                raise e
        return False

    def authenticate(self):
        """Perform OAUTH authentication"""
        if xbmcgui.Dialog().yesno(self.getstring(334), self.getstring(335)):
            if webbrowser.open(_OAUTH_URL, new=2, autoraise=True):
                xbmcgui.Dialog().ok(self.getstring(334), self.getstring(337))
                return True
            else:
                xbmcgui.Dialog().ok(self.getstring(334), self.getstring(336))
        return False