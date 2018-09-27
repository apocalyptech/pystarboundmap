Python Starbound Mapper
-----------------------

Yet another Starbound mapper!  This is in very early stages, and
apologies if it never gets much beyond this point but it pops up
in your Google results anyway.

Uses:
 - Python 3
 - python-pillow
 - PyQt5
 - py-starbound (by blixt)

**Extremely** rough at the moment, and not suitable for public use
yet.  Will update this with usage info and the like if it ever gets to a nicer
stage.  Uses blixt's lovely
[py-starbound](https://github.com/blixt/py-starbound) to get at the data
(currently it requires some functions which are not yet actually committed to
that project though).

TODO
----

 - Choose maps (totally hardcoded to my own savegames at the moment)
 - Fix object placement
 - Add plants
 - Add NPCs/Enemies/Monsters?
   - (What's a StagehandEntity, I wonder?)
 - Highlight tiles for info
   - Click for full info
 - Go to spawn points, flags
 - Zoom
   - Slider
   - `+`/`-` via keyboard
 - Click-to-drag
 - Open file menu
 - Progress bars while loading stuff
 - Search for item types (ores, quest-related things?)
 - Visualization of explored areas (as defined by light sources)
 - Remember window geometry between runs
 - Autodetect game location
   - Have some methods for Steam detection via other projects, but
     is there any registry entries or something for non-Steam installs?
     Does Starbound even have non-Steam builds?
   - Manually choose install dir, regardless
 - Support for mods
 - Performance improvements
 - Toggles for various element types?
 - Fancier rendering?  (base map materials have "edges" which we completely
   ignore at the moment.  I suspect I'll never actually implement this
   since it'd probably increas our render time for a bunch, and it's not
   really important for anything you'd want to actually use this for)

LICENSE
-------

pystarboundmap is licensed under the
[New/Modified (3-Clause) BSD License](https://opensource.org/licenses/BSD-3-Clause).
A copy is also found in [COPYING.txt](COPYING.txt).
