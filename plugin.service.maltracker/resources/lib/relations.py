# Copyright (c) 2017, Carl Lewis
#
# This source code is released under the MIT license
# https://opensource.org/licenses/MIT

import os
import re
import urllib2

class Rule(object):
    """Episode redirection rule"""
    def __init__(self, match=None):
        self.srcid = []
        self.srcstart = 0
        self.srcend = 0
        self.destid = []
        self.deststart = 0
        self.destend = 0
        self.redirected = False

        if match is not None:
            self.populate(match)

    @staticmethod
    def safeint(value):
        try:
            return int(value)
        except TypeError:
            return 0
        except ValueError:
            return 0

    def populate(self, match):
        self.srcid = match.group(1).split("|")         # left service id list
        self.srcstart = Rule.safeint(match.group(2))   # left ep start
        self.srcend = Rule.safeint(match.group(3))     # left ep end
        self.destid = match.group(4).split("|")        # right service id list
        self.deststart = Rule.safeint(match.group(5))  # right ep start
        self.destend = Rule.safeint(match.group(6))    # right ep end
        self.redirected = match.group(7) == "!"        # self-redirect marker

        # Tilde indicates that the source id should be repeated
        for idx, id in enumerate(self.destid):
            if (id == "~"):
                self.destid[idx] = self.srcid[idx]

class Relationships(object):
    """Keeps a list of episode redirection rules, used when fansubbers do not restart episode numbers over, across one or more cours"""
    _re_ruleset = re.compile("((?:(?:\d+|[?~])(?:\||))+):(\d+)(?:-(\d+|\?))? -> ((?:(?:\d+|[?~])(?:\||))+):(\d+)(?:-(\d+|\?))?(!)?")
    lookup = {}
    meta = {}

    @staticmethod
    def load(filepath):
        if os.path.isfile(filepath):
            try:
                fs = open(filepath, "r")
                text = fs.read()
                fs.close()

                Relationships.parse(text)
                if Relationships.lookup:
                    return True
            except IOError:
                pass
        return False

    @staticmethod
    def update(filepath):
        try:
            # Fetch the latest data from github
            url = "https://raw.githubusercontent.com/erengy/anime-relations/master/anime-relations.txt"
            text = urllib2.urlopen(url).read()

            # Save the file to disk
            dir = os.path.dirname(filepath)
            if not os.path.isdir(dir):
                os.makedirs(dir)

            fs = open(filepath, "w")
            fs.write(text)
            fs.close()

            # Parse the relationship file
            Relationships.parse(text)
            if Relationships.lookup:
                return True
        except:
            pass

        return False

    @staticmethod
    def parse(text):
        # Remove any existing rules
        Relationships.lookup.clear()
        Relationships.meta.clear()

        for line in text.split("\n"):
            # Only care about rules
            if line.startswith("-"):
                # Discard meta data
                raw = line[2:]
                m = Relationships._re_ruleset.match(raw)
                if m:
                    # Create the rule
                    rule = Rule(m)

                    # Map the rule by service id
                    for idx, id in enumerate(rule.srcid):
                        if idx not in Relationships.lookup:
                            Relationships.lookup[idx] = {}
                        Relationships.lookup[idx][id] = rule

                    # If the rule requires a self-redirect, then create it now
                    if rule.redirected:
                        for idx, id in enumerate(rule.destid):
                            Relationships.lookup[idx][id] = rule

                elif ":" in raw:
                    # Meta data
                    key, value = raw.split(": ")
                    Relationships.meta[key] = value

    @staticmethod
    def get(serviceid, animeid):
        try:
            return Relationships.lookup.get(serviceid).get(animeid)
        except:
            return None

    @staticmethod
    def find(serviceid, animeid, episode):
        rule = Relationships.get(serviceid, animeid)
        if rule and episode >= rule.srcstart and (rule.srcend == 0 or episode <= rule.srcend):
            offset = episode - rule.srcstart
            mapped = rule.deststart + offset
            return rule.destid, mapped
        return "", 0
