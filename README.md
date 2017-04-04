# MALT
MALT uses MyAnimeList services to track what shows you are currently watching, and automatically find and identify videos in your library. With a click of button, simply play the next episode of a show without needing to remember which episode you watched last.

MALT requires an account on MyAnimeList, populated with shows that you are watching. Simply sync inside Kodi to pull down your list, point to the location where you keep your episodes, and MALT will present a list of shows that are ready to watch.

Once you have synced your shows, MALT will work completely offline. You can set it to send updates as soon you finish watching, wait until a sync happens, or never send updates at all.

# Watching progress indicator
When browsing your collection, a simple indicator will appear in the description to show which episodes have been watched, which episodes have a video in the library ready to play, and what you are missing.

You may customize the indicator to show more/less episodes, and specify how the blocks wrap

# Built-in sorting for when a show was last updated
By default, your lists are sorted alphabetically.

If want to sort by when you last updated the show, such as after you finish watching an episode, then simply change the sort to "Last Played".

# Manually increment or decrement progress for a show
Sometimes you may need to change the progress of a show manually. You can do this by opening the context menu for the show and choose the Increment/Decrement options.

# Automatic Season Detection
Some shows split seasons across different database entries, yet typically subbers will not start the episode numbering over from the start. In these situations, a 3rd party season relationship mapping is used to match these episodes the correct entry.

The relationship file is managed by the [Taiga project](https://github.com/erengy/anime-relations). As such, it only updates as needed and infrequently. Freshly added seasonal shows may not recognize episodes until thier mapping has been added.

# Set show synonymns
MALT relies on the list of show titles, provided by MyAnimeList, to properly identify episodes in your library. Occasionally, files will be named differently than what is provided, which causes them to not be recognized.

In these situations, you will want to provide your own custom "synonym" to provide a hint to the recognition system.

Example:
MAL provides the following titles for the show "Active Raid":

    Active Raid: Kidou Kyoushuushitsu Dai Hachi Gakari
    Active Raid: Special Public Security Fifth Division Third Mobile Assault Eighth Unit
    
If the video files are named "Active Raid", then those files will not be recognized and will appear missing in the episode indicator. Simply adding "Active Raid" as a custom synonym will allow them to be detected. You may access this feature from the show's context menu.

# Credit
Much of the recognition system was heavily based on [Taiga](https://github.com/erengy/taiga), and its related project, [Anitomy](https://github.com/erengy/anitomy).
Taiga and Anitomy are Copyright by Eren Okka

# LICENSE
Copyright 2017 Carl Lewis

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.