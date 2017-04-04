# Python port:
# Copyright (c) 2017, Carl Lewis
#
# This source code port is released under the MIT license
# https://opensource.org/licenses/MIT
#
# Original c++ Version:
# https://github.com/erengy/anitomy
# Copyright (c) 2014-2016, Eren Okka
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

import string
import re

kUnknown    = 0
kBracket    = 1
kDelimiter  = 2
kIdentifier = 3
kInvalid    = 4

kFlagNone          = 0
kFlagBracket       = 1 << 0
kFlagNotBracket    = 1 << 1
kFlagDelimiter     = 1 << 2
kFlagNotDelimiter  = 1 << 3
kFlagIdentifier    = 1 << 4
kFlagNotIdentifier = 1 << 5
kFlagUnknown       = 1 << 6
kFlagNotUnknown    = 1 << 7
kFlagValid         = 1 << 8
kFlagNotValid      = 1 << 9
kFlagEnclosed      = 1 << 10
kFlagNotEnclosed   = 1 << 11
kFlagMaskCategories = kFlagBracket | kFlagNotBracket | kFlagDelimiter | kFlagNotDelimiter | kFlagIdentifier | kFlagNotIdentifier | kFlagUnknown | kFlagNotUnknown | kFlagValid | kFlagNotValid
kFlagMaskEnclosed   = kFlagEnclosed | kFlagNotEnclosed

kElementIterateFirst        = 0
kElementAnimeSeason = kElementIterateFirst
kElementAnimeSeasonPrefix   = 1
kElementAnimeTitle          = 2
kElementAnimeType           = 3
kElementAnimeYear           = 4
kElementAudioTerm           = 5
kElementDeviceCompatibility = 6
kElementEpisodeNumber       = 7
kElementEpisodeNumberAlt    = 8
kElementEpisodePrefix       = 9
kElementEpisodeTitle        = 10
kElementFileChecksum        = 11
kElementFileExtension       = 12
kElementFileName            = 13
kElementLanguage            = 14
kElementOther               = 15
kElementReleaseGroup        = 16
kElementReleaseInformation  = 17
kElementReleaseVersion      = 18
kElementSource              = 19
kElementSubtitles           = 20
kElementVideoResolution     = 21
kElementVideoTerm           = 22
kElementVolumeNumber        = 23
kElementVolumePrefix        = 24
kElementIterateLast         = 25
kElementUnknown = kElementIterateLast

kAnimeYearMin = 1900
kAnimeYearMax = 2050
kEpisodeNumberMax = kAnimeYearMin - 1
kVolumeNumberMax = 20

#==============================================================
# Functions
#==============================================================)
def IsHexadecimalString(value):
    return value and all(c in string.hexdigits for c in value)
def IsMostlyLatinString(value):
    if not value:
        return False
    cnt = sum(1 if c <= u"\u024F" else 0 for c in value)
    return cnt / float(len(value)) >= 0.5
def FindAny(haystack, needles, start = 0, end = None):
    for index, c in enumerate(haystack[start:end]):
        if c in needles:
            return start+index
    return -1
def FindAnyReversed(haystack, needles, start = 0, end = None):
    e = end or len(haystack)
    for index, c in enumerate(reversed(haystack[start:end])):
        if c in needles:
            return e - index
    return -1
def TrimString(value, chars):
    first = None
    last = None
    for index, c in enumerate(value):
        if c not in chars:
            first = index
            break
    for index, c in enumerate(reversed(value)):
        if c not in chars:
            last = len(value) - index
            break
    return value[first:last]
def StringToInt(value): #std::wcstol behaviour
    for pos, c in enumerate(value):
        if not c.isdigit():
            value = value[:pos]
            break
    if value != "":
        return int(value)
    return 0
def DebugTokens(toklist):
    out = ""
    footer = ""
    for t in toklist:
        out += t.content

        if t.category == kUnknown:
            char = "?"
        elif t.category == kBracket:
            char = "|"
        elif t.category == kDelimiter:
            char = ","
        elif t.category == kIdentifier:
            char = "#"
        else:
            char = "!"

        l = len(t.content)
        for c in range(0, l):
            footer += char
    print(out + "\n" + footer)

#==============================================================
# Objects
#==============================================================
class Keyword:
    word = None         # type: str
    category = None     # type: int
    identifiable = None # type: bool
    searchable = None   # type: bool
    valid = None        # type: bool

    def __init__(self, word, category, identifiable, searchable, valid):
        self.word = word
        self.category = category
        self.identifiable = identifiable
        self.searchable = searchable
        self.valid = valid


class Keywords:
    list = []
    peekentries = {
        kElementAudioTerm: ["Dual Audio"],
        kElementVideoTerm: ["H264","H.264","h264","h.264"],
        kElementVideoResolution: ["480p","720p","1080p"],
        kElementSource: ["Blu-Ray"]
    }

    def __init__(self):
        self.Add(kElementAnimeSeasonPrefix, False, True, True, ["SAISON","SEASON"])

        self.Add(kElementAnimeType, False, True, True, ["GEKIJOUBAN","MOVIE","OAD","OAV","ONA","OVA","SPECIA","SPECIALS","TV"])
        self.Add(kElementAnimeType, False, False, True, ["SP"])
        self.Add(kElementAnimeType, False, True, False, ["ED","ENDING","NCED","NCOP","OP","OPENING","PREVIEW","PV"])

        self.Add(kElementAudioTerm, True, True, True, ["2.0CH","2CH","5.1","5.1CH","DTS","DTS-ES","DTS5.1","TRUEHD5.1","AAC","AACX2","AACX3","AACX4","AC3","FLAC","FLACX2","FLACX3","FLACX4","LOSSLESS","MP3","OGG","VORBIS","DUALAUDIO","DUAL AUDIO"])

        self.Add(kElementDeviceCompatibility, True, True, True, ["IPAD3","IPHONE5","IPOD","PS3","XBOX","XBOX360"])
        self.Add(kElementDeviceCompatibility, False, True, True, ["ANDROID"])

        self.Add(kElementEpisodePrefix, True, True, True, ["EP","EP.","EPS","EPS.","EPISODE","EPISODE.","EPISODES","CAPITULO","EPISODIO","FOLGE"])
        self.Add(kElementEpisodePrefix, True, True, False, ["E",u"\u7B2C"])

        self.Add(kElementFileExtension, True, True, True, ["3GP","AVI","DIVX","FLV","M2TS","MKV","MOV","MP4","MPG","OGM","RM","RMVB","WEBM","WMV"])
        self.Add(kElementFileExtension, True, True, False, ["AAC","AIFF","FLAC","M4A","MP3","MKA","OGG","WAV","WMA","7Z","RAR","ZIP","ASS","SRT"])

        self.Add(kElementLanguage, True, True, True, ["ENG","ENGLISH","ESPANO","JAP","PT-BR","SPANISH","VOSTFR"])
        self.Add(kElementLanguage, False, True, True, ["ESP","ITA"])

        self.Add(kElementOther, True, True, True, ["REMASTER","REMASTERED","UNCENSORED","UNCUT","TS","VFR","WIDESCREEN","WS"])

        self.Add(kElementReleaseGroup, True, True, True, ["THORA"])

        self.Add(kElementReleaseInformation, True, True, True, ["BATCH","COMPLETE","PATCH","REMUX"])
        self.Add(kElementReleaseInformation, False, True, True, ["END","FINAL"])

        self.Add(kElementReleaseVersion, True, True, True, ["V0","V1","V2","V3","V4"])
        self.Add(kElementSource, True, True, True, ["BD","BDRIP","BLURAY","BLU-RAY","DVD","DVD5","DVD9","DVD-R2J","DVDRIP","DVD-RIP","R2DVD","R2J","R2JDVD","R2JDVDRIP","HDTV","HDTVRIP","TVRIP","TV-RIP","WEBCAST","WEBRIP"])
        self.Add(kElementSubtitles, True, True, True, ["ASS","BIG5","DUB","DUBBED","HARDSUB","RAW","SOFTSUB","SOFTSUBS","SUB","SUBBED","SUBTITLED"])
        self.Add(kElementVideoTerm, True, True, True, ["23.976FPS","24FPS","29.97FPS","30FPS","60FPS","120FPS","8BIT","8-BIT","10BIT","10BITS","10-BIT","10-BITS","HI10","HI10P","H264","H265","H.264","H.265","X264","X265","X.264","AVC","HEVC","DIVX","DIVX5","DIVX6","XVID","AVI","RMVB","WMV","WMV3","WMV9","HQ","LQ","HD","SD"])
        self.Add(kElementVolumePrefix, True, True, True, ["VOL","VOL.","VOLUME"])

    def Exists(self, keyword, category = None):
        keyword = keyword.upper() #normalize
        for item in self.list:
            if item.word == keyword and (not category or item.category == category):
                return True
        return False

    def Add(self, category, identifiable, searchable, valid, keywords):
        for word in keywords:
            if not word:
                continue
            if self.Exists(word):
                continue
            item = Keyword(word, category, identifiable, searchable, valid)
            self.list.append(item)

    def Find(self, category, keyword):
        keyword = keyword.upper() #normalize
        for item in self.list:
            if item.word == keyword:
                if category == kElementUnknown or item.category == category:
                    return item
                return None
        return None

    def Peek(self, filename, offset, size, elements):
        peeklist = []

        for category in self.peekentries:
            for keyword in self.peekentries[category]:
                it = filename.find(keyword,offset,offset+size)
                if it != -1:
                    elements[category] = keyword
                    peeklist.append([it, len(keyword)])
        return peeklist

#instantiate a global copy of the manager
kwmanager = Keywords()


class Token:
    category = None # type: int
    content = None  # type: str
    enclosed = None # type: bool

    def __init__(self, category = kUnknown, content = None, enclosed = False):
        self.category = category
        self.content = content
        self.enclosed = enclosed

    def AppendTo(self, tok):
        tok.content += self.content
        self.category = kInvalid

    def IsSingle(self):
        return self.category == kUnknown and len(self.content) == 1 and self.content != "-"

    def CheckFlags(self, flags):
        if (flags & kFlagMaskEnclosed):
            if not (self.enclosed if (flags & kFlagEnclosed) == kFlagEnclosed else not self.enclosed):
                return False

        if (flags & kFlagMaskCategories):
            def CheckCategory(flags, fe, fn, c):
                return self.category == c if (flags & fe) == fe else self.category != c if (flags & fn) == fn else False

            if CheckCategory(flags, kFlagBracket, kFlagNotBracket, kBracket):
                return True
            if CheckCategory(flags, kFlagDelimiter, kFlagNotDelimiter, kDelimiter):
                return True
            if CheckCategory(flags, kFlagIdentifier, kFlagNotIdentifier, kIdentifier):
                return True
            if CheckCategory(flags, kFlagUnknown, kFlagNotUnknown, kUnknown):
                return True
            if CheckCategory(flags, kFlagNotValid, kFlagValid, kInvalid):
                return True
            return False

        return True


class Tokens(list):
    def FindNext(self, tok, flags):
        index = self.index(tok)
        if index == -1:
            return None
        for tok in self[index+1:]:
            if tok.CheckFlags(flags):
                return tok
        return None

    def FindPrev(self, tok, flags):
        index = self.index(tok)
        if index == -1:
            return None
        for tok in reversed(self[0:index]):
            if tok.CheckFlags(flags):
                return tok
        return None

    def IsIsolated(self, tok):
        '''Checks to see if the specified token is wholly contained by brackets'''
        prev = self.FindPrev(tok, kFlagNotDelimiter)
        if not prev or prev.category != kBracket:
            return False
        next = self.FindNext(tok, kFlagNotDelimiter)
        if not next or next.category != kBracket:
            return False
        return True

    def FindFirst(self, flags, start=None, end=None):
        for tok in self[start:end]:
            if tok.CheckFlags(flags):
                return tok
        return None

    def FindLast(self, flags, start=None, end=None):
        for tok in reversed(self[start:end]):
            if tok.CheckFlags(flags):
                return tok
        return None

    def FindFirstIndex(self, flags, start=0, end=None):
        for index, tok in enumerate(self[start:end]):
            if tok.CheckFlags(flags):
                return start + index
        return -1

    def FindLastIndex(self, flags, start=0, end=None):
        e = end or len(self)
        for index, tok in enumerate(reversed(self[start:end])):
            if tok.CheckFlags(flags):
                return e - index
        return -1

    def distance(self, start, end):
        if start == -1:
            start = 0
        if end == -1:
            end = len(self)
        return end - start


class Tokenizer:
    tokens = Tokens()

    _elements = None # type: Elements
    _filename = None # type: str
    _brackets = [
        ["(",")"],             # U+0028-U+0029 Parenthesis
        ["[","]"],             # U+005B-U+005D Square bracket
        ["{","}"],             # U+007B-U+007D Curly bracket
        [u"\u300C", u"\u300D"], # Corner bracket
        [u"\u300E", u"\u300F"], # White corner bracket
        [u"\u3010", u"\u3011"], # Black lenticular bracket
        [u"\uFF08", u"\uFF09"], # Fullwidth parenthesis
    ]
    _delimiters = " _.&+,|"

    def __init__(self, filename, elements):
        self._filename = filename
        self._elements = elements

    def Tokenize(self):
        del self.tokens[:] #clear list
        self.TokenizeByBrackets()
        return len(self.tokens) > 0

    def TokenizeByBrackets(self):
        is_open = False
        matching_bracket = None
        char_begin = 0
        char_end = len(self._filename)

        def find_first_bracket(text, start):
            for c in range(start, len(text)):
                for p in self._brackets:
                    if (text[c] == p[0]):
                        return [c, p[1]]
            return [len(text), None]

        current_char = 0
        while current_char < char_end and char_begin < char_end:
            if not is_open:
                result = find_first_bracket(self._filename, char_begin)
                current_char = result[0]
                matching_bracket = result[1]
            else:
                current_char = self._filename.find(matching_bracket, char_begin, char_end)
                if (current_char == -1):
                    current_char = len(self._filename)

            offset = char_begin
            size = current_char - char_begin

            #unknown token
            if (size > 0):
                self.TokenizeByPreidentified(is_open, offset, size)

            #found bracket
            if current_char < char_end:
                offset = offset + size
                size = 1

                content = self._filename[offset:offset+size]
                t = Token(kBracket, self._filename[offset:offset + size], True)
                self.tokens.append(t)

                is_open = not is_open
                current_char = current_char + 1
                char_begin = current_char

    def TokenizeByPreidentified(self, enclosed, offset, size):
        pretokens = kwmanager.Peek(self._filename, offset, size, self._elements)

        tokoffset = offset
        suboffset = offset
        subsize = 0

        while tokoffset < offset + size:
            for pt in pretokens:
                if tokoffset == pt[0]:
                    if subsize > 0:
                        self.TokenizeByDelimiters(enclosed, suboffset, subsize)
                    t = Token(kIdentifier, self._filename[pt[0]:pt[0] + pt[1]], enclosed)
                    self.tokens.append(t)

                    suboffset = pt[0]+pt[1]
                    tokoffset = suboffset - 1

                    break

            tokoffset = tokoffset + 1
            subsize = tokoffset - suboffset

        if subsize > 0:
            self.TokenizeByDelimiters(enclosed, suboffset, subsize)

    def TokenizeByDelimiters(self, enclosed, offset, size):
        delimiters = self.GetDelimiters(offset, size)
        if not delimiters:
            t = Token(kUnknown, self._filename[offset:offset + size], enclosed)
            self.tokens.append(t)
            return

        char_begin = offset
        char_end = offset + size
        current_char = offset

        while current_char < char_end:
            current_char = FindAny(self._filename, delimiters, current_char, char_end)
            if (current_char == -1):
                current_char = char_end

            suboffset = char_begin
            subsize = current_char - char_begin

            if subsize > 0:
                content = self._filename[suboffset:suboffset+subsize]
                t = Token(kUnknown, content, enclosed)
                self.tokens.append(t)

            if current_char < char_end:
                content = self._filename[suboffset+subsize:suboffset+subsize+1]
                t = Token(kDelimiter, content, enclosed)
                self.tokens.append(t)

                current_char = current_char + 1
                char_begin = current_char
        self.ValidateDelimiterTokens()

    def ValidateDelimiterTokens(self):
        for tok in self.tokens:
            if tok.category != kDelimiter:
                continue

            delimiter = tok.content
            prev_token = self.tokens.FindPrev(tok, kFlagValid)
            next_token = self.tokens.FindNext(tok, kFlagValid)

            if next_token and prev_token:
                #dont split group names, keywords, episode number, etc
                if delimiter != " " and delimiter != "_":
                    if prev_token.IsSingle():
                        tok.AppendTo(prev_token)
                        while next_token and next_token.category == kUnknown:
                            next_token.AppendTo(prev_token)
                            if not next_token:
                                continue
                            next_token = self.tokens.FindNext(next_token, kFlagValid)
                            if not next_token:
                                continue

                            if next_token.category == kDelimiter and next_token.content == delimiter:
                                next_token.AppendTo(prev_token)
                                next_token = self.tokens.FindNext(next_token, kFlagValid)
                        continue
                    if next_token.IsSingle():
                        tok.AppendTo(prev_token)
                        next_token.AppendTo(prev_token)
                        continue

                #check for adjacent delimiters
                if prev_token.category == kUnknown and next_token.category == kDelimiter:
                    next_delimiter = next_token.content
                    if delimiter != next_delimiter and delimiter != ",":
                        if next_delimiter == " " or next_delimiter == "_":
                            tok.AppendTo(prev_token)
                elif prev_token.category == kDelimiter and next_token.category == kDelimiter:
                    prev_delimiter = prev_token.content
                    next_delimiter = next_token.content

                    if prev_delimiter == next_delimiter and prev_delimiter != delimiter:
                        tok.category = kUnknown

                #check special cases, such as 01+02
                if delimiter == "&" or delimiter == "+":
                    if prev_token.category == kUnknown and next_token.category == kUnknown:
                        if prev_token.content.isdigit() and next_token.content.isdigit():
                            tok.AppendTo(prev_token)
                            next_token.AppendTo(prev_token)

        # remove tokens marked as invalid
        self.tokens[:] = [x for x in self.tokens if x.category != kInvalid]

    def GetDelimiters(self, offset, size):
        delimiters = ""
        for c in range(offset, offset + size):
            char = self._filename[c]
            if not char.isalnum():
                if char in self._delimiters:
                    if not char in delimiters:
                        delimiters = delimiters + char
        return delimiters

class Parser:
    parse_group = True
    parse_title = True
    parse_episode = True

    _elements = None # type: Elements
    _tokens = None   # type: Tokens
    _searchable = [kElementAnimeSeasonPrefix,kElementAnimeType,kElementAudioTerm,kElementDeviceCompatibility,kElementEpisodePrefix,kElementFileChecksum,kElementLanguage,kElementOther,kElementReleaseGroup,kElementReleaseInformation,kElementReleaseVersion,kElementSource,kElementSubtitles,kElementVideoResolution,kElementVideoTerm,kElementVolumePrefix]
    _multiple = [kElementAnimeSeason, kElementAnimeType, kElementAudioTerm, kElementDeviceCompatibility, kElementEpisodeNumber, kElementLanguage, kElementOther, kElementReleaseInformation, kElementSource, kElementVideoTerm]
    _numericalmap = {"1st":"1","First":"1","2nd":"2","Second":"2","3rd":"3","Third":"3","4th":"4","Fourth":"4","5th":"5","Fifth":"5","6th":"6","Sixth":"6","7th":"7","Seventh":"7","8th":"8","Eighth":"8","9th":"9","Ninth":"9"}
    _found_episode_keywords = False

    _re_episode_single = re.compile("(\d{1,3})[vV](\d)$") #re.fullmatch not available until py3.4, so tacking on an anchor for these
    _re_episode_multi  = re.compile("(\d{1,3})(?:[vV](\d))?[-~&+](\d{1,3})(?:[vV](\d))?$")
    _re_season_range   = re.compile("S?(\d{1,2})(?:-S?(\d{1,2}))?(?:x|[ ._-x]?E)(\d{1,3})(?:-E?(\d{1,3}))?$", re.IGNORECASE)
    _re_episode_frac   = re.compile("\d+\.5$")
    _re_episode_hash   = re.compile("#(\d{1,3})(?:[-~&+](\d{1,3}))?(?:[vV](\d))?$")
    _re_episode_jpn    = re.compile(u"(\d{1,3})\u8A71$")
    _re_volume_single  = re.compile("(\d{1,2})[vV](\d)$")
    _re_volume_multi   = re.compile("(\d{1,2})[-~&+](\d{1,2})(?:[vV](\d))?$")

    _dashes = u"-\u2010\u2011\u2012\u2013\u2014\u2015"
    _dasheswithspace = u" -\u2010\u2011\u2012\u2013\u2014\u2015"

    def __init__(self, elements, tokens):
        self._elements = elements
        self._tokens = tokens

    def Parse(self):
        self.SearchForKeywords()
        self.SearchForIsolatedNumbers()
        if self.parse_episode:
            self.SearchForEpisodeNumber()
        self.SearchForAnimeTitle()
        if self.parse_group and kElementReleaseGroup not in self._elements:
            self.SearchForReleaseGroup()
        if self.parse_title and kElementEpisodeNumber in self._elements:
            self.SearchForEpisodeTitle()
        self.ValidateElements()

        return kElementAnimeTitle in self._elements

    def IsResolution(self, str):
        size = len(str)
        if size > 6:
            pos = FindAny(str, u"xX\u00D7")  # multiplier unicode
            if (pos != -1 and pos >= 3 and pos <= size - 4):
                if str[:pos].isdigit() and str[pos + 1:].isdigit():
                    return True
        elif size > 3 and str.endswith(("p", "P")) and str[:-1].isdigit():
            return True
        return False

    def IsCrc32(self, str):
        return len(str) == 8 and IsHexadecimalString(str)

    def IsDashCharacter(self, str):
        if len(str) != 1:
            return False
        return str in self._dashes

    def CheckSeasonKeyword(self, tok):
        #check numerical prefixes (1st, 2nd, etc)
        previous_token = self._tokens.FindPrev(tok, kFlagNotDelimiter)
        if (previous_token):
            if previous_token.content in self._numericalmap:
                self._elements[kElementAnimeSeason] = self._numericalmap[previous_token.content]
                previous_token.category = kIdentifier
                tok.category = kIdentifier
                return True

        #check numerical suffixes (1, 2, 3, etc)
        next_token = self._tokens.FindNext(tok, kFlagNotDelimiter)
        if (next_token and next_token.content.isdigit()):
            self._elements[kElementAnimeSeason] = next_token.content
            next_token.category = kIdentifier
            tok.category = kIdentifier
            return True
        return False

    def CheckExtentKeyword(self, category, tok):
        next_token = self._tokens.FindNext(tok, kFlagNotDelimiter)
        if next_token and next_token.category == kUnknown:
            if FindAny(next_token.content, string.digits) == 0:
                if category == kElementEpisodeNumber:
                    if not self.MatchEpisodePatterns(next_token.content, next_token):
                        self.SetEpisodeNumber(next_token.content, next_token, False)
                elif category == kElementVolumeNumber:
                    if not self.MatchVolumePatterns(next_token.content, next_token):
                        self.SetVolumeNumber(next_token.content, next_token, False)
                else:
                    return False

                tok.category = kIdentifier
                return True
        return False

    def SetEpisodeNumber(self, number, tok, validate):
        if validate and StringToInt(number) > kEpisodeNumberMax:
            return False

        tok.category  = kIdentifier
        category = kElementEpisodeNumber
        if self._found_episode_keywords and kElementEpisodeNumber in self._elements:
            content = self._elements[kElementEpisodeNumber]
            comp = StringToInt(number) - StringToInt(content)

            if comp > 0:
                category = kElementEpisodeNumberAlt
            elif comp < 0:
                self._elements.pop(kElementEpisodeNumber)
                self._elements[kElementEpisodeNumberAlt] = content
            else:
                return False

        self._elements[category] = number
        return True

    def SetAlternativeEpisodeNumber(self, number, tok):
        self._elements[kElementEpisodeNumberAlt] = number
        tok.category = kIdentifier
        return True

    def SetVolumeNumber(self, number, tok, validate):
        if validate and StringToInt(number) > kVolumeNumberMax:
            return False

        self._elements[kElementVolumeNumber] = number
        tok.category = kIdentifier
        return True

    def MatchVolumePatterns(self, word, tok):
        if word.isdigit():
            return False
        word = TrimString(word, " -")

        front = word[:1].isdigit()
        back = word[-1:].isdigit()

        if front and back:
            # single volume - e.g. "01v2"
            m = self._re_volume_single.match(word)
            if m:
                self.SetVolumeNumber(m.group(1), tok, False)
                self._elements[kElementReleaseVersion] = m.group(2)
                return True

            # multi volume - e.g. "01-02", "03-05v2"
            m = self._re_volume_multi.match(word)
            if m:
                lower = m.group(1)
                upper = m.group(2)

                if StringToInt(lower) < StringToInt(upper):
                    if self.SetVolumeNumber(lower, tok, True):
                        self.SetVolumeNumber(upper, tok, False)
                        if m.group(3):
                            self._elements[kElementReleaseVersion] = m.group(3)
                        return True
        return False

    def MatchEpisodePatterns(self, word, tok):
        if word.isdigit():
            return False
        word = TrimString(word, " -")

        front = word[:1].isdigit()
        back = word[-1:].isdigit()

        if front and back:
            # single episode - e.g. "01v2"
            m = self._re_episode_single.match(word)
            if m:
                tok.category = kIdentifier
                self.SetEpisodeNumber(m.group(1), tok, False)
                self._elements[kElementReleaseVersion] = m.group(2)
                return True

            # episode ranges - e.g. "01-02", "03-05v2"
            m = self._re_episode_multi.match(word)
            if m:
                lower = m.group(1)
                upper = m.group(3)

                if StringToInt(lower) < StringToInt(upper):
                    if self.SetEpisodeNumber(lower, tok, True):
                        self.SetEpisodeNumber(upper, tok, False)
                        if m.group(2):
                            self._elements[kElementReleaseVersion] = m.group(2)
                        if m.group(4):
                            self._elements[kElementReleaseVersion] = m.group(4)
                        return True

        if back:
            # season + episode, can be single or a range - e.g. "2x01", "S01E03", "S01-02xE001-150"
            m = self._re_season_range.match(word)
            if m:
                self._elements[kElementAnimeSeason] = m.group(1)
                if m.group(2):
                    self._elements[kElementAnimeSeason] = m.group(2)
                self.SetEpisodeNumber(m.group(3), tok, False)
                if m.group(4):
                    self.SetEpisodeNumber(m.group(4), tok, False)
                return True

        if not front:
            # episode type - e.g. "ED1", "OP4a", "OVA2"
            number_begin = FindAny(word, string.digits)
            prefix = word[:number_begin]

            keyword = kwmanager.Find(kElementAnimeType, prefix)
            if keyword:
                self._elements[kElementAnimeType] = prefix

                number = word[number_begin:]
                if self.MatchEpisodePatterns(number, tok) or self.SetEpisodeNumber(number, tok, True):
                    idx = self._tokens.index(tok)
                    if idx != -1:
                        # Split token
                        tok.content = number
                        newtok = Token(kIdentifier if keyword.identifiable else kUnknown, prefix, tok.enclosed)
                        self._tokens.insert(idx, newtok)

                    return True

        if front and back:
            # fractional episodes - e.g. "07.5"
            m = self._re_episode_frac.match(word)
            if m:
                if self.SetEpisodeNumber(word, tok, True):
                    return True

        if front and not back:
            # partial episodes - e.g. "4a", "111C"
            number_end = FindAnyReversed(word, string.digits)
            suffix = word[number_end:]
            if len(suffix) == 1 and ((suffix >= "A" and suffix <= "C") or  (suffix >= "a" and suffix <= "c")):
                if self.SetEpisodeNumber(word, tok, True):
                    return True

        if back:
            # episodes with hash sigh - e.g. "#01", "#02-03v2"
            m = self._re_episode_hash.match(word)
            if m:
                if self.SetEpisodeNumber(m.group(1), tok, True):
                    if m.group(2):
                        self.SetEpisodeNumber(m.group(2), tok, False)
                    if m.group(3):
                        self._elements[kElementReleaseVersion] = m.group(3)
                    return True

        if front:
            # U+8A71 is used as counter for stories, episodes of TV series, etc.
            m = self._re_episode_jpn.match(word)
            if m:
                self.SetEpisodeNumber(m.group(1), tok, False)

        return False

    def SearchForKeywords(self):
        for tok in self._tokens:
            if tok.category != kUnknown:
                continue

            word = TrimString(tok.content, " -")
            if not word:
                continue

            # skip any numeric token that isnt a possible CRC
            if len(word) != 8 and word.isdigit():
                continue

            category = kElementUnknown
            keyword = kwmanager.Find(category, word)

            if (keyword):
                category = keyword.category
                if not self.parse_group and category == kElementReleaseGroup:
                    continue
                if category not in self._searchable or not keyword.searchable:
                    continue
                if category not in self._multiple and category in self._elements:
                    continue
                if category == kElementAnimeSeasonPrefix:
                    self.CheckSeasonKeyword(tok)
                    continue
                elif category == kElementEpisodePrefix:
                    if keyword.valid:
                        self.CheckExtentKeyword(kElementEpisodeNumber, tok)
                        pass
                    continue
                elif category == kElementReleaseVersion:
                    word = word[1:]
                elif category == kElementVolumePrefix:
                    self.CheckExtentKeyword(kElementVolumeNumber, tok)
                    continue
            else:
                if not kElementFileChecksum in self._elements and self.IsCrc32(word):
                    category = kElementFileChecksum
                elif not kElementVideoResolution in self._elements and self.IsResolution(word):
                    category = kElementVideoResolution

            if category != kElementUnknown:
                self._elements[category] = word
                if not keyword or keyword.identifiable:
                    tok.category = kIdentifier

    def SearchForIsolatedNumbers(self):
        for tok in self._tokens:
            if tok.category != kUnknown or not tok.content.isdigit() or not self._tokens.IsIsolated(tok):
                continue
            number = StringToInt(tok.content)

            # anime year
            if number >= kAnimeYearMin and number <= kAnimeYearMax:
                if not kElementAnimeYear in self._elements:
                    self._elements[kElementAnimeYear] = tok.content
                    tok.category = kIdentifier
                    continue

            # video resolution
            if number == 480 or number == 720 or number == 1080:
                if not kElementVideoResolution in self._elements:
                    self._elements[kElementVideoResolution] = tok.content
                    tok.category = kIdentifier
                    continue

    def SearchForEpisodeNumber(self):
        subtokens = Tokens()
        for tok in self._tokens:
            if tok.category == kUnknown:
                if FindAny(tok.content, string.digits) != -1:
                    subtokens.append(tok)

        if not subtokens:
            return
        self._found_episode_keywords = kElementEpisodeNumber in self._elements

        # check if the tokens match any of the known patterns
        if self.SearchForEpisodePatterns(subtokens):
            return

        # discard if an episode was identified
        if kElementEpisodeNumber in self._elements:
            return

        # remove all tokens that are not numeric
        subtokens[:] = [x for x in subtokens if x.content.isdigit()]
        if not subtokens:
            return

        # e.g. "01 (176)", "29 (04)"
        if self.SearchForEquivalentNumbers(subtokens):
            return

        # e.g. " - 08"
        if self.SearchForSeparatedNumbers(subtokens):
            return

        # e.g. "[12]", "(2006)"
        if self.SearchForIsolatedEpisodes(subtokens):
            return

        # Consider using the last number as a last resort
        self.SearchForLastNumber(subtokens)

    def TokenPreceedsNumber(self, tok):
        septok = self._tokens.FindNext(tok, kFlagNotDelimiter)
        if septok:
            seplist = {"&": True, "of": False}
            for sep in seplist:
                if septok.content == sep:
                    othertok = self._tokens.FindNext(septok, kFlagNotDelimiter)
                    if othertok and othertok.content.isdigit():
                        self.SetEpisodeNumber(tok.content, tok, False)
                        if seplist[sep]:
                            self.SetEpisodeNumber(othertok.content, othertok, False)
                        septok.category = kIdentifier
                        othertok.category = kIdentifier
                        return True
        return False

    def NumberComesAfterPrefix(self, category, tok):
        number_begin = FindAny(tok.content, string.digits)
        keyword = kwmanager.Find(category, tok.content[:number_begin])
        if keyword:
            number = tok.content[number_begin:]
            if category == kElementEpisodePrefix:
                if not self.MatchEpisodePatterns(number, tok):
                    self.SetEpisodeNumber(number, tok, False)
                return True
            elif category == kElementVolumePrefix:
                if not self.MatchVolumePatterns(number, tok):
                    self.SetVolumeNumber(number, tok, False)
                return True
        return False

    def SearchForEpisodePatterns(self, toklist):
        for tok in toklist:
            front = tok.content[:1].isdigit()
            if front:
                # e.g. "8 & 10", "01 of 24"
                if self.TokenPreceedsNumber(tok):
                    return True
            else:
                # e.g. "EP.1", "Vol.1"
                if self.NumberComesAfterPrefix(kElementEpisodePrefix, tok):
                    return True
                if self.NumberComesAfterPrefix(kElementVolumePrefix, tok):
                    return True
            # check if the token is an episode identifier
            if self.MatchEpisodePatterns(tok.content, tok):
                return True
        return False

    def SearchForSeparatedNumbers(self, toklist):
        for tok in toklist:
            prev = self._tokens.FindPrev(tok, kFlagNotDelimiter)
            if prev and prev.category == kUnknown and self.IsDashCharacter(prev.content):
                if self.SetEpisodeNumber(tok.content, tok, True):
                    prev.category = kIdentifier
                    return True
        return False


    def SearchForIsolatedEpisodes(self, toklist):
        for tok in toklist:
            if not tok.enclosed or not self._tokens.IsIsolated(tok):
                continue
            if self.SetEpisodeNumber(tok.content, tok, True):
                return True
        return False

    def SearchForEquivalentNumbers(self, toklist):
        for tok in toklist:
            if self._tokens.IsIsolated(tok) and StringToInt(tok.content) > kEpisodeNumberMax:
                continue

            # Find the first enclosed, isolated, non-delimiter token
            next_token = self._tokens.FindNext(tok, kFlagNotDelimiter)
            if not next_token or next_token.category != kBracket:
                continue
            next_token = self._tokens.FindNext(next_token, kFlagEnclosed | kFlagNotDelimiter)
            if not next_token or next_token.category != kUnknown:
                continue
            if not self._tokens.IsIsolated(next_token) or not next_token.content.isdigit() or StringToInt(next_token.content) > kEpisodeNumberMax:
                continue

            # set the episode range based on which is number is the smallest
            if int(tok.content) < int(next_token.content):
                self.SetEpisodeNumber(tok.content, tok, False)
                self.SetAlternativeEpisodeNumber(next_token.content, next_token)
            else:
                self.SetEpisodeNumber(next_token.content, next_token, False)
                self.SetAlternativeEpisodeNumber(tok.content, tok)

            return True
        return False

    def SearchForLastNumber(self, toklist):
        for tok in toklist:
            # Assuming that episode number always comes after the title, first token
            # cannot be what we're looking for
            index = self._tokens.index(tok)
            if index == 0:
                continue

            # An enclosed token is unlikely to be the episode number at this point
            if tok.enclosed:
                continue

            # Ignore if it's the first non-enclosed, non-delimiter token
            if all(t.enclosed or t.category == kDelimiter for t in self._tokens[:index]):
                continue

            # Ignore if the previous token is "Movie" or "Part"
            prev = self._tokens.FindPrev(tok, kFlagNotDelimiter)
            if prev.category == kUnknown:
                if prev.content == "Movie" or prev.content == "Part":
                    continue

            if self.SetEpisodeNumber(tok.content, tok, True):
                return True
        return False

    def SearchForAnimeTitle(self):
        enclosed_title = False
        start = self._tokens.FindFirstIndex(kFlagNotEnclosed | kFlagUnknown)
        if start == -1:
            enclosed_title = True
            skipped_prev = False
            start = 0

            while True:
                start = self._tokens.FindFirstIndex(kFlagUnknown, start)
                if start == -1:
                    break

                if IsMostlyLatinString(self._tokens[start].content):
                    if skipped_prev:
                        break

                start = self._tokens.FindFirstIndex(kFlagBracket, start)
                start = self._tokens.FindFirstIndex(kFlagUnknown, start)
                skipped_prev = True

                if start == -1:
                    return

        end = self._tokens.FindFirstIndex(kFlagIdentifier | (kFlagBracket if enclosed_title else kFlagNone), start)
        if not enclosed_title:
            last_bracket = end
            bracket_open = False

            for loc, tok in enumerate(self._tokens[start:end]):
                if tok.category == kBracket:
                    last_bracket = start + loc
                    bracket_open = not bracket_open
            if bracket_open:
                end = last_bracket

        if not enclosed_title:
            if end == -1:
                curtok = self._tokens.FindLast(kFlagNotDelimiter)
            else:
                curtok = self._tokens.FindPrev(self._tokens[end], kFlagNotDelimiter)

            while curtok and curtok.category == kBracket and curtok.content != ")":
                curtok = self._tokens.FindPrev(curtok, kFlagBracket)
                if curtok:
                    end = self._tokens.index(curtok)
                    curtok = self._tokens.FindPrev(curtok, kFlagNotDelimiter)

        self.BuildElement(kElementAnimeTitle, False, start, end)

    def SearchForReleaseGroup(self):
        end = 0
        while True:
            start = self._tokens.FindFirstIndex(kFlagEnclosed | kFlagUnknown, end)
            if start == -1:
                return

            end = self._tokens.FindFirstIndex(kFlagBracket | kFlagIdentifier, start)
            if end == -1 or self._tokens[end].category != kBracket:
                continue

            prev = self._tokens.FindPrev(self._tokens[start], kFlagNotDelimiter)
            if not prev and prev.category != kBracket:
                continue

            self.BuildElement(kElementReleaseGroup, True, start, end)
            return

    def SearchForEpisodeTitle(self):
        end = 0
        while True:
            start = self._tokens.FindFirstIndex(kFlagNotEnclosed | kFlagUnknown, end)
            if start == -1:
                return

            end = self._tokens.FindFirstIndex(kFlagBracket | kFlagIdentifier, start)
            if self._tokens.distance(start, end) <= 2 and self.IsDashCharacter(self._tokens[start].content):
                continue

            self.BuildElement(kElementEpisodeTitle, False, start, end)
            return

    def BuildElement(self, category, keep_delim, start, end):
        if end == -1:
            end = None
        value = ""
        for tok in self._tokens[start:end]:
            if tok.category == kUnknown:
                value += tok.content
                tok.category = kIdentifier
            elif tok.category == kBracket:
                value += tok.content
            elif tok.category == kDelimiter:
                delim = tok.content
                if keep_delim:
                    value += delim
                else:
                    if delim == "," or delim == "&":
                        value += delim
                    else:
                        value += " "

        if not keep_delim:
            value = TrimString(value, self._dasheswithspace)
        if value:
            self._elements[category] = value

    def ValidateElements(self):
        if kElementAnimeType in self._elements and kElementEpisodeTitle in self._elements:
            title = self._elements[kElementEpisodeTitle]
            atype = self._elements[kElementAnimeType]

            try:
                title.index(atype) # only continues if atype is in the title
                if len(title) == len(atype):
                    del self._elements[kElementEpisodeTitle]
                elif kwmanager.Exists(atype, kElementAnimeType):
                    del self._elements[kElementAnimeType]
            except:
                pass #discard


class Elements(dict):
    def __setitem__(self, key, value):
        if key in self:
            if isinstance(self[key], list):
                return self[key].append(value)
            else:
                value = [self[key], value]
        dict.__setitem__(self, key, value)

class Anitomy:
    elements = Elements()

    parse_ext = True
    parse_group = True
    parse_title = True
    parse_episode = True

    def parse(self, filename):
        self.elements.clear()
        if (self.parse_ext):
            result = self.RemoveExtensionFromFilename(filename)
            if (result):
                filename = result["name"]
                self.elements[kElementFileExtension] = result["ext"]

        if not filename:
            return False
        self.elements[kElementFileName] = filename

        # split the string into tokens
        t = Tokenizer(filename, self.elements)
        if not t.Tokenize():
            return False

        # bin the tokens into their appropriate buckets
        p = Parser(self.elements, t.tokens)
        p.parse_episode = self.parse_episode
        p.parse_group = self.parse_group
        p.parse_title = self.parse_title
        if not p.Parse():
            return False

        return True

    def RemoveExtensionFromFilename(self, filename):
        pos = filename.rfind('.')
        if (pos == -1):
            return False
        ext = filename[pos + 1:]
        if (len(ext) > 4):
            return False
        if not ext.isalnum():
            return False
        if not kwmanager.Exists(ext, kElementFileExtension):  #must be a recognized file extention
            return False
        return {"name": filename[:pos], "ext": ext}