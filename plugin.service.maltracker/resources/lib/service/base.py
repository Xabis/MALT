# Copyright (c) 2017, Carl Lewis
#
# This source code is released under the MIT license
# https://opensource.org/licenses/MIT

import xbmc, xbmcaddon, xbmcgui

class AnimeService(object):
    def __init__(self, addon):
        self.Addon = addon
        self._badauth = True

    def __getstate__(self):
        d = dict(self.__dict__)
        del d['Addon'] # unneeded for the ipc jar, and causing serialization problems anyway
        return d

    def __setstate__(self, d):
        self.__dict__.update(d)

    @property
    def relationship_index(self):
        return False

    @property
    def id(self):
        return "offline"

    @property
    def cansync(self):
        return not self.badauth

    @property
    def hasAsyncInfo(self):
        return False

    @property
    def badauth(self):
        return self._badauth

    @property
    def authchanged(self):
        return False

    def login(self):
        return False

    def logout(self):
        return False

    def fetch(self, db, progress):
        return False

    def push(self, anime):
        return False

    def fetchAsyncInfo(self, db, anime):
        return False

    def requiresAsyncFetch(self, anime):
        return False

    def status_to_server(self, value):
        return value

    def status_to_local(self, value):
        return value

    def authenticate(self):
        return False

    def log(self, text):
        if self.Addon:
            xbmc.log(u"[{0}] {1}".format(self.Addon.getAddonInfo('name'), text.encode('ascii', 'replace')), level=xbmc.LOGDEBUG)

    def getstring(self, key):
        if self.Addon:
            return self.Addon.getLocalizedString(key)

    def getsetting(self, key):
        if self.Addon:
            return self.Addon.getSetting(key)

    def notify(self, text, level=0):
        if level == 2:
            flag = xbmcgui.NOTIFICATION_ERROR
        elif level == 1:
            flag = xbmcgui.NOTIFICATION_WARNING
        else:
            flag = xbmcgui.NOTIFICATION_INFO
        if self.Addon:
            xbmcgui.Dialog().notification(self.Addon.getAddonInfo('name'), text, flag)
