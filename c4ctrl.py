#!/usr/bin/env python3
#
# c4ctrl: Command line client for AutoC4

import sys

class C4Interface():
    """Interaction with the C4 home automation system."""

    port = 1883
    broker = "autoc4.labor.koeln.ccc.de"
    qos = 0
    retain = True
    debug = False

    def __init__(self, topic=None):
        # Set a default topic
        if topic: self.topic = topic

    def push(self, cmd, topic=None, retain=True):
        """Send cmd to topic via the MQTT broker."""
        from paho.mqtt import publish

        # Overwrite defaults
        if topic: self.topic = topic
        if retain == False: self.retain = retain

        if type(cmd) == list:
            # Add <qos> and <retain> to every message
            for item in cmd.copy():
                if type(item) == dict:
                    item["qos"] = self.qos
                    item["retain"] = self.retain
                elif type(item) == tuple:
                    new_item = (
                        item[0] or self.topic, # topic
                        item[1], # payload
                        self.qos, # qos
                        self.retain # retain
                        )
                    cmd.remove(item)
                    cmd.append(new_item)
                        
            if self.debug: return print("[DEBUG] inhibited messages:", cmd)

            publish.multiple(cmd,
                    hostname=self.broker,
                    port=self.port)

        else:
            if self.debug:
                return print("[DEBUG] inhibited message to '{}': '{}'".format(
                        self.topic, cmd))

            publish.single(self.topic,
                    payload=cmd,
                    qos=self.qos,
                    retain=self.retain,
                    hostname=self.broker,
                    port=self.port)

    def pull(self, topic=[]):
        """Return current state of topic."""
        from paho.mqtt import subscribe
        topic = topic or self.topic
        # <topic> must be a list
        if type(topic) == str:
            topic = [topic]

        if self.debug:
            print("[DEBUG] inhibited query for:", topic)
            return []

        return subscribe.simple(topic,
                msg_count=len(topic),
                qos=self.qos,
                hostname=self.broker,
                port=self.port)

    def status(self):
        """Print current status (open or closed) of C4."""
        st = self.pull("club/status")

        # Produce fake result to prevent errors if in debug mode
        if C4Interface.debug:
            print("[DEBUG] Warning: handing over fake data to allow further execution!")
            class st: pass
            st.payload = b'\x00'

        if st.payload == b'\x01':
            print("Club is open")
        else:
            print("Club is closed")

    def open_gate(self):
        """Open the gate."""
        self.push(cmd=b'\x01', topic="club/gate", retain=False)

    def shutdown(self, force=False):
        """Invoke the shutdown routine.""" 
        if force:
            payload = b'\x44'
        else:
            payload = b'\x00'
        self.push(cmd=payload, topic="club/shutdown", retain=False)


class Dmx:
    """Abstraction of the 3 channel LED cans in the club."""

    template = "000000"

    def __init__(self, topic, color=None):
        self.topic = topic
        self.set_color(color or self.template)
        self.is_master = topic.rfind("/master") == len(topic)-7 # 7 = len("/master")

    def __repr__(self):
        return "<Dmx '{}: {}'>".format(self.topic, self.color)

    def _pad_color(self, color):
        """Merge hex color value into hex template.

        Expand 4 bit hex code notation (eg. #f0f) and pad with template."""
        if len(color) > len(self.template): # Truncate
            print("Warning: truncating color value {} to {}".format(
                color, color[:len(self.template)]))
            return color[:len(self.template)]

        # Expand 3 char codes and codes of half the required length.
        # Yet, lets presume that a 6-char code should never be expanded.
        if len(color) != 6 and len(color) == 3 or len(color) == (len(self.template) / 2):
            expanded = ""
            for c in color:
                expanded += c*2
            color = expanded

        if len(color) == len(self.template): # Nothing more to do
            return color

        # Add padding
        color = color + self.template[len(color):]
        return color

    def set_color(self, color):
        """Set color (hex) for this instance.

        The color is then available via its color variable."""
        color = self._pad_color(color)

        self.color = color
        self.payload = bytearray.fromhex(color)


class Dmx4(Dmx):
    """Abstraction of the 4 channel LED cans in the club."""

    template = "000000ff"

    def __repr__(self):
        return "<Dmx4 '{}: {}'>".format(self.topic, self.color)


class Dmx7(Dmx):
    """Abstraction of the 7 channel LED cans in the club."""

    template = "000000000000ff"

    def __repr__(self):
        return "<Dmx7 '{}: {}'>".format(self.topic, self.color)


class C4Room:
    """Base class for club rooms."""

    def __init__(self):
        self.c4 = C4Interface()

    def _interactive_light_switch(self):
        # Interactively ask for input
        print("[{}]".format(self.name))
        print("Please enter 0 or 1 for every lamp:")
        for level in range(len(self.switches)):
            print((level * '|') + ",- " + self.switches[level][0])

        # Current state of witches
        state = ""
        req = []
        for t in self.switches:
            req.append(t[1])
        responce = self.c4.pull(req)
        for sw in self.switches:
            for r in responce:
                if r.topic == sw[1]:
                    state = state + str(int.from_bytes(r.payload,
                            byteorder="little"))
        print(state) # Present current state

        try:
            userinput = sys.stdin.readline().rstrip('\n')
        except KeyboardInterrupt:
            print("\rInterrupted by user.")
            return ""

        return userinput

    def light_switch(self, userinput=""):
        """Switch lamps in this rooms on and off."""
        if not userinput:
            userinput = self._interactive_light_switch()

        if len(userinput) != len(self.switches):
            if int(userinput) <= 15 and len(bin(int(userinput))) <= len(self.switches)+2:
                # +2 because bin() returns something like 'b0...'
                # Try to interpret as integer
                binary = bin(int(userinput))[2:]
                userinput = str(len(self.switches)*'0')[:-len(binary)] + binary
            else:
                print("Error: wrong number of digits (expected {}, got {})!".format(
                        len(self.switches), len(userinput)))
                return False

        cmd=[]
        for si in range(len(self.switches)):
            if userinput[si] not in "01":
                print("Error: invalid digit: " + userinput[si])
                return False
            cmd.append({
                "topic" : self.switches[si][1],
                "payload" : bytearray([int(userinput[si])])
            })

        return self.c4.push(cmd)

    def set_colorscheme(self, colorscheme, magic):
        """Apply colorscheme to the LED Cans in this room."""
        cmd = []
        for light in self.lights:
            if colorscheme.color_for(light.topic):
                if magic != "none" and magic != '0': # Send color to ghost, but skip masters
                    if light.is_master: continue

                    mode_id, error = Fluffy().mode_id(magic)
                    if error:
                        print("Warning: unknown mode \"{}\". Using default.".format(magic))

                    light.set_color(colorscheme.color_for(light.topic))
                    cmd.append({
                        "topic" : "ghosts" + light.topic[light.topic.find('/'):],
                        "payload" : light.payload + int(mode_id).to_bytes(1, "little")
                    })
                else:
                    light.set_color(colorscheme.color_for(light.topic))
                    cmd.append({
                        "topic" : light.topic,
                        "payload" : light.payload
                    })

        # Do not retain "magic" messages
        return self.c4.push(cmd, retain=(not magic))


class Wohnzimmer(C4Room):
    """The Wohnzimmer."""

    name = "Wohnzimmer"
    switches = (
            ("Tür", "licht/wohnzimmer/tuer"),
            ("Mitte", "licht/wohnzimmer/mitte"),
            ("Flur", "licht/wohnzimmer/gang"),
            ("Küche", "licht/wohnzimmer/kueche")
        )
    master = Dmx7("dmx/wohnzimmer/master")
    lights = (
            Dmx7("dmx/wohnzimmer/master"),
            Dmx7("dmx/wohnzimmer/tuer1"),
            Dmx7("dmx/wohnzimmer/tuer2"),
            Dmx7("dmx/wohnzimmer/tuer3"),
            Dmx7("dmx/wohnzimmer/mitte1"),
            Dmx7("dmx/wohnzimmer/mitte2"),
            Dmx7("dmx/wohnzimmer/mitte3"),
            Dmx7("dmx/wohnzimmer/gang"),
            Dmx7("dmx/wohnzimmer/baellebad"),
            Dmx("led/kitchen/sink")
        )


class Plenarsaal(C4Room):
    """The Plenarsaal."""

    name = "Plenarsaal"
    switches = (
            ("Vorne/Wand", "licht/plenar/vornewand"),
            ("Vorne/Fenster", "licht/plenar/vornefenster"),
            ("Hinten/Wand", "licht/plenar/hintenwand"),
            ("Hinten/Fenster", "licht/plenar/hintenfenster")
        )
    master = Dmx7("dmx/plenar/master")
    lights = (
            Dmx7("dmx/plenar/master"),
            Dmx7("dmx/plenar/vorne1"),
            Dmx7("dmx/plenar/vorne2"),
            Dmx7("dmx/plenar/vorne3"),
            Dmx7("dmx/plenar/hinten1"),
            Dmx7("dmx/plenar/hinten2"),
            Dmx7("dmx/plenar/hinten3"),
            Dmx7("dmx/plenar/hinten4")
        )


class Fnordcenter(C4Room):
    """The Fnordcenter."""

    name = "Fnordcenter"
    switches = (
            ("Links (Fairydust)", "licht/fnord/links"),
            ("Rechts (SCUMM)", "licht/fnord/rechts")
        )
    master = Dmx4("dmx/fnord/master")
    lights = (
            Dmx4("dmx/fnord/master"),
            Dmx4("dmx/fnord/scummfenster"),
            Dmx4("dmx/fnord/schranklinks"),
            Dmx4("dmx/fnord/fairyfenster"),
            Dmx4("dmx/fnord/schrankrechts")
        )


class Keller(C4Room):
    """The Keller."""

    name = "Keller"
    switches = (
            ("Außen", "licht/keller/aussen"),
            ("Innen", "licht/keller/innen"),
            ("Vorne", "licht/keller/vorne")
        )
    master = ""
    lights = ()


class Kitchenlight:
    """The Kitchenlight."""

    _END = "little" # Endianess
    _available_modes = """
  off                   turn off
  checker[,DELAY[,COLOR_1[,COLOR_2]]]
                        Checker
  matrix[,LINES]        Matrix
  mood[,MODE] (1=Colorwheel, 2=Random)
                        Moodlight
  oc[,DELAY]            Open Chaos
  pacman                Pacman
  sine                  Sine
  text[,TEXT[,DELAY]]   Text
  flood                 Flood
  clock                 Clock"""

    def __init__(self, topic="kitchenlight/change_screen",
                       powertopic="power/wohnzimmer/kitchenlight",
                       autopower=True):
        self.topic = topic # Kitchenlight topic
        self.powertopic = powertopic # Topic for power on
        self.autopower = autopower # Power on on every mode change?

    def _switch(self, data, poweron=False, poweroff=False):
        """Send commands via a C4Interface to the MQTT broker."""
        if self.autopower or poweron or poweroff:
            c4 = C4Interface(self.topic)
            cmd = []
            cmd.append({
                "topic" : self.topic,
                "payload" : data })
            if poweroff:
                cmd.append({
                    "topic" : self.powertopic,
                    "payload" : bytearray((0,))})
            elif self.autopower or poweron:
                cmd.append({
                    "topic" : self.powertopic,
                    "payload" : bytearray((1,))})
            c4.push(cmd)
        else:
            c4 = C4Interface(self.topic)
            c4.push(data)

    def set_mode(self, mode, opts=[]):
        """Switch to given mode."""
        mode = mode.lower()
        if mode == "off":
            return self.empty()
        if mode == "checker":
            return self.checker(*opts)
        if mode == "matrix":
            return self.matrix(*opts)
        if mode == "mood":
            return self.moodlight(*opts)
        if mode == "oc" or mode == "openchaos":
            return self.openchaos(*opts)
        if mode == "pacman":
            return self.pacman()
        if mode == "sine":
            return self.sine()
        if mode == "text":
            return self.text(*opts)
        if mode == "flood":
            return self.flood()
        if mode == "clock":
            return self.clock()
        print("Error: unknown Kitchenlight mode {}!".format(mode))
        return False

    def empty(self):
        """Set to mode "empty" and turn off Kitchenlight."""
        # Screen 0
        d = int(0).to_bytes(4, self._END)
        self._switch(d, poweroff=True)

    def checker(self, delay=500, colA="0000ff", colB="00ff00"):
        """Set to mode "checker"."""
        # Kind of a hack: lets treat the two colors as DMX lights
        ca = Dmx("checker/a", colA.lstrip('#'))
        cb = Dmx("checker/b", colB.lstrip('#'))
        d = bytearray(20)
        v = memoryview(d)
        # Screen 1
        v[0:4] = int(1).to_bytes(4, self._END)
        # Delay
        v[4:8] = int(delay).to_bytes(4, self._END)
        # ColorA R/G/B
        v[8:10] = int(ca.color[0:2], base=16).to_bytes(2, self._END)
        v[10:12] = int(ca.color[2:4], base=16).to_bytes(2, self._END)
        v[12:14] = int(ca.color[4:6], base=16).to_bytes(2, self._END)
        # ColorB R/G/B
        v[14:16] = int(cb.color[0:2], base=16).to_bytes(2, self._END)
        v[16:18] = int(cb.color[2:4], base=16).to_bytes(2, self._END)
        v[18:20] = int(cb.color[4:6], base=16).to_bytes(2, self._END)
        self._switch(d)

    def matrix(self, lines=8):
        """Set to mode "matrix"."""
        if int(lines) > 31: lines = 31 # Maximal line count
        d = bytearray(8)
        v = memoryview(d)
        # Screen 2
        v[0:4] = int(2).to_bytes(4, self._END)
        v[4:8] = int(lines).to_bytes(4, self._END)
        self._switch(d)

    def moodlight(self, mode=1):
        """Set to mode "moodlight"."""
        if mode == 1: # Mode "Colorwheel"
            d = bytearray(19)
            v = memoryview(d)
            # Screen 3
            v[0:4] = int(3).to_bytes(4, self._END)
            # Mode
            v[4:5] = int(mode).to_bytes(1, self._END)
            # Step
            v[5:9] = int(1).to_bytes(4, self._END)
            # Fade delay
            v[9:13] = int(10).to_bytes(4, self._END)
            # Pause
            v[13:17] = int(10000).to_bytes(4, self._END)
            # Hue step
            v[17:19] = int(30).to_bytes(2, self._END)
        else: # Mode "Random"
            d = bytearray(17)
            v = memoryview(d)
            # Screen 3
            v[0:4] = int(3).to_bytes(4, self._END)
            # Mode
            v[4:5] = int(mode).to_bytes(1, self._END)
            # Step
            v[5:9] = int(1).to_bytes(4, self._END)
            # Fade delay
            v[9:13] = int(10).to_bytes(4, self._END)
            # Pause
            v[13:17] = int(10000).to_bytes(4, self._END)
        self._switch(d)

    def openchaos(self, delay=1000):
        """Set to mode "openchaos"."""
        d = bytearray(8)
        v = memoryview(d)
        # Screen 4
        v[0:4] = int(4).to_bytes(4, self._END)
        v[4:8] = int(delay).to_bytes(4, self._END)
        self._switch(d)

    def pacman(self):
        """Set to mode "pacman"."""
        # Screen 5
        d = int(5).to_bytes(4, self._END)
        self._switch(d)

    def sine(self):
        """Set to mode "sine"."""
        # Screen 6
        d = int(6).to_bytes(4, self._END)
        self._switch(d)

    # Screen 7 is Strobo, which is disabled because it seems to do harm to
    # the Kitchenlight. Evil strobo!

    def text(self, text="Hello World", delay=250):
        """Set to mode "text"."""
        text = text.encode("ascii", "ignore")
        if len(text) > 256: # Maximum text length
            print("Warning: text length must not exceed 256 characters!")
            text = text[:256]
        d = bytearray(8 + len(text) + 1)
        v = memoryview(d)
        # Screen 8
        v[0:4] = int(8).to_bytes(4, self._END)
        v[4:8] = int(delay).to_bytes(4, self._END)
        v[8:8 + len(text)] = text
        v[len(d) - 1:len(d)] = bytes(1)
        self._switch(d)

    def flood(self):
        """Set to mode "flood"."""
        # Screen 9
        d = int(9).to_bytes(4, self._END)
        self._switch(d)

    def clock(self):
        """Set to mode "clock"."""
        # Screen 11
        d = int(11).to_bytes(4, self._END)
        self._switch(d)


class ColorScheme:
    """Abstraction of a colorscheme."""

    # Names of virtual presets
    _virtual_presets = ["off", "random"]

    def __init__(self, autoinit=""):
        self.mapping = {}
        self.single_color = False
        self.return_random_color = False
        self.available = None # List of available presets
        if autoinit:
            # Load or generate preset
            if autoinit[0] == '#':
                return self.from_color(autoinit)
            elif self._expand_preset(autoinit) == "off":
                # Virtual preset: set masters to #000000
                return self.from_color("000000")
            elif self._expand_preset(autoinit) == "random":
                # Virtual preset: return random color on every query
                return self.from_random()
            else:
                # Load preset file
                return self.from_file(autoinit)

    def __bool__(self):
        # Return true if color_for has a chance to present anything useful
        if self.mapping: return True
        if self.single_color: return True
        if self.return_random_color: return True
        else: return False

    def _get_cfg_dir(self, quiet=False, create=False):
        """Returns path of the config dir."""
        import os
        # The name of our config directory
        XDG_NAME = "c4ctrl"

        # Get XDG_CONFIG_DIR from environment or set default
        if "XDG_CONFIG_DIR" in os.environ:
            XDG_CONFIG_DIR = os.environ["XDG_CONFIG_DIR"]
        else:
            XDG_CONFIG_DIR = os.path.expanduser("~/.config")

        # Does our config dir exist?
        cfg_dir = os.path.join(XDG_CONFIG_DIR, XDG_NAME)
        if not os.path.isdir(cfg_dir):
            if create:
                print("Creating config directory \"{}\"".format(cfg_dir))
                os.mkdir(cfg_dir)
            elif quiet:
                return None
            else:
                print("Warning: config dir \"{}\" does not exist!".format(cfg_dir))
                return None

        return cfg_dir

    def _expand_preset(self, preset):
        """Tries to expand given string to a valid preset name."""
        import os
        if not self.available:
            cfg_dir = self._get_cfg_dir(quiet=True)
            if not cfg_dir:
                self.available = self._virtual_presets.copy()
            else:
                self.available = os.listdir(cfg_dir)
                self.available.extend(self._virtual_presets)
        # Search for an exact match first
        for a in self.available:
            if a == preset: return a
        # Return anything which begins with the name given
        for a in self.available:
            if a.find(preset) == 0: return a
        # Fallback
        return preset

    def _topic_is_master(self, topic):
        """Does the given topic look like a master topic?"""
        return topic.lower().rfind("/master") == len(topic)-7 # 7 = len("/master")

    def _random_color(self):
        """Returns a 3*4 bit pseudo random color in 6 char hex notation."""
        from random import randint, sample
        chls = [15]
        chls.append(randint(0,15))
        chls.append(randint(0,15) - chls[1])
        if chls[2] < 0: chls[2] = 0

        color = ""
        for ch in sample(chls, k=3):
            color += hex(ch)[2:]*2
        return color

    def color_for(self, topic):
        """Returns the color (hex) this ColorScheme provides for the given topic."""
        if self.mapping:
            if topic in self.mapping.keys():
                return self.mapping[topic]
        elif self.single_color:
            return self.single_color
        elif self.return_random_color:
            # Returning a value for master would override all other settings
            if self._topic_is_master(topic):
                return None
            else:
                return self._random_color()
        # Fallback
        return None

    def from_file(self, preset):
        """Load ColorScheme from file."""
        if preset == '-':
            fd = sys.stdin
        else:
            import os
            cfg_dir = self._get_cfg_dir()
            if not cfg_dir:
                print("Error: could not load preset!")
                return None

            # Expand preset name
            preset = self._expand_preset(preset)
            # Try to open the preset file
            fn = os.path.join(cfg_dir, preset)
            try:
                fd = open(fn)
            except OSError:
                print("Error: could not load preset \"{}\" (file could not be accessed)!".format(preset))
                return None

        # Parse the preset file
        self.mapping = {}
        self.name = preset
        for line in fd.readlines():
            # Skip every line which does not begin with an alphabetic character
            try:
                if not line.lstrip()[0].isalpha(): continue
            except IndexError: continue # Empty line

            # Strip spaces and split
            k, v = line.replace(' ','').replace('\t','').split('=')
            # Convert #fff to fff and remove trailing comments, nl and cr chars
            vl = v.rstrip("\n\r").split('#')
            v = vl[0] or vl[1]

            # Validate hex code
            for c in v.lower():
                if c not in "0123456789abcdef":
                    print("Error: invalid color code \"{}\" in preset \"{}\"!".format(v, preset))
                    sys.exit(1)
            self.mapping[k] = v

        fd.close()

    def from_color(self, color):
        """Derive ColorScheme from a single hex color."""
        self.single_color = color.lstrip('#')

    def from_random(self):
        """Derive ColorScheme from random colors."""
        self.return_random_color = True

    def list_available(self):
        """List available presets."""
        import os
        cfg_dir = self._get_cfg_dir()
        if not cfg_dir:
            self.available = self._virtual_presets.copy()

        if not self.available:
            self.available = os.listdir(cfg_dir)
            self.available.extend(self._virtual_presets)
        self.available.sort()
        print("Available presets:\n")
        for entry in self.available:
            if entry[0] == '.' or entry[-1:] == '~': continue
            print("  " + entry)

    def store(self, name):
        """Store the current state of all lights as preset."""
        # First of all, refuse to override virtual presets
        if name in self._virtual_presets:
            print("I'm sorry Dave. I'm afraid I can't do that. The name \"{}\" is reserved. Please choose a different one.".format(name))
            return False

        if name == '-':
            fd = sys.stdout
        else:
            import os
            cfg_dir = self._get_cfg_dir(create=True) # Create config dir if missing

            fn = os.path.join(cfg_dir, name)
            try:
                fd = open(fn, 'xt')
            except FileExistsError:
                print("A preset with this name already exists, overwrite? [y/N]",
                        end=' ', flush=True)
                if sys.stdin.read(1).lower() == 'y':
                    fd = open(fn, 'wt')
                else:
                    return False

        # Get current states
        c4 = C4Interface()

        fd.write("# Preset \"{}\" (auto generated)\n".format(name))
        fd.write("# Note: \"/master\" topics override every other topic in the room.\n")
        for room in Wohnzimmer, Plenarsaal, Fnordcenter: 
            topics = []
            for light in room.lights:
                topics.append(light.topic)

            responce = c4.pull(topics)
            fd.write("\n# {}\n".format(room.name))
            for light in room.lights:
                for r in responce:
                    if r.topic == light.topic:
                        light.set_color(r.payload.hex())
                        # Out comment master, as it would override everything else
                        if self._topic_is_master(r.topic):
                            fd.write("#{} = {}\n".format(light.topic, light.color))
                        else:
                            fd.write("{} = {}\n".format(light.topic, light.color))

        if name != '-':
            fd.close()
            print("Wrote preset \"{}\"".format(name))


class Fluffy:
    """Fluffyd functions."""

    modes = {
        "fade" : 1,
        "wave" : 4,
        "emp" : 8
    }

    def mode_id(self, name):
        if name.isdecimal():
            if int(name) in self.modes.values():
                return (int(name), False)
        else:
            if name.lower() in self.modes.keys():
                return (self.modes[name.lower()], False)

        # Fallback
        return (0, True)


class RemotePresets:
    """Remote preset control."""

    def __init__(self):
        self.map = {
            "global" : {
                "name" : "AutoC4",
                "list_topic" : "preset/list",
                "set_topic" : "preset/set",
                "def_topic" : "preset/def"
                },
            "wohnzimmer" : {
                "name" : "Wohnzimmer",
                "list_topic" : "preset/wohnzimmer/list",
                "set_topic" : "preset/wohnzimmer/set",
                "def_topic" : "preset/wohnzimmer/def"
                },
            "plenar" : {
                "name" : "Plenarsaal",
                "list_topic" : "preset/plenar/list",
                "set_topic" : "preset/plenar/set",
                "def_topic" : "preset/plenar/def"
                },
            "fnord" : {
                "name" : "Fnordcenter",
                "list_topic" : "preset/fnord/list",
                "set_topic" : "preset/fnord/set",
                "def_topic" : "preset/fnord/def"
                },
            "keller" : {
                "name" : "Keller",
                "list_topic" : "preset/keller/list",
                "set_topic" : "preset/keller/set",
                "def_topic" : "preset/keller/def"
                }
            }

    def _expand_room_name(self, name):
        """Try to expand partial names."""
        if name in self.map.keys():
            # Return on exact match
            return name

        for room in self.map.keys():
            if room.find(name) == 0:
                return room
        # Fallback
        return name

    def _expand_preset_name(self, name, rooms, available):
        """Try to expand partial preset names.
        
        <rooms> must be a list of rooms to consider.
        <available> must be a dict as returned by query_available()."""
        # We need to take care to match only presets which are available for
        # every room specified

        # Strip every "global" out of the room list. We take special care of
        # "global" later on.
        while "global" in rooms:
            rooms.remove("global")

        matchtable = {}
        if "global" not in rooms:
            for preset in available["global"]:
                # Candidate?
                if preset == name or preset.find(name) == 0:
                    # Presets in "global" are available everywhere
                    matchtable[preset] = len(rooms)

        for room in rooms:
            for preset in available[room]:
                # Candidate? 
                if preset == name or preset.find(name) == 0:
                    if preset in matchtable.keys():
                        matchtable[preset] += 1
                    else:
                        matchtable[preset] = 1

        # First check if there is an exact match in all rooms
        if name in matchtable.keys() and matchtable[name] >= len(rooms):
            return name
        # Return first preset available in all rooms
        for match in matchtable.keys():
            if matchtable[match] >= len(rooms):
                return match
            elif match in available["global"]:
                return match
        # Fallback
        return name

    def query_available(self, rooms=["global"]):
        """Returns a dict of remotely available presets for [rooms]."""
        import json

        # Presets in "global" are available everywhere and should always be included
        if "global" not in rooms:
            rooms.insert(0, "global")

        req = []
        for room in rooms:
            if room not in self.map.keys():
                print("Error: unknown room \"{}\"".format(room))
                return {}

            req.append(self.map[room]["list_topic"])

        c4 = C4Interface()
        responce = c4.pull(req)
        # Make responce iterable
        if type(responce) != list: responce = [responce]

        available = {}
        for room in rooms:
            for r in responce:
                if r.topic == self.map[room]["list_topic"]:
                    available[room] = json.decoder.JSONDecoder().decode(r.payload.decode())

        return available

    def list_available(self, room="global"):
        """Print a list of available Presets."""
        room = self._expand_room_name(room)
        available = self.query_available([room])

        if not available:
            print("No presets available for {}".format(self.map[room]["name"]))
        else:
            print("Available presets for {}:".format(self.map[room]["name"]))
            for r in available.keys():
                for preset in available[r]:
                    print( "  " + preset)

    def apply_preset(self, preset, rooms=["global"]):
        """Apply preset to given rooms."""
        # Strip spaces and expand rooms names
        for i in range(len(rooms)):
            rooms[i] = self._expand_room_name(rooms[i].strip())

        available = self.query_available(rooms.copy())
        # Produce some fake data to prevent KeyErrors if in debug mode
        if C4Interface.debug:
            print("[DEBUG] Warning: handing over fake data to allow further execution!")
            available = {
                "global" : [preset],
                "wohnzimmer" : [preset],
                "plenar" : [preset],
                "fnord" : [preset],
                "keller" : [preset]
            }
        # Expand preset name (stripping spaces)
        preset = self._expand_preset_name(preset, rooms.copy(), available.copy())

        for room in rooms:
            if preset not in available[room] and preset not in available["global"]:
                print("Error: preset \"{}\" not available for room \"{}\"!".format(
                        preset, self.map[room]["name"]))
                return False

        cmd = []
        for room in rooms:
            cmd.append((self.map[room]["set_topic"], preset))

        c4 = C4Interface()
        return c4.push(cmd)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Command line client for AutoC4.")
    parser.add_argument(
        "-d", "--debug", action="store_true",
        help="display what would be send to the MQTT broker, but do not actually connect")
    # Various club functions
    group_fn = parser.add_argument_group(title="various functions")
    group_fn.add_argument(
        "-s", "--status", action="store_true",
        help="display club status")
    group_fn.add_argument(
        "-g", "--gate", action="store_true",
        help="open club gate")
    group_fn.add_argument(
        "-S", "--shutdown", action="count",
        help="shutdown (give twice to force shutdown)")
    # Kitchenlight control
    group_kl = parser.add_argument_group(title="Kitchenlight control")
    group_kl.add_argument(
        "-k", "--kl-mode", type=str, metavar="MODE[,OPTIONS]",
        help="set Kitchenlight to MODE")
    group_kl.add_argument(
        "-i", "--list-kl-modes", action="store_true",
        help="list available Kitchenlight modes and their options")
    # Ambient control
    group_cl = parser.add_argument_group(title="ambient color control",
        description="PRESET may be either a preset name (which may be abbreviated) or '#' followed by a color value in hex notation (eg. \"#ff0066\").")
    group_cl.add_argument(
        "-w", "--wohnzimmer", type=str, dest="w_color", metavar="PRESET",
        help="apply local colorscheme PRESET to Wohnzimmer")
    group_cl.add_argument(
        "-p", "--plenarsaal", type=str, dest="p_color", metavar="PRESET",
        help="apply local colorscheme PRESET to Plenarsaal")
    group_cl.add_argument(
        "-f", "--fnordcenter", type=str, dest="f_color", metavar="PRESET",
        help="apply local colorscheme PRESET to Fnordcenter")
    group_cl.add_argument(
        "-m", "--magic", type=str, default="fade", metavar="MODE",
        help="EXPERIMENTAL: blend into preset (needs a running instance of fluffyd on the network). MODE is either \"fade\", \"wave\", \"emp\" or \"none\".")
    group_cl.add_argument(
        "-l", "--list-presets", action="store_true",
        help="list locally available presets")
    group_cl.add_argument(
        "-o", "--store-preset", type=str, dest="store_as", metavar="NAME",
        help="store current state as preset NAME")
    # Remote presets
    group_rp = parser.add_argument_group(title="remote preset functions",
        description="Available room names are \"wohnzimmer\", \"plenar\", \"fnord\" and \"keller\". Preset and room names may be abbreviated.")
    group_rp.add_argument(
        "-r", "--remote-preset", type=str, metavar="PRESET[:ROOM[,ROOM,...]]",
        help="activate remote PRESET for ROOM(s).")
    group_rp.add_argument(
        "-R", "--list-remote", nargs='?', const="global", metavar="ROOM",
        help="list remote presets for ROOM")
    # Switch control
    group_sw = parser.add_argument_group(title="light switch control",
        description="The optional DIGIT_CODE is a string of 0s or 1s for every light in the room. Works interactively if missing.")
    group_sw.add_argument(
        "-W", nargs='?', dest="w_switch", const="", metavar="DIGIT_CODE",
        help="switch lights in Wohnzimmer on/off")
    group_sw.add_argument(
        "-P", nargs='?', dest="p_switch", const="", metavar="DIGIT_CODE",
        help="switch lights in Plenarsaal on/off")
    group_sw.add_argument(
        "-F", nargs='?', dest="f_switch", const="", metavar="DIGIT_CODE",
        help="switch lights in Fnordcentter on/off")
    group_sw.add_argument(
        "-K", nargs='?', dest="k_switch", const="", metavar="DIGIT_CODE",
        help="switch lights in Keller on/off")
    args = parser.parse_args()

    # Debug, gate, status and shutdown
    if args.debug:
        C4Interface.debug = True
    if args.status:
        C4Interface().status()
    if args.gate:
        C4Interface().open_gate()
    if args.shutdown:
        if args.shutdown >= 2:
            C4Interface().shutdown(force=True)
        else:
            C4Interface().shutdown()

    # Kitchenlight
    if args.list_kl_modes:
        print("Available Kitchenlight modes (options are optional):")
        print(Kitchenlight._available_modes)
    if args.kl_mode:
        kl = Kitchenlight()
        mode = args.kl_mode.split(',')
        if len(mode) == 1:
            kl.set_mode(mode[0])
        else:
            kl.set_mode(mode[0], mode[1:])

    # Colorscheme
    if args.store_as:
        ColorScheme().store(args.store_as)
    if args.w_color:
        preset = ColorScheme(autoinit=args.w_color)
        if preset: Wohnzimmer().set_colorscheme(preset, args.magic)
    if args.p_color:
        preset = ColorScheme(autoinit=args.p_color)
        if preset: Plenarsaal().set_colorscheme(preset, args.magic)
    if args.f_color:
        preset = ColorScheme(autoinit=args.f_color)
        if preset: Fnordcenter().set_colorscheme(preset, args.magic)
    if args.list_presets:
        ColorScheme().list_available()

    # Remote presets
    if args.list_remote:
        RemotePresets().list_available(args.list_remote.lower())
    if args.remote_preset:
        remote_opts = args.remote_preset.split(':')
        if len(remote_opts) == 1:
            RemotePresets().apply_preset(remote_opts[0].strip())
        else:
            RemotePresets().apply_preset(remote_opts[0].strip(),
                    remote_opts[1].lower().split(','))

    # Light switches
    if args.w_switch != None:
        Wohnzimmer().light_switch(args.w_switch)
    if args.p_switch != None:
        Plenarsaal().light_switch(args.p_switch)
    if args.f_switch != None:
        Fnordcenter().light_switch(args.f_switch)
    if args.k_switch != None:
        Keller().light_switch(args.k_switch)

    # No or no useful command line options?
    if len(sys.argv) <= 1 or len(sys.argv) == 2 and args.debug:
        parser.print_help()

