# Copyright (c) 2017, Carl Lewis
#
# This source code is released under the MIT license
# https://opensource.org/licenses/MIT

import os, urllib2
from datetime import datetime, time
import json

from anitomy import *
from unicodedata import normalize
from .relations import Relationships
from collections import deque
from HTMLParser import HTMLParser
from service.base import AnimeService


# =====================================================================================================================
# Constants
# =====================================================================================================================
# Series Type
TV = 1
OVA = 2
MOVIE = 3
SPECIAL = 4
ONA = 5
MUSIC = 6

# Series Status
AIRING = 1
FINISHED = 2
NOTSTARTED = 3
CANCELLED = 4

# Watch Status
WATCHING = 1
COMPLETE = 2
ONHOLD = 3
DROPPED = 4
PLANTOWATCH = 6

# =====================================================================================================================
# Normalization
# =====================================================================================================================
_wordboundary = string.whitespace + string.punctuation
_roman = [["2", "II"], ["3", "III"], ["4", "IV"], ["5", "V"], ["6", "VI"], ["7", "VII"], ["8", "VIII"], ["9", "IX"], ["11", "XI"], ["12", "XII"], ["13", "XIII"]]
_transa = [["a", "@"], ["x", u"\u00D7"], [":", u"\uA789"], ["ou", u"\u014C"], ["ou", u"\u014D"], ["uu", u"\u016B"]]
_transb = [["ha", "wa"], ["he", "e"], ["wo", "o"]]
_ord = [["1st", "first"], ["2nd", "second"], ["3rd", "third"], ["4th", "fourth"], ["5th", "fifth"], ["6th", "sixth"], ["7th", "seventh"], ["8th", "eighth"], ["9th", "ninth"]]
_seasons = [["1", "1st season", "season 1", "series 1", "s1"],["2", "2nd season", "season 2", "series 2", "s2"],["3", "3rd season", "season 3", "series 3", "s3"],["4", "4th season", "season 4", "series 4", "s4"],["5", "5th season", "season 5", "series 5", "s5"],["6", "6th season", "season 6", "series 6", "s6"]]
_extra = [["and", "&"],["", "the animation", "the", "episode", "(tv)"],["ova", "oad", "oav"],["sp", "specials", "special"]]

def whole_replace(value, old, new):
    if old == "" or old == new or len(value) < len(old):
        return value

    pos = value.find(old)
    while pos != -1:
        end = pos + len(old)
        if not ((pos == 0 or value[pos - 1] in _wordboundary) and (end >= len(value) or value[end] in _wordboundary)):
            pos += len(old)
        else:
            value = value[:pos] + new + value[pos+len(old):]
            pos += len(new)
        pos = value.find(old, pos)
    return value

def replace_pairs(value, reps, whole):
    for rep in reps:
        new = rep[0]
        for idx in range(1, len(rep)):
            old = rep[idx]
            if whole:
                value = whole_replace(value, old, new)
            else:
                value = value.replace(old, new)
    return value

def normalize_title(value):
    value = replace_pairs(value, _roman, True)
    value = replace_pairs(value, _transa, False)
    value = replace_pairs(value, _transb, True)
    value = normalize('NFKD', value).encode('ascii', 'ignore') #deconstruct unicode and then remove the non-ascii extras
    value = value.lower()
    value = replace_pairs(value, _ord, True)
    value = replace_pairs(value, _seasons, True)
    value = replace_pairs(value, _extra, True)
    value = value.strip()

    # Remove all spaces and unicode punctuation
    out = ""
    for c in value:
        o = ord(c)
        if (o < 0xFF and not c.isalnum()) or (o > 0x2000 and o < 0x2767):
            pass
        else:
            out += c
    return out

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

def getTimeStamp(value):
    diff = value - datetime(1970, 1, 1)
    return int(diff.total_seconds()) #float to int conversion

# =====================================================================================================================
# Database
# =====================================================================================================================
class AnimeItem(object):
    _re_bbcode = re.compile("\[\/?(b|i|u|(size(=[0-9]+)?)|(url(=[^\]]*)?))\]")
    _re_tags = re.compile("<[^<]+?>")
    _html_parser = HTMLParser()

    # =================================================================================================================
    # Constructor
    # =================================================================================================================
    def __init__(self, db=None):
        self._db = db
        self._id = 0
        self._title = ""
        self._title_normalized = ""
        self._type = 0
        self._state = 0
        self._art = ""
        self._episodes = 0
        self._watched = 0
        self._watched_server = 0
        self._available = {}
        self._updated = None
        self._datestart = None
        self._dateend = None
        self._datenextair = None
        self._nextair_episode = 0
        self._synonyms = []
        self._synonyms_normalized = []
        self._usersyn = []
        self._usersyn_normalized = []
        self._status = 0
        self._synopsis = ""
        self._score = 0.0

    # =================================================================================================================
    # Properties
    # =================================================================================================================
    @property
    def db(self):
        return self._db

    @property
    def id(self):
        return self._id

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        if value != self._title:
            self._title = value
            self._title_normalized = ""

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, value):
        try:
            self._type = int(value)
        except:
            pass

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        try:
            self._state = int(value)
        except:
            pass

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        try:
            self._status = int(value)
        except:
            pass

    @property
    def art(self):
        return self._art

    @property
    def episodes(self):
        return self._episodes

    @episodes.setter
    def episodes(self, value):
        try:
            value = int(value)
            self._episodes = value
        except:
            pass

    @property
    def watched(self):
        return self._watched

    @watched.setter
    def watched(self, value):
        try:
            value = int(value)
            if value > 0 and (self.episodes == 0 or value <= self.episodes):
                self._watched = value
                if self.episodes > 0 and value == self.episodes:
                    self.status = COMPLETE
                elif self.status == COMPLETE or self.status == PLANTOWATCH:
                    # If already complete or in PTW, then set to watching, otherwise leave as-is
                    self.status = WATCHING
        except ValueError:
            pass

    @property
    def watched_server(self):
        return self._watched_server

    @watched_server.setter
    def watched_server(self, value):
        if value is None:
            return
        try:
            self._watched_server = int(value)
        except Exception:
            self._watched_server = self.watched

    @property
    def updated(self):
        return self._updated

    @updated.setter
    def updated(self, value):
        self._updated = AnimeItem.getdate(value)

    @property
    def datestart(self):
        return self._datestart

    @datestart.setter
    def datestart(self, value):
        self._datestart = AnimeItem.getdate(value)

    @property
    def dateend(self):
        return self._dateend

    @dateend.setter
    def dateend(self, value):
        self._dateend = AnimeItem.getdate(value)

    @property
    def datenextair(self):
        if self._datenextair and self._datenextair >= datetime.now():
            return self._datenextair
        return None

    @datenextair.setter
    def datenextair(self, value):
        self._datenextair = AnimeItem.getdate(value)

    @property
    def nextairepisode(self):
        return self._nextair_episode

    @nextairepisode.setter
    def nextairepisode(self, value):
        try:
            value = int(value)
            self._nextair_episode = value
        except:
            pass

    @property
    def available(self):
        return self._available

    @property
    def nextfile(self):
        nextepisode = self._watched + 1
        if nextepisode in self._available:
            return self._available[nextepisode]
        return None

    @property
    def synonyms(self):
        return self._synonyms

    @synonyms.setter
    def synonyms(self, value):
        if isinstance(value, str):
            value = value.split(";")

        arr = []
        if isinstance(value, list):
            for syn in value:
                syn = syn.strip()
                if syn:
                    arr.append(syn)
        self._synonyms = arr

    @property
    def usersynonyms(self):
        return self._usersyn

    @usersynonyms.setter
    def usersynonyms(self, value):
        if isinstance(value, str):
            value = value.split(";")

        arr = []
        if isinstance(value, list):
            for syn in value:
                syn = syn.strip()
                if syn:
                    arr.append(syn)
        self._usersyn = arr

    @property
    def synopsis(self):
        return self._synopsis

    @synopsis.setter
    def synopsis(self, value):
        self._synopsis = AnimeItem.decodetext(value)

    @property
    def score(self):
        return self._score

    @score.setter
    def score(self, value):
        try:
            value = float(value)
            self._score = value
        except:
            pass

    # =================================================================================================================
    # Methods
    # =================================================================================================================
    @staticmethod
    def getdate(value, format='%Y-%m-%d'):
        if value:
            try:
                if isinstance(value, datetime):
                    return value
                elif isinstance(value, int) and value > 0:
                    return datetime.utcfromtimestamp(value)
                elif isinstance(value, str):
                    return datetime.strptime(value, format)
            except:
                return None
        return None

    @staticmethod
    def decodetext(value):
        """Converts enriched text to plain text"""
        value = value.replace("<br />", "\r")
        value = value.replace("\n\n", "\r\n\r\n")
        value = value.replace("\r\n", "[CR]")  # KODI: Convert line breaks to cr codes
        value = AnimeItem._re_tags.sub("", value)  # Remove html tags
        value = AnimeItem._html_parser.unescape(value)  # Convert html entities
        value = AnimeItem._re_bbcode.sub("", value)  # Remove BB code
        return value

    def touched(self):
        try:
            self._updated = datetime.now()
        except TypeError:
            pass
        except ValueError:
            pass

    @staticmethod
    def createFromItem(db, obj):
        item = AnimeItem(db)

        item._id = obj.get("id")
        item._art = obj.get("image")
        item.title = obj.get("title")
        item.type = obj.get("type", TV)
        item.state = obj.get("state", NOTSTARTED)
        item.synonyms = obj.get("synonyms")
        item.usersynonyms = obj.get("synonyms_user")
        item.episodes = obj.get("episodes", 0)
        item.datestart = obj.get("series_start")
        item.dateend = obj.get("series_end")
        item.datenextair = obj.get("series_nextair")
        item.nextairepisode = obj.get("series_nextair_epi")

        item.status = obj.get("status", PLANTOWATCH)
        item.updated = obj.get("updated")
        item.watched = obj.get("watched")
        item.watched_server = obj.get("watched_server")

        # these are fetched via a separate call, so they will never be available during a list parse
        item.synopsis = obj.get("desc")
        item.score = obj.get("score")

        # load in previously cached norms
        item._title_normalized = obj.get("cache_title_norm", "")

        cached_value = obj.get("cache_synonyms_norm")
        if isinstance(cached_value, list):
            item._synonyms_normalized = cached_value

        cached_value = obj.get("cache_user_synonyms_norm")
        if isinstance(cached_value, list):
            item._usersyn_normalized = cached_value

        return item

    def update(self, obj):
        # An update only cares about a few key things
        item.state = obj.get("state", NOTSTARTED)
        item.episodes = obj.get("episodes", 0)
        item.datestart = obj.get("series_start")
        item.dateend = obj.get("series_end")
        item.datenextair = obj.get("series_nextair")
        item.nextairepisode = obj.get("series_nextair_epi")
        item.status = obj.get("status", PLANTOWATCH)
        item.updated = obj.get("updated")
        item.watched = obj.get("watched")

    def save(self):
        anime = {
            "id": self.id,
            "image": self.art,
            "title": self.title,
            "cache_title_norm": self._title_normalized,
            "type": self.type,
            "state": self.state,
            "episodes": self.episodes,
            "series_start": self.datestart,
            "series_end": self.dateend,
            "status": self.status,
            "updated": self.updated,
            "watched": self.watched,
            "watched_server": self.watched_server,
            "desc": self.synopsis,
            "score": self.score
        }

        if self.datenextair:
            anime["series_nextair"] = self.datenextair
        if self.nextairepisode:
            anime["series_nextair_epi"] = self.nextairepisode

        if self._synonyms:
            anime["synonyms"] = self._synonyms
        if self._synonyms_normalized:
            anime["cache_synonyms_norm"] = self._synonyms_normalized

        if self._usersyn:
            anime["synonyms_user"] = self._usersyn
        if self._usersyn_normalized:
            anime["cache_user_synonyms_norm"] = self._usersyn_normalized

        return anime

    def add_episode(self, episode, filename):
        try:
            value = int(episode)
            if value < 1:
                return False
            if self.episodes > 0 and value > self.episodes:
                return False
            self._available[value] = filename
            return True
        except ValueError:
            return False

    def remove_episode(self, episode):
        try:
            value = int(episode)
            if value in self._available:
                del self._available[value]
                return True
            return False
        except ValueError:
            return False

    def resetprogress(self):
        self._watched = 0
        self._watched_server = 0

    def is_match(self, value):
        """Returns True if the normalized string matches this database item"""
        # Normalize title on demand
        if not self._title_normalized:
            self._title_normalized = normalize_title(self._title)
        if value == self._title_normalized:
            return True

        # Normalize synonyms on demand
        if self._synonyms:
            # Service-Provided synonyms
            if self._synonyms and not self._synonyms_normalized:
                for syn in self._synonyms:
                    norm = normalize_title(syn)
                    if norm:  # If the unicode normalization translates to nothing, then dont write it
                        self._synonyms_normalized.append(normalize_title(syn))

            if value in self._synonyms_normalized:
                return True

            # User customized synonyms
            if self._usersyn and not self._usersyn_normalized:
                for syn in self._usersyn:
                    norm = normalize_title(syn)
                    if norm:  # If the unicode normalization translates to nothing, then dont write it
                        self._usersyn_normalized.append(normalize_title(syn))

            if value in self._usersyn_normalized:
                return True
        return False

    def is_outofsync(self):
        """Returns True if the local progress of this item needs to be synced with MAL"""
        return self.watched != self.watched_server

    def is_airing(self):
        if self.datestart is None:
            return False
        if self.dateend is None:
            return True
        now = datetime.date.today()
        if now >= self.datestart.date and now <= self.dateend.date:
            return True
        return False

    def synced(self):
        """Flags the item as having been successfully synced to the server"""
        self.watched_server = self.watched


class AnimeDatabase(object):
    storeFile = "db.json"

    def __init__(self, path, service, library):
        #internal
        self._ant = Anitomy()
        self._dbstore = os.path.join(path, AnimeDatabase.storeFile)
        self._db = {}
        self._library = unicode(library) #py2: force unicode, so that os.walk will properly handle unicode filenames
        self._updatelist = deque()
        self._service = service

        #init
        self.load()
    def __iter__(self):
        for id in self._db:
            yield id
    def __getitem__(self, item):
        return self._db[item]
    def __len__(self):
        return len(self._db)
    def __contains__(self, item):
        return item in self._db

    @property
    def service(self):
        return self._service

    @service.setter
    def service(self, value):
        """Switch service handler. Empties the database and removes all queued updates"""
        if value != self._service and isinstance(value, AnimeService):
            self._db.clear()
            self._updatelist.clear()
            self._service = value

    def load(self):
        """Loads the database from disk"""
        try:
            #A valid service handler must be bound to the database before any load will be accepted
            if not isinstance(self.service, AnimeService):
                return
            if not os.path.exists(self._dbstore):
                return
            fp = open(self._dbstore, "r")
            data = json.load(fp)
            fp.close()

            #Ensure the loaded db matches the active service. If not, then the load will be aborted, resulting in an empty db
            serviceid = data.get("service")
            if serviceid != self.service.id:
                return

            self._db.clear()
            for anime in data.get("items"):
                key = anime.get("id")
                if key in self._db:
                    self._db[key].update(anime)
                else:
                    dbitem = AnimeItem.createFromItem(self, anime)
                    self.add_anime(dbitem)

                    # If the item requires additional data, then add it to the update list for later processing
                    if self.service.requiresAsyncFetch(dbitem):
                        if dbitem.status == WATCHING or dbitem.status == PLANTOWATCH:
                            # Give priority to shows that are most likely to be viewed first
                            self._updatelist.append(dbitem)
                        else:
                            self._updatelist.appendleft(dbitem)

        except ValueError:
            #In py2, deserializing errors raise ValueError
            pass
        except IOError:
            pass

    def fetch(self):
        """Syncs the database with the active service"""
        if not isinstance(self.service, AnimeService):
            return False
        return self.service.fetch(self)

    def save(self):
        """Saves the database to disk"""

        def json_default(obj):
            if isinstance(obj, datetime):
                return getTimeStamp(obj)
            raise TypeError ("Type %s not serializable" % type(obj))

        try:
            items = []
            for key, item in self._db.iteritems():
                obj = item.save()
                items.append(obj)

            fp = open(self._dbstore, "w")
            json.dump({
                "service": self.service.id,
                "items"  : items
            }, fp, default=json_default)
            fp.close()
        except IOError:
            pass

    def find(self, name):
        """Finds a database item based on the series title"""
        title = normalize_title(name)
        for key, item in self._db.iteritems():
            if item.is_match(title):
                return item
        return None

    def resolve(self, filename):
        """Finds a database item, and its episode number, based on the file name"""
        # Extract the anime title from the file
        if self._ant.parse(filename):
            # only care about files that have a declared episode number or range
            if kElementEpisodeNumber in self._ant.elements:
                # normalize the title, then attempt to find it in the database
                title = self._ant.elements[kElementAnimeTitle]
                episodes = self._ant.elements[kElementEpisodeNumber]

                # Anitomy returns episodes as a string, so they must be converted
                # If the file is a single episode the value will be a string, otherwise a list of two strings
                if isinstance(episodes, list):
                    try:
                        start = int(episodes[0])
                    except ValueError:
                        start = 0

                    try:
                        end = int(episodes[1])
                    except ValueError:
                        end = start
                else:
                    try:
                        start = int(episodes)
                        end = start
                    except ValueError:
                        start = 0
                        end = 0

                # If the start episode is invalid, then discard this file
                if start > 0:
                    return self.find(title), title, start, end
        return None, "", 0, 0

    def add_anime(self, anime):
        """Adds an anime item to the database. If an item with the same key exists, it will be overwritten"""
        if not isinstance(anime, AnimeItem):
            return False
        if not anime.id:
            return False
        self._db[anime.id] = anime

    def map_episode(self, anime, episode):
        # If there is a mapped episode redirection, then calculate the new episode and return the new entry
        if anime.episodes > 0 and episode > anime.episodes and self._service and self._service.relationship_index >= 0:
            did, episode = Relationships.find(self._service.relationship_index, anime.id, episode)
            if did in self._db:
                return self._db[did], episode
        return anime, episode  # No mapping or mapped anime not in db. Just echo back the original values

    def add_episode(self, filepath):
        """Determines the series and episode from the file name, and marks it as available"""
        item, title, start, end = self.resolve(os.path.basename(filepath))
        if item is not None:
            # Mark episode(s) as available
            abspath = os.path.abspath(filepath)
            for episode in range(start, end+1):
                mappeditem, mappedepi = self.map_episode(item, episode)
                mappeditem.add_episode(mappedepi, abspath)
            return True
        return False

    def remove_episode(self, filepath):
        """Determines the series and episode from the file name, and marks it as unavailable"""
        item, title, start, end = self.resolve(os.path.basename(filepath))
        if item is not None:
            # Remove episode(s) from availability
            for episode in range(start, end+1):
                mappeditem, mappedepi = self.map_episode(item, episode)
                mappeditem.remove_episode(mappedepi)
            return True
        return False

    def find_episodes(self):
        """Crawls the library folder to look for available episodes"""
        foundany = False
        if os.path.isdir(self._library):
            # Grab all the files
            for (dirpath, dirnames, filenames) in os.walk(self._library):
                for filename in filenames:
                    item, title, start, end = self.resolve(filename)
                    if item is not None:
                        # Mark episode(s) as available
                        abspath = os.path.abspath(os.path.join(dirpath, filename))
                        for episode in range(start, end + 1):
                            mappeditem, mappedepi = self.map_episode(item, episode)
                            if mappeditem.add_episode(mappedepi, abspath):
                                foundany = True
        return foundany

    @property
    def library(self):
        return self._library

    @library.setter
    def library(self, value):
        # Force unicode for the library path, so that os walk returns unicode strings
        value = unicode(value)
        if value != self._library:
            self._library = value

    @property
    def user(self):
        return self._user

    @user.setter
    def user(self, value):
        if value != self._user:
            self._db.clear()
            self._user = value

    @property
    def password(self):
        return self._pass

    @password.setter
    def password(self, value):
        self._pass = value

    @property
    def ready(self):
        """Returns a list of database items that are ready to play the next episode"""
        for key in self._db:
            dbitem = self._db[key]
            # only return series that are in watch/plan to watch, and have an available episode to watch
            if (dbitem.status == WATCHING or dbitem.status == PLANTOWATCH) and dbitem.nextfile is not None:
                yield dbitem

    @property
    def pushlist(self):
        """Returns a list of database items that need to be synced with MAL."""
        for key in self._db:
            dbitem = self._db[key]
            if dbitem.is_outofsync():
                yield dbitem

    @property
    def updatecount(self):
        return len(self._updatelist)

    def updatepeek(self):
        return self._updatelist[-1]

    def updatenext(self):
        # Bail out if the service is offline or not setup
        if not self.service.cansync:
            return

        anime = None
        try:
            anime = self._updatelist.pop()

            # Perform the sync operation for the item
            self.service.fetchAsyncInfo(self, anime)

            # Double check the fetch was successful
            if self.service.requiresAsyncFetch(anime):
                return False
            return True

        except urllib2.HTTPError, e:
            # put it back on the pile, and then pass the exception to the caller
            if anime is not None:
                self._updatelist.append(anime)
            raise e

        except IndexError:
            return False

    def statuslist(self, status):
        """Returns a list of database items that are ready to play the next episode"""
        for key in self._db:
            dbitem = self._db[key]
            # only return series that are in watch/plan to watch, and have an available episode to watch
            if dbitem.status == status:
                yield dbitem
