# Copyright (c) 2017, Carl Lewis
#
# This source code is released under the MIT license
# https://opensource.org/licenses/MIT

import time
import base64
import urllib
import urllib2
import xbmc, xbmcaddon, xbmcgui
import sys, os
import datetime
from threading import Thread, Event, Lock
from resources.lib.database import AnimeDatabase
from resources.lib.relations import Relationships
from resources.lib.util import int2
from resources.lib.service.base import AnimeService
from resources.lib.service.mal import MALService
from resources.lib.service.anilist import ALService

try:
    import cPickle as pickle
except ImportError:
    import pickle


__addon__     = xbmcaddon.Addon(id="service.maltracker")
__addonid__   = __addon__.getAddonInfo('id')
__addonname__ = __addon__.getAddonInfo('name')
__profile__   = xbmc.translatePath(__addon__.getAddonInfo("profile"))
__path__      = xbmc.translatePath(__addon__.getAddonInfo("path"))
__relfile__   = os.path.join(__profile__, 'rel.txt')
__picklejar__ = os.path.join(__profile__, 'db.bin')
__ipc__       = xbmcgui.Window(10000)  # command ipc marshaller
__services__  = {"anilist.co": ALService, "myanimelist.com": MALService}
__svc_def__   = "anilist.co"

def log(text):
    # Convert text to plain ascii, otherwise kodi will raise an exception
    xbmc.log(u"[{0}] {1}".format(__addonname__, text.encode('ascii', 'replace')), level=xbmc.LOGDEBUG)

def getstring(key):
    return __addon__.getLocalizedString(key)

def notify(text, level=0):
    if level == 2:
        flag = xbmcgui.NOTIFICATION_ERROR
    elif level == 1:
        flag = xbmcgui.NOTIFICATION_WARNING
    else:
        flag = xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification(__addonname__, text, flag)


# If a command is coming in from a run script, then put it on the ipc and terminate this thread
if len(sys.argv) > 1:
    param = sys.argv[1]
    __ipc__.setProperty("maltcommand", param)

    if len(sys.argv) > 2:
        params = ";".join(sys.argv[2:])
        __ipc__.setProperty("maltparam", params)
    sys.exit()

# If not processing a command, then this is the main service being started.
# For whatever reason, Kodi will start the service twice after a fresh install, which cannot be allowed
if __ipc__.getProperty("maltinit"):
    log("KILLING DUPLICATE SERVICE INSTANCE")
    sys.exit()
__ipc__.setProperty("maltinit", "false")  # Claim this instance as main one. kill the rest.

# Ensure the profile folder exists, for the db and jar
if not os.path.exists(__profile__):
    os.makedirs(__profile__)

# Add the lib path for the 3rd party libs. This is needed due to internal relative imports
lib = os.path.join(__path__, 'resources', 'lib')
sys.path.append(lib)

# Import the folder monitoring lib.
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

class Main(xbmc.Player, PatternMatchingEventHandler):  # Subclasses for the playback and file notifications
    _svc_cache = {}

    """Main Service"""
    def __init__(self):
        __ipc__.setProperty("maltready", "false")
        super(Main, self).__init__()

        # Build list of watch extensions from the supported media list
        media = xbmc.getSupportedMedia("video")
        media = media.replace(".", "*.")
        medialist = media.split("|")
        PatternMatchingEventHandler.__init__(self, patterns=medialist, ignore_directories=True)

        # Property Initialization
        self._monitor = xbmc.Monitor()
        self._lastanime = None
        self._lastepisode = 0
        self._playstart = None
        self._observer = None
        self._updatethread = None
        self._shutdown = Event()
        self._iolock = Lock()
        self._allow_update = __addon__.getSetting("maltAllowUpdate") == "true"

        # If this is the first time this addon has ever been run, then popup a brief welcome message and
        #   a convenience option to open the setting panel immediately.
        if not __addon__.getSetting("maltFirstRun"):
            __addon__.setSetting("maltFirstRun", "true")
            if xbmcgui.Dialog().yesno(getstring(316), getstring(317)):
                __addon__.openSettings()

        # Grab settings
        libpath = __addon__.getSetting("maltLibraryPath")
        sync = False

        # Emit a notification error, if the library path is no longer valid
        if libpath and not os.path.isdir(libpath):
            notify(getstring(207), 2)  # folder is invalid

        # Build the relative episode relationship database
        try:
            rel_needsupdate = True
            if Relationships.load(__relfile__):
                rel_last = __addon__.getSetting("maltRelLastUpdate")
                if rel_last:
                    try:
                        # The relationships file doesnt update very often, so only download a fresh copy every couple days.
                        # No need to spam.
                        rel_date = datetime.datetime.strptime(rel_last, "%Y-%m-%d")
                        days = (datetime.datetime.now() - rel_date).days
                        if days < 3:
                            rel_needsupdate = False
                    except:
                        pass

            # If updating, then grab the latest copy from github, then mark the date
            if rel_needsupdate and Relationships.update(__relfile__):
                __addon__.setSetting("maltRelLastUpdate", datetime.datetime.now().strftime("%Y-%m-%d"))
        except:
            # something went wrong while parsing the relationship data. notify the user that season pairing will be off.
            notify(getstring(223), 2)

        # Create the service handler
        self._service = self.getService()
        if self._service:
            log("Initializing with service: {0}".format(self._service.id))

        # Create the video database
        self._db = AnimeDatabase(__profile__, self._service, libpath)
        if self._service.cansync:
            if __addon__.getSetting("maltAutoSync") == "true":
                sync = True
            elif not self._db and xbmcgui.Dialog().yesno(__addonname__, getstring(202)):  # no entries. sync now?
                sync = True

        # Do a sync if needed, otherwise do the initial episode search and then write out the jar
        if sync:
            self.sync()
        else:
            # Since the main sync is disabled, check the push queue separately
            self.push_queue()

            # Search for available episodes and then write the database to the jar.
            self._db.find_episodes()
            self.updatejar()

        # Start the main service loop
        __ipc__.setProperty("maltinit", "true")  # We are ready to go
        self.daemon()

    def getService(self):
        id = __addon__.getSetting("maltService") or __svc_def__
        if id in Main._svc_cache:
            return Main._svc_cache[id]

        try:
            cls = __services__[id]
        except:
            #Bad service id, so switch to the default and notify the user. Existing db will get wrecked.
            notify(getstring(224), 1)
            id = __svc_def__
            __addon__.setSetting("maltService", id)

            if id in Main._svc_cache:
                return Main._svc_cache[id]
            cls = __services__[id]

        svc = cls(__addon__)
        if isinstance(svc, AnimeService):
            Main._svc_cache[id] = svc
            return svc
        return None

    def onPlayBackStarted(self):
        """KODI PLAYER: playback was started"""
        self._lastanime = None
        self._lastepisode = 0
        self._playstart = datetime.datetime.now()

        # If the user is not playing a video, then cancel
        if not self.isPlayingVideo():
            return
        filepath = self.getPlayingFile()

        # If the user is allowing any file to trip an update, then skip these checks
        if __addon__.getSetting("maltUpdateAny") != "true":
            # No library, so just cancel out
            if not self._db.library:
                return

            # Check to make sure the file being played is inside the library folder
            try:
                if filepath.index(self._db.library) != 0:
                    return
            except ValueError:
                return

        # Lookup the anime database entry
        basefile = os.path.basename(filepath)
        anime, title, start, end = self._db.resolve(basefile)
        if anime is None:
            if __addon__.getSetting("maltShowUknown") == "true":
                # If the title could not be found in the database, then emit a warning
                notify(getstring(213).format(title), 1)
        else:
            # If the file represents multiple episodes (such as a special), then advance to the very end
            self._lastanime, self._lastepisode = self._db.map_episode(anime, end)  # need to map, as resolve doesnt do it

            # Show what's playing
            if __addon__.getSetting("maltShowPlaying") == "true":
                episodes = self._lastanime.episodes
                if episodes == 0:
                    episodes = "?"
                notify(getstring(221).format(self._lastanime.title, self._lastepisode, episodes))

    def onPlayBackStopped(self):
        """KODI PLAYER: playback was manually stopped by the user"""
        # Non-qualifying media was playing, so skip
        if self._lastanime is None:
            return

        # Since the user manually stopped, check to see if the minimum playback time has elapsed before updating
        timelapse = (datetime.datetime.now() - self._playstart).seconds
        minseconds = int2(__addon__.getSetting("maltMinSeconds"))
        if timelapse > minseconds:
            self.onPlayBackEnded()

    def onPlayBackEnded(self):
        """KODI PLAYER: playback reached the end"""
        # Non-qualifying media was playing, so skip
        if self._lastanime is None:
            return

        # Only auto-increment, if the episode watched was the next one in the list
        #   This prevents skipping ahead or going back
        if self._lastepisode == (self._lastanime.watched + 1):
            self.updatewatched(self._lastanime, self._lastepisode, True)
            xbmc.executebuiltin('Container.Refresh()')

    def on_created(self, event):
        """WATCHDOG: A file was created"""
        if self._db.add_episode(event.src_path):
            with self._iolock:
                __ipc__.setProperty("maltready", "false")
                self._db.save()
                self.updatejar()
            xbmc.executebuiltin('Container.Refresh()')

    def on_deleted(self, event):
        """WATCHDOG: A file was deleted"""
        if self._db.remove_episode(event.src_path):
            with self._iolock:
                __ipc__.setProperty("maltready", "false")
                self._db.save()
                self.updatejar()
            xbmc.executebuiltin('Container.Refresh()')

    def updatejar(self):
        """Creates a binary representation of the database object, so that the listing component can access it"""
        try:
            fs = open(__picklejar__, "wb")
            pickle.dump(self._db, fs, pickle.HIGHEST_PROTOCOL)
            fs.close()
            __ipc__.setProperty("maltready", "true")
            return True

        except Exception, e:
            log("Exception thrown updating the jar: " + str(e))
            notify(getstring(204), 2)
            return False

    def save(self):
        """Saves the local database to disk"""
        with self._iolock:
            # Inform the components that an update is underway
            __ipc__.setProperty("maltready", "false")

            # Save the database and update the jar
            self._db.save()
            self.updatejar()  # Ready flag is set inside

    def authenticate(self):
        if not isinstance(self._service, AnimeService):
            log("Unable to authenticate: no service handler available")
            notify("Cannot proceed as there is no active service handler.", 2)
            return False

        return self._service.authenticate()

    def sync(self):
        """Syncs the local database with MAL"""

        if not isinstance(self._service, AnimeService):
            log("Critical sync error: no service handler available")
            notify(getstring(203), 2)  # Sync failed
            return False

        with self._iolock:
            __ipc__.setProperty("maltready", "false")
            d = xbmcgui.DialogProgressBG()
            d.create(__addonname__, getstring(209))  # Sync starting
            
            def updater(percent):
                d.update(int(percent * 0.40 * 100))

            try:
                if self._service.fetch(self._db, updater):
                    # If there are local changes that need to be pushed to MAL, then do so now
                    pushlist = list(self._db.pushlist)
                    if pushlist and __addon__.getSetting("maltAllowUpdate") == "true":
                        cnt = 1
                        pushcount = len(pushlist)
                        for anime in pushlist:
                            # Fail out if any of these error. A notification will already be on the screen
                            if not self.push(anime):
                                return False
                            percent = float(cnt) / pushcount
                            d.update(int(percent * 0.80 * 100))
                            cnt = cnt + 1
                    else:
                        d.update(80)

                    # Save changes to the local database
                    self._db.save()
                    d.update(85)
                    self._db.find_episodes()
                    d.update(95)
                    self.updatejar()
                    d.update(100)

                    # All Done
                    d.close()
                    return True

            except Exception, e:
                log("Exception thrown during sync:")
                for msg in e.args:
                    if isinstance(msg, Exception):
                        log(msg.strerror)
                    else:
                        log(str(msg))

            __ipc__.setProperty("maltready", "true")  # normally set when updating the jar
            d.close()
            notify(getstring(203), 2)  # Sync failed
            return False

    def push_queue(self):
        pushlist = list(self._db.pushlist)
        if pushlist and __addon__.getSetting("maltAllowUpdate") == "true":
            d = xbmcgui.DialogProgressBG()
            d.create(__addonname__, getstring(209))  # Sync starting
            cnt = 1
            pushcount = len(pushlist)
            for anime in pushlist:
                if not self.push(anime):
                    return False
                percent = float(cnt) / pushcount
                d.update(int(percent * 100))
                cnt = cnt + 1
            self._db.save() # Save progress updates

    def process_settings(self):
        """Checks to see if there have been changes to a few key service settings, and applies them as needed"""
        monitorlib = __addon__.getSetting("maltMonitorLibrary") == "true"
        if self._observer is not None and not monitorlib:
            # turn off monitoring if the setting is off, but there is an active instance running
            self._observer.stop()
            self._observer.join()
            self._observer = None

        # Check if the selected service handler has changed
        svc = self.getService()
        if self._service != svc and self._db:
            if xbmcgui.Dialog().yesno(__addonname__, getstring(338)):
                # set service and clear db
                self._service = svc
                self._db.service = svc

                # if service has previous auth saved, then ask if the user wants to sync now
                if self._service.cansync:
                    sync = False
                    if __addon__.getSetting("maltAutoSync") == "true":
                        sync = True
                    elif not self._db and xbmcgui.Dialog().yesno(__addonname__, getstring(202)):  # no entries. sync now?
                        sync = True

                    if sync:
                        self.sync()
                else:
                    xbmcgui.Dialog().ok(__addonname__, getstring(339))
            else:
                # revert setting back to the previous service
                idx = __svc_def__
                for key in __services__:
                    if isinstance(self._service, __services__[key]):
                        idx = key
                        break
                __addon__.setSetting("maltService", idx)

        # Check if the library path has been changed since launch
        libpath = __addon__.getSetting("maltLibraryPath")
        if libpath != self._db.library:
            self._db.library = libpath
            with self._iolock:
                if self._db.find_episodes():
                    self.updatejar()

            # If an observer is already running, then stop it and join the thread
            if self._observer is not None:
                self._observer.stop()
                self._observer.join()
                self._observer = None

        # Turn monitoring on if either the monitor setting is enabled, or the library path has changed
        if self._observer is None and monitorlib and libpath:
            # The previous instance is dead now (it cant be restarted), so make a new one
            try:
                self._observer = Observer()
                self._observer.schedule(self, libpath, True)
                self._observer.start()
            except:
                notify(getstring(210), 2)
                self._observer = None

        # Check if the user has been changed since launch
        if self._service.authchanged and self._service.cansync:
            if xbmcgui.Dialog().yesno(__addonname__, getstring(206)):  # Sync now?
                self.sync()
            else:
                self.save()

        # If the allow update setting has been turned on recently, then push any queued items
        # only do this once per enable: the full queue is pushed at startup, and individuals are pushed on demand
        updateenabled = __addon__.getSetting("maltAllowUpdate") == "true"
        if updateenabled and not self._allow_update:
            self.push_queue()
        self._allow_update = updateenabled # this is cheaper than hitting a yield list every tick

        # Start/Stop the update thread based on config or if the user resolved auth issues
        updateenabled = __addon__.getSetting("maltUpdateEnabled") == "true"
        if updateenabled and self._service.cansync and self._updatethread is None:
            self._shutdown.clear()  # Reset the shutdown event in case it was tripped earlier
            self._updatethread = Thread(target=self.updatelist)
            self._updatethread.start()
        elif not updateenabled and self._updatethread is not None:
            # Inform the update thread it needs to shut itself down.
            self._shutdown.set()
            self._updatethread.join()  # This should be quick unless there is a fetch in progress
            self._updatethread = None

    def process_commands(self):
        """Check for any IPC commands from the components"""
        command = __ipc__.getProperty("maltcommand")
        if command:
            params =  __ipc__.getProperty("maltparam").split(";")

            # Clear ipc
            __ipc__.setProperty("maltcommand", "")  # Clear the command
            __ipc__.setProperty("maltparam", "")  # Clear the params

            # If a sync is being requested then sync, save, and update the pickle jar
            if command == "sync":
                if not self._service.cansync:
                    xbmcgui.Dialog().ok(__addonname__, getstring(212))  # unable to sync, bad auth
                    return
                self.sync()

            # Handle authentication requests
            elif command == "authenticate":
                self.authenticate()

            # Force an episode scan
            elif command == "scan":
                d = xbmcgui.DialogProgressBG()
                d.create(__addonname__, getstring(216))  # scanning...
                __ipc__.setProperty("maltready", "false")
                with self._iolock:
                    if self._db.find_episodes():
                        self.updatejar()
                d.close()

            # Force an update to the relationship rules, then do an episode scan
            elif command == "rel":
                d = xbmcgui.DialogProgressBG()
                d.create(__addonname__, getstring(218))  # updating...
                if Relationships.update(__relfile__):
                    __addon__.setSetting("maltRelLastUpdate", datetime.datetime.now().strftime("%Y-%m-%d"))
                    __ipc__.setProperty("maltready", "false")
                    with self._iolock:
                        if self._db.find_episodes():
                            self.updatejar()
                    d.close()
                else:
                    d.close()
                    xbmcgui.Dialog().ok(__addonname__, getstring(220))  # failure

            # Show a series of choices for changing the show status
            elif command == "setstatus":
                try:
                    key = params[0]
                    if key in self._db:
                        anime = self._db[key]

                        # MAL status types have a strict mapping-- ptw isnt even in order
                        choices = [
                            (1, getstring(303)),
                            (2, getstring(304)),
                            (3, getstring(305)),
                            (4, getstring(306)),
                            (6, getstring(307))
                        ]

                        # Build a mapping for the choices, since the list will vary, and kodi is index based
                        choicelist = []
                        choicemap = []
                        for key, value in choices:
                            if key == 2 and anime.is_airing():  # Don't allow setting complete if series is still airing
                                continue
                            if key == anime.status:  # Don't include the same status it's already set to
                                continue
                            choicelist.append(value)
                            choicemap.append(key)

                        # Show the choices to the user
                        choice = xbmcgui.Dialog().select(getstring(315).format(anime.title), choicelist)
                        if choice != -1:
                            status = choicemap[choice]
                            oldstatus = anime.status
                            anime.status = status
                            if status == 2:  # complete
                                # If setting a series to complete, then update the progress to MAX
                                anime.watched = anime.episodes
                            elif status == 1 and oldstatus == 2:  # new is watching; old is complete
                                # If reopening a previously complete series, then reset the watch progress to zero
                                anime.resetprogress()

                            self.save()
                            self.push(anime)
                            xbmc.executebuiltin('Container.Refresh()')

                except ValueError:
                    pass

            # Allow the user to edit custom synonyms
            elif command == "syn":
                try:
                    key = params[0]
                    if key in self._db:
                        anime = self._db[key]
                        previous = "; ".join(anime.usersynonyms)
                        newvalue = xbmcgui.Dialog().input("Enter title synonyms, separate with semi-colon:", previous)

                        if newvalue != "" and newvalue != previous:
                            anime.usersynonyms = newvalue
                            self._db.find_episodes()
                            self.save()
                            xbmc.executebuiltin('Container.Refresh()')

                except ValueError:
                    pass

            # Dialog().input is jankey, where you cannot distinguish from a legitimate empty string and a cancel
            elif command == "syndelete":
                try:
                    key = params[0]
                    if key in self._db:
                        anime = self._db[key]
                        anime.usersynonyms = []
                        self.save()  # pointless to update episodes on a clear. episodes are bonded until a restart

                except ValueError:
                    pass

            # Increment or decrement the watch progress by 1
            elif command == "inc" or command == "dec":
                try:
                    key = params[0]
                    if key in self._db:
                        anime = self._db[key]
                        episode = anime.watched
                        if command == "dec":
                            episode -= 1
                        else:
                            episode += 1

                        # Update the watched progress and then force the list to refresh
                        if self.updatewatched(anime, episode):
                            xbmc.executebuiltin('Container.Refresh()')

                except ValueError:
                    pass

    def updatewatched(self, anime, episode, fromplayback=False):
        """Updates the progress of a show in the local database, and then pushes to MAL, if enabled"""
        # Ensure the episode is valid
        if episode > 0 and (anime.episodes == 0 or episode <= anime.episodes):
            # Set the watched value, flush the database, then push to the server
            anime.watched = episode
            if fromplayback:
                anime.touched()
            self.save()

            # Only push the progress if the user wants to do it immediately, otherwise wait for a sync
            if __addon__.getSetting("maltUpdateProgress") == "true":
                self.push(anime)

            return True
        return False

    def push(self, anime):
        """Push the update to MAL, if enabled"""
        allow_update = __addon__.getSetting("maltAllowUpdate") == "true"
        if allow_update:
            if self._service.cansync:
                try:
                    return self._service.push(anime)

                except urllib2.HTTPError, e:
                    if e.code == 401:
                        notify(getstring(200), 2)  # Bad user or password
                    elif e.code == 400:
                        log("Service update failed: Bad Request")
                        notify(getstring(214), 2)
                    else:
                        log("Service update failed: Error code {0} was received".format(e.code))
                        notify(getstring(215), 2)  # Unknown Error

                except Exception, e:
                    log("An error occurred inside the service handler while pushing:")
                    for msg in e.args:
                        if isinstance(msg, Exception):
                            log(msg.strerror)
                        else:
                            log(str(msg))
                    notify(getstring(215), 2)  # Unknown Error

            elif not self._service._badauth:
                notify(getstring(205), 2)  # Update is on, but credentials are bad
        return False

    def updatelist(self):
        """Fetches synopsis and score information for database items that need it"""
        lastupdate = datetime.datetime.now()
        batchcnt = 0
        batchout = 9  # Flush the database every 10 pulls
        totalcnt = 0
        retrycnt = 0
        maxattempts = 3

        log("service update thread started")

        d = xbmcgui.DialogProgressBG()
        visible = False
        minimum_time = int2(__addon__.getSetting("maltUpdateTime"), 4)
        throttle = minimum_time

        while not self._shutdown.is_set():
            # Do not make an attempt if the user/password is known to be invalid
            if self._service.cansync and self._db.updatecount > 0:
                # Rate throttle these requests, otherwise you will be asking for the ban hammer
                if (datetime.datetime.now() - lastupdate).seconds > throttle:
                    throttle = minimum_time  # Reset throttle in case it was changed during error handling
                    try:
                        # Update the progress display
                        cntleft = self._db.updatecount
                        percent = int(round(totalcnt / (float(cntleft) + totalcnt) * 100))
                        anime = self._db.updatepeek()

                        if not visible:
                            d.create(getstring(331))  # fetching info...
                            visible = True
                        d.update(percent, message=anime.title)

                        # Perform the update on the next item in the queue
                        self._db.updatenext()

                        # Don't spam IO operations. Save the db after a reasonable number of searches are done
                        if batchcnt >= batchout or cntleft == 0:
                            self.save()

                            if cntleft == 0:
                                totalcnt = 0
                                d.close()
                                visible = False
                            batchcnt = 0
                        else:
                            batchcnt += 1

                        retrycnt = 0
                        totalcnt += 1

                    except urllib2.HTTPError, e:
                        # Service Error
                        d.close()
                        visible = False

                        if not self._service.cansync:
                            log("Service authentication rejected")
                            notify(getstring(200), 2)  # Bad user or password
                        else:
                            # Possibly some network problems going on, so lets wait a bit before retrying
                            log("Service HTTP error: {0}".format(e.code))
                            retrycnt += 1
                            throttle = 60

                    except Exception, e:
                        # An internal error occurred. Possibly unrecoverable, but lets try a few times anyway
                        log("Exception thrown while processing the update: {0}".format(e.message))
                        retrycnt += 1
                        d.close()
                        visible = False
                        throttle = 60

                    finally:
                        lastupdate = datetime.datetime.now()

                    # If an unhandled exception was thrown, then allow for up a certain number of attempts
                    if retrycnt >= maxattempts:
                        if batchcnt > 0:
                            self.save()
                        xbmcgui.Dialog().ok(__addonname__, getstring(332))  # Too many failed attempts
                        __addon__.setSetting("maltUpdateEnabled", "false")  # turn the update setting off
                        break  # Kill the thread. User will have to turn the setting back on to get this going again.
                    elif retrycnt > 0:
                        notify(getstring(333).format(retrycnt, maxattempts), 2)  # Attempt x/y

                    # If there are outstanding items, then commit them to disk now.
                    if self._db.updatecount == 0 and batchcnt > 0:
                        self.save()
                        d.close()
                        visible = False

            # Keep a high rate, so that when the thread is shutdown, we can quickly join the main thread
            time.sleep(0.1)

            # Allow user to change the throttle without having to restart the thread
            minimum_time = int2(__addon__.getSetting("maltUpdateTime"), 4)

        log("service update thread stopped")

    def daemon(self):
        """Main service dispatch"""
        monitor = self._monitor

        # Start watching for file changes, if enabled
        if self._db.library and __addon__.getSetting("maltMonitorLibrary") == "true":
            try:
                self._observer = Observer()
                self._observer.schedule(self, self._db.library, True)
                self._observer.start()
            except:
                notify(getstring(210), 2)
                self._observer = None

        # Start the synopsis update thread, if enabled
        if __addon__.getSetting("maltUpdateEnabled") == "true":
            self._updatethread = Thread(target=self.updatelist)
            self._updatethread.start()

        # --MAIN LOOP--
        while not monitor.abortRequested():
            # Delay 100ms. THIS CALL IS REQUIRED FOR THE PLAYER NOTIFICATIONS TO FIRE
            if monitor.waitForAbort(0.1):
                break
            self.process_settings()
            self.process_commands()

        # Shutdown and wait for the update worker thread
        if self._updatethread is not None:
            self._shutdown.set()
            self._updatethread.join(3)

        # Stop watching for file changes
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()

        # Remove the jar as it is no longer needed
        if os.path.isfile(__picklejar__):  # Will be missing if uninstalling
            os.remove(__picklejar__)

# Sleep the thread for 1 second. This lets imports on the other threads finish up so that they are not locked
time.sleep(1)
log('service started')
Main()
log('service stopped')