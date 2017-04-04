# Copyright (c) 2017, Carl Lewis
#
# This source code is released under the MIT license
# https://opensource.org/licenses/MIT

import sys, os, time
from urllib import urlencode
from urlparse import parse_qsl
import xbmc, xbmcaddon, xbmcgui, xbmcplugin
import urlparse
from resources.lib.util import int2
try:
    import cPickle as pickle
except ImportError:
    import pickle

__url__       = sys.argv[0]
__handle__    = int2(sys.argv[1])
__addon__     = xbmcaddon.Addon(id="service.maltracker")
__addonid__   = __addon__.getAddonInfo('id')
__addonname__ = __addon__.getAddonInfo('name')
__profile__   = xbmc.translatePath(__addon__.getAddonInfo("profile"))
__svcpath__   = os.path.join(__addon__.getAddonInfo("path"), 'service.py')
__picklejar__ = os.path.join(__profile__, 'db.bin')
__ipc__       = xbmcgui.Window(10000) # command ipc marshaller
xbmcplugin.setContent(__handle__, 'episodes')

show_progress = __addon__.getSetting("malShowProgress") == "true"
show_avail    = __addon__.getSetting("malShowAvailable") == "true"
ind_nodes     = int2(__addon__.getSetting("malIndNodes"), 13)
ind_wrap      = int2(__addon__.getSetting("malIndWrap"), 13)
ind_offset    = int2(__addon__.getSetting("malIndOffset"), 3)

def get_url(**kwargs):
    return '{0}?{1}'.format(__url__, urlencode(kwargs))

def create_folder(path, title, description=""):
    list_item = xbmcgui.ListItem(label=title)
    if description:
        list_item.setInfo("video", {"plot": description})
    xbmcplugin.addDirectoryItem(__handle__, __url__ + "/" + path, list_item, True)

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

def buildprogressbar(anime):
    # Calculate where in the episode list to render the view
    if anime.episodes > 0 and anime.episodes <= ind_nodes:
        start = 1
        end = anime.episodes
    else:
        start = anime.watched + 1 - ind_offset
        if start < 1:
            start = 1
        end = start + ind_nodes - 1
        if anime.episodes > 0 and end > anime.episodes:
            end = anime.episodes
            start = end - ind_nodes + 1

    # Color blocks
    output = u""
    epi = start
    cnt = 0
    while epi <= end:
        # Wrap if exceeding the threshold
        if cnt > 0 and cnt % ind_wrap == 0:
            output += "\n"

        # Colorize block based on status
        if epi <= anime.watched:
            output += u"[COLOR yellowgreen]\u25A0[/COLOR]"
        elif epi in anime.available:
            output += u"[COLOR steelblue]\u25A0[/COLOR]"
        else:
            output += u"\u25A1"  # hollowed out block
        epi += 1
        cnt += 1

    # X/Y count
    total = anime.episodes
    if total == 0:
        total = "?"
    output += u" {0}/{1}\n".format(anime.watched, total)

    return output

def translatetype(value):
    if value == 1:
        return getstring(325)
    elif value == 2:
        return getstring(326)
    elif value == 3:
        return getstring(327)
    elif value == 4:
        return getstring(328)
    elif value == 5:
        return getstring(329)
    elif value == 6:
        return getstring(330)

def buildvideoitem(anime):
    list_item = xbmcgui.ListItem(label=anime.title)
    nextepisode = anime.watched + 1
    prevepisode = anime.watched - 1

    # Add emphasis to series that can be played
    if show_avail and anime.nextfile:
        title = u"[B][I]{0}[/I][/B]".format(anime.title)
    else:
        title = anime.title

    # Build description
    description = u""
    if show_progress:
        description += buildprogressbar(anime)
    description += getstring(323).format(translatetype(anime.type)) + "\n\n"  # Type: x
    description += (anime.synopsis or getstring(324)) + "\n\n"

    # Set show info
    list_item.setInfo('video', {'title': title,
                                'originaltitle': anime.title,
                                'plot': description,
                                'episode': nextepisode,
                                'tvshowtitle': anime.title,
                                'lastplayed': anime.updated.strftime('%Y-%m-%d %H:%M:%S')})

    # Set video type
    if anime.type == 1:  # TV
        list_item.setInfo('mediatype', 'tvshow')
    elif anime.type == 3:  # MOVIE
        list_item.setInfo('mediatype', 'movie')
    else:
        list_item.setInfo('mediatype', 'episode')

    # Set art assets
    list_item.setArt({'poster': anime.art})

    # Create context menu options
    context = []
    if anime.episodes == 0 or nextepisode <= anime.episodes:
        context.append((getstring(300).format(nextepisode), 'RunScript({0},inc,{1})'.format(__svcpath__, anime.id)))
    if prevepisode > 0 and (anime.episodes == 0 or prevepisode <= anime.episodes):
        context.append((getstring(301).format(prevepisode), 'RunScript({0},dec,{1})'.format(__svcpath__, anime.id)))
    context.append((getstring(314), 'RunScript({0},setstatus,{1})'.format(__svcpath__, anime.id)))
    context.append((getstring(318), 'RunScript({0},syn,{1})'.format(__svcpath__, anime.id)))
    if anime.usersynonyms:
        context.append((getstring(319), 'RunScript({0},syndelete,{1})'.format(__svcpath__, anime.id)))
    list_item.addContextMenuItems(context)

    # Create the link for playback
    if anime.nextfile:
        url = get_url(action='play', video=anime.nextfile, id=anime.id)
        list_item.setProperty('IsPlayable', 'true')
    else:
        url = ""
        list_item.setProperty('IsPlayable', 'false')

    xbmcplugin.addDirectoryItem(__handle__, url, list_item, False)

def buildfolder(list):
    # Build the list of episodes that are ready to play
    for anime in list:
        buildvideoitem(anime)

    xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
    xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_LASTPLAYED)
    xbmcplugin.endOfDirectory(__handle__)


if __name__ == '__main__':
    attempts = 0
    db = None
    while attempts < 20:  # Wait up to 20 seconds
        init = __ipc__.getProperty("malinit") == "true"
        ready = __ipc__.getProperty("malready") == "true"

        # The service needs to be fully up and running and not in the middle of a sync
        if init and ready:
            # If the jar doesnt exist, then the service hasnt finished starting up
            if os.path.isfile(__picklejar__):
                # Load the database from the service layer
                try:
                    fs = open(__picklejar__, "rb")
                    db = pickle.load(fs)
                    fs.close()
                    break
                except:
                    pass

        attempts += 1
        time.sleep(1)  # Wait a second between each attempt

    # If the maximum attempts is reached, then something is not right
    if attempts == 20:
        xbmcgui.Dialog().notification(__addonname__, __addon__.getLocalizedString(211), xbmcgui.NOTIFICATION_ERROR)  # db not ready
        sys.exit()

    paramstring = sys.argv[2][1:]
    params = dict(parse_qsl(paramstring))

    if params:
        if "action" in params:
            if params["action"] == "play":
                play_item = xbmcgui.ListItem(path=params["video"])
                xbmcplugin.setResolvedUrl(__handle__, True, listitem=play_item)

    else:
        # Sanity checks for the progress indicator display
        if ind_wrap < 1:
            ind_wrap = 1
        if ind_offset < 0:
            ind_offset = 0
        if ind_offset > ind_nodes - 1:
            ind_offset = ind_nodes - 1

        # Parse the url for the path the user is currently in
        urlparse.uses_netloc.append("plugin")
        urlparse.uses_fragment.append("plugin")
        urlparse.uses_relative.append('plugin')
        path = urlparse.urlparse(__url__).path

        # Build the status folders
        if path == "//current":
            buildfolder(db.ready)
        elif path == "//watching":
            buildfolder(db.statuslist(1))
        elif path == "//completed":
            buildfolder(db.statuslist(2))
        elif path == "//onhold":
            buildfolder(db.statuslist(3))
        elif path == "//dropped":
            buildfolder(db.statuslist(4))
        elif path == "//plantowatch":
            buildfolder(db.statuslist(6))
        else:
            # If at the root, then build out the list of status folders to traverse
            create_folder("current", getstring(302), getstring(308))
            create_folder("watching", getstring(303), getstring(309))
            create_folder("completed", getstring(304), getstring(310))
            create_folder("onhold", getstring(305), getstring(311))
            create_folder("dropped", getstring(306), getstring(312))
            create_folder("plantowatch", getstring(307), getstring(313))
            xbmcplugin.addSortMethod(__handle__, xbmcplugin.SORT_METHOD_NONE)
            xbmcplugin.endOfDirectory(__handle__)