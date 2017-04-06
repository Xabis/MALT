# Copyright (c) 2017, Carl Lewis
#
# This source code is released under the MIT license
# https://opensource.org/licenses/MIT

import os, urllib, urllib2
from datetime import datetime, time
import xml.etree.cElementTree as ET
from anitomy import *
from unicodedata import normalize
from .relations import Relationships
from collections import deque
import base64
from HTMLParser import HTMLParser

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

# =====================================================================================================================
# Database
# =====================================================================================================================
# MAL SAMPLE:
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
class AnimeItem(object):
    _re_bbcode = re.compile("\[\/?(b|i|u|(size(=[0-9]+)?)|(url(=[^\]]*)?))\]")
    _re_tags = re.compile("<[^<]+?>")
    _html_parser = HTMLParser()

    # =================================================================================================================
    # Constructor
    # =================================================================================================================
    def __init__(self, el=None, server=False):
        self._id = 0
        self._title = ""
        self._title_normalized = ""
        self._type = 0
        self._state = 0
        self._art = ""
        self._episodes = 0
        self._watched = 0
        self._watched_server = 0
        self._aired = None
        self._available = {}
        self._updated = None
        self._datestart = None
        self._dateend = None
        self._synonyms = []
        self._synonyms_normalized = []
        self._usersyn = []
        self._usersyn_normalized = []
        self._status = 0
        self._synopsis = ""
        self._score = 0.0

        if el is not None:
            self.parse(el, server)

    # =================================================================================================================
    # Properties
    # =================================================================================================================
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

    @property
    def aired(self):
        """Returns an ESTIMATED number of episodes that have been currently aired"""
        if self._aired is None:
            # Check the dates instead of the show status, as dates are usually provided in advance
            today = datetime.combine(datetime.today(), time())  # start of day
            if self.datestart is None or today < self.datestart:
                self._aired = 0
            elif self.dateend is not None and today >= self.dateend:
                self._aired = self.episodes
            elif self.type == TV:
                # Unfortunately MAL does not provide the number of aired episodes, so an estimation must be made
                #   estimations are useful for one to two cour series, but get wildly off track
                #   when the series is long running (ex: One Piece)
                diff = (today - self.datestart).days - 1
                if diff > -1:
                    weeks = diff / 7
                    if self.episodes == 0 or weeks < self.episodes:
                        self._aired = weeks + 1
                    else:
                        self._aired = self.episodes
            else:
                self._aired = 0
        return self._aired

    @property
    def updated(self):
        return self._updated

    @updated.setter
    def updated(self, value):
        try:
            self._updated = datetime.fromtimestamp(int(value))
        except:
            pass

    @property
    def datestart(self):
        return self._datestart

    @datestart.setter
    def datestart(self, value):
        try:
            self._datestart = datetime.strptime(value, '%Y-%m-%d')
        except:
            pass

    @property
    def dateend(self):
        return self._dateend

    @dateend.setter
    def dateend(self, value):
        try:
            self._dateend = datetime.strptime(value, '%Y-%m-%d')
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
    def usersynonyms(self):
        if self._usersyn:
            return "; ".join(self._usersyn)
        return ""

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
    def _safeget(node, tag):
        child = node.find(tag)
        if child is None:
            return ""
        return child.text

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

    def parse(self, node, server=False):
        self._id = AnimeItem._safeget(node, "series_animedb_id")
        self._art = AnimeItem._safeget(node, "series_image")
        self.title = AnimeItem._safeget(node, "series_title")
        self.type = AnimeItem._safeget(node, "series_type")
        self.state = AnimeItem._safeget(node, "series_status")
        self.set_synonyms(AnimeItem._safeget(node, "series_synonyms"))
        self.set_user_synonyms(AnimeItem._safeget(node, "series_user_synonyms"))
        self.episodes = AnimeItem._safeget(node, "series_episodes")
        self.datestart = AnimeItem._safeget(node, "series_start")
        self.dateend = AnimeItem._safeget(node, "series_end")

        self.status = AnimeItem._safeget(node, "my_status")
        self.updated = AnimeItem._safeget(node, "my_last_updated")
        self.watched = AnimeItem._safeget(node, "my_watched_episodes")

        if server:
            # if parsing from the server, then set the server watch prop as well. no need to look at cached values
            self._watched_server = self.watched
        else:
            # these are fetched via a separate call, so they will never be available during a list parse
            self.synopsis = AnimeItem._safeget(node, "synopsis")
            self.score = AnimeItem._safeget(node, "score")

            # load the server watched progress from the cache
            cached_value = node.find("cache_server_progress")
            if cached_value is not None:
                try:
                    self._watched_server = int(cached_value.text)
                except ValueError:
                    self._watched_server = self.watched

            # load in previously cached norms
            cached_value = node.find("cache_title_norm")
            if cached_value is not None:
                self._title_normalized = cached_value.text

            cached_value = node.find("cache_synonyms_norm")
            if cached_value is not None and cached_value.text is not None:
                arr = cached_value.text.split("; ")
                for syn in arr:
                    if syn != "":
                        self._synonyms_normalized.append(syn)

            cached_value = node.find("cache_user_synonyms_norm")
            if cached_value is not None and cached_value.text is not None:
                arr = cached_value.text.split("; ")
                for syn in arr:
                    if syn != "":
                        self._usersyn_normalized.append(syn)

    def update(self, node):
        # An update only cares about a few key things
        self.state = AnimeItem._safeget(node, "series_status")
        self.episodes = AnimeItem._safeget(node, "series_episodes")
        self.datestart = AnimeItem._safeget(node, "series_start")
        self.dateend = AnimeItem._safeget(node, "series_end")
        self.status = AnimeItem._safeget(node, "my_status")
        self.updated = AnimeItem._safeget(node, "my_last_updated")

        # An update always comes from the server.
        watched = AnimeItem._safeget(node, "my_watched_episodes")
        try:
            watched = int(watched)
            self._watched_server = watched

            # If the server is not as progressed as the local db, then do not set it.
            if watched > self.watched:
                self.watched = watched
        except ValueError:
            pass

    def save(self):
        animenode = ET.Element("anime")

        # Series info
        ET.SubElement(animenode, "series_animedb_id").text = self._id
        ET.SubElement(animenode, "series_image").text = self._art
        ET.SubElement(animenode, "series_title").text = self._title
        ET.SubElement(animenode, "series_type").text = str(self.type)
        ET.SubElement(animenode, "series_status").text = str(self.state)

        if len(self._synonyms) > 0:
            ET.SubElement(animenode, "series_synonyms").text = "; ".join(self._synonyms)
        if len(self._usersyn) > 0:
            ET.SubElement(animenode, "series_user_synonyms").text = "; ".join(self._usersyn)
        ET.SubElement(animenode, "series_episodes").text = str(self._episodes)
        if self._datestart:
            ET.SubElement(animenode, "series_start").text = self._datestart.strftime('%Y-%m-%d')
        if self._dateend:
            ET.SubElement(animenode, "series_end").text = self._dateend.strftime('%Y-%m-%d')

        # User data
        ET.SubElement(animenode, "my_status").text = str(self._status)
        ET.SubElement(animenode, "my_watched_episodes").text = str(self._watched)
        if self._updated:
            diff = self._updated - datetime(1970, 1, 1)
            ET.SubElement(animenode, "my_last_updated").text = str(int(diff.total_seconds()))

        # Async fetched items
        if self.synopsis and not self.synopsis.startswith("No synopsis has been added for this series yet"):
            # Do not save the broilerplate synopsis to the DB. This will allow it to be requeued when relaunched
            ET.SubElement(animenode, "synopsis").text = self.synopsis
        if self.score:
            ET.SubElement(animenode, "score").text = str(self.score)

        # Cache on-demand calculated items
        if self._watched_server > 0 and self._watched_server != self._watched:
            ET.SubElement(animenode, "cache_server_progress").text = str(self._watched_server)
        if self._title_normalized:
            ET.SubElement(animenode, "cache_title_norm").text = self._title_normalized
        if self._synonyms_normalized:
            ET.SubElement(animenode, "cache_synonyms_norm").text = "; ".join(self._synonyms_normalized)
        if self._usersyn_normalized:
            ET.SubElement(animenode, "cache_user_synonyms_norm").text = "; ".join(self._usersyn_normalized)

        return animenode

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

    def set_synonyms(self, value):
        if not value:
            return
        changed = False
        arr = value.split("; ")
        for syn in arr:
            if syn != "" and syn != self._title and syn not in self._synonyms:
                self._synonyms.append(syn)
                changed = True
        if changed:
            self._synonyms_normalized = []

    def set_user_synonyms(self, value):
        self._usersyn = []
        self._usersyn_normalized = []
        arr = value.split(";")
        for syn in arr:
            syn = syn.strip()
            if syn != "" and syn != self._title and syn not in self._synonyms and syn not in self._usersyn:
                self._usersyn.append(syn)

    def is_match(self, value):
        """Returns True if the normalized string matches this database item"""
        # Normalize title on demand
        if not self._title_normalized:
            self._title_normalized = normalize_title(self._title)
        if value == self._title_normalized:
            return True

        # Normalize synonyms on demand
        if self._synonyms:
            # MAL-Provided synonyms
            if not self._synonyms_normalized:
                for syn in self._synonyms:
                    norm = normalize_title(syn)
                    if norm:  # If the unicode normalization translates to nothing, then dont write it
                        self._synonyms_normalized.append(normalize_title(syn))
            for syn in self._synonyms_normalized:
                if value == syn:
                    return True

            # User customized synonyms
            if not self._usersyn_normalized:
                for syn in self._usersyn:
                    norm = normalize_title(syn)
                    if norm:  # If the unicode normalization translates to nothing, then dont write it
                        self._usersyn_normalized.append(normalize_title(syn))
            for syn in self._usersyn_normalized:
                if value == syn:
                    return True
        return False

    def is_outofsync(self):
        """Returns True if the local progress of this item needs to be synced with MAL"""
        return self.watched > self.watched_server

    def is_airing(self):
        if self.dateend is None:
            return True
        if datetime.now() < self.dateend:
            return True
        return False

    def synced(self):
        """Flags the item as having been successfully synced to the server"""
        self._watched_server = self.watched


class AnimeDatabase(object):
    _statuspriority = {1: 0, 6: 1, 3: 2, 2: 3, 4: 4}

    def __init__(self, dbstore, user, password, library):
        self._ant = Anitomy()
        self._dbstore = dbstore
        self._user = user
        self._pass = password
        self._db = {}
        self._library = unicode(library) #py2: force unicode, so that os.walk will properly handle unicode filenames
        self._updatelist = deque()
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

    def load(self):
        """Loads the database from disk"""
        try:
            xml = ET.parse(self._dbstore)
            root = xml.getroot()
            nodes = root.findall("anime")
            for node in nodes:
                self.parse(node)
        except ET.ParseError:
            pass
        except IOError:
            pass

    def sync(self):
        """Syncs the database with MAL"""
        if not self._user:
            return False

        # #TODO: remove --- load the snapshot file instead of doing the request
        # filepath = os.path.join(os.path.dirname(__file__), "snapshot.xml")
        # xml = ET.parse(filepath)
        # root = xml.getroot()

        # Fetch the latest list data from MAL
        url = "http://myanimelist.net/malappinfo.php?u={0}&status=all".format(self._user)
        response = urllib2.urlopen(url).read()
        root = ET.fromstring(response)

        # #TODO: remove --- save the xml to a snapshot file
        # snapshot = open(filepath, "w")
        # snapshot.write(response)
        # snapshot.close()

        # load the nodes into the database
        nodes = root.findall("anime")
        for node in nodes:
            self.parse(node, True)

        return True

    def parse(self, node, server=False):
        """Parses an anime xml node, either from disk or MAL"""
        child = node.find("series_animedb_id")
        if child is None:
            return
        key = child.text

        # If item already exists, then simply update it, otherwise create and add it
        if key in self._db:
            dbitem = self._db[key]
            dbitem.update(node)
        else:
            dbitem = AnimeItem(node, server)
            self._db[dbitem.id] = dbitem

            # if synopsis is not available, then add it to the update list for later processing
            if not dbitem.synopsis:
                if dbitem.status == WATCHING or dbitem.status == PLANTOWATCH:
                    # Give priority to shows that are most likely to be viewed first
                    self._updatelist.append(dbitem)
                else:
                    self._updatelist.appendleft(dbitem)

    def save(self):
        """Saves the database to disk"""
        try:
            root = ET.Element("database")
            for key, item in self._db.iteritems():
                node = item.save()
                root.append(node)

            tree = ET.ElementTree(root)
            tree.write(self._dbstore, "UTF-8")
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

    def map(self, anime, episode):
        # If there is a mapped episode redirection, then calculate the new episode and return the new entry
        if anime.episodes > 0 and episode > anime.episodes:
            did, episode = Relationships.find(anime.id, episode)
            if did in self._db:
                return self._db[did], episode
        return anime, episode  # No mapping or mapped anime not in db. Just echo back the original values

    def add(self, filepath):
        """Determines the series and episode from the file name, and marks it as available"""
        item, title, start, end = self.resolve(os.path.basename(filepath))
        if item is not None:
            # Mark episode(s) as available
            abspath = os.path.abspath(filepath)
            for episode in range(start, end+1):
                mappeditem, mappedepi = self.map(item, episode)
                mappeditem.add_episode(mappedepi, abspath)
            return True
        return False

    def remove(self, filepath):
        """Determines the series and episode from the file name, and marks it as unavailable"""
        item, title, start, end = self.resolve(os.path.basename(filepath))
        if item is not None:
            # Remove episode(s) from availability
            for episode in range(start, end+1):
                mappeditem, mappedepi = self.map(item, episode)
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
                            mappeditem, mappedepi = self.map(item, episode)
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
        # Unfortunately, MAL requires the password for searching, so if one is not provided, then do nothing
        if not self.user or not self.password:
            return

        anime = None
        try:
            anime = self._updatelist.pop()

            # If this show got its synopsis from an earlier search, then skip
            if anime.synopsis:
                return True

            # Make the request the MAL. This function is not throttled, so care must be taken
            encodedauth = base64.encodestring('%s:%s' % (self.user, self.password)).replace('\n', '')
            headers = {'Content-Type': 'application/x-www-form-urlencoded',
                       'Authorization': 'Basic %s' % encodedauth}
            url = "https://myanimelist.net/api/anime/search.xml?{0}".format(urllib.urlencode({'q': anime.title.encode('utf8')}))

            req = urllib2.Request(url, headers=headers)
            response = urllib2.urlopen(req)
            output = response.read()

            # # Debug helper
            # filepath = os.path.join(os.path.dirname(__file__), "search.xml")
            # fs = open(filepath, "r")
            # output = fs.read()

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
                    if key in self._db:
                        dbitem = self._db[key]
                        dbitem.synopsis = AnimeItem._safeget(node, "synopsis")
                        dbitem.score = AnimeItem._safeget(node, "score")

                # Return whether the search yielded info for the entry that was passed in
                if anime.synopsis:
                    return True
            return False

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
