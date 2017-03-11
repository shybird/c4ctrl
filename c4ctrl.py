#!/bin/python
#
# c4ctrl: Command line client for AutoC4

import sys
sys.path.append("/home/shy/build/paho.mqtt.python/src")

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

    def update(self, cmd, topic=None):
        """Send cmd to topic via the MQTT broker."""
        from paho.mqtt import publish

        # Overwrite default topic
        if topic: self.topic = topic

        if type(cmd) == list:
            # Add <qos> and <retain> to every message
            for item in cmd:
                if type(item) == dict:
                    item["qos"] = self.qos
                    item["retain"] = self.retain

            if self.debug: return print("[DEBUG] inhibited message:", cmd)

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

    def fetch(self, topic=[]):
        """Return curent state of topic."""
        from paho.mqtt import subscribe
        if self.debug:
            print("[DEBUG] inhibited query for:", topic)
            return []

        # <topic> must be a list
        if type(topic) == str:
            topic = [topic]
        return subscribe.simple(topic,
                msg_count=len(topic),
                qos=self.qos,
                hostname=self.broker,
                port=self.port)

    def status(self):
        """Print current status (open or closed) of C4."""
        st = self.fetch("club/status")
        if st.payload == b'\x01':
            print("Club is open")
        else:
            print("Club is closed")

    def open_gate(self):
        """Open the gate."""
        self.update(cmd=b'\x01', topic="club/gate")

    def shutdown(self, force=False):
        """Invoke the shutdown routine.""" 
        if force:
            payload = b'\x44'
        else:
            payload = b'\x00'
        self.update(cmd=payload, topic="club/shutdown")


class Dmx:
    """Abstraction of the 3 Channel LED Cans in the Club."""

    def __init__(self, topic, color=None):
        self.topic = topic
        if color:
            self.set_color(color)
        else:
            self.color = None

    def __repr__(self):
        return self.topic + " : " + str(self.color)

    def _pad_color(self, color, template):
        """Merge hex color value into hex template."""
        # Expand shorthand hex codes (eg. #f0f) and pad with template
        if len(color) > len(template): # Truncate
            print("Warning: truncating color value {} to {}".format(
                color, color[:len(template)]))
            return color[:len(template)]

        # Expand 3 char codes and codes of half the required length.
        # Yet, lets presume that a 6-char code should never be expanded.
        if len(color) != 6 and len(color) == 3 or len(color) == (len(template) / 2):
            expanded = ""
            for c in color:
                expanded += c*2
            color = expanded

        if len(color) == len(template): # Nothing to do
            return color

        # Add padding
        color = color + template[-(len(template) - len(color)):]
        return color

    def set_color(self, color):
        """Set color (hex) for this instance.
        The color is then available via the color variable."""

        if not color:
            self.color = None
            return
        color = self._pad_color(color, "000000")
        self.color = color
        self.payload = bytearray.fromhex(color)

    def color_from_array(self, ba):
        """Set color (bytearray) for thes instance.

        The color is then available via the color variable."""
        self.set_color(ba.hex())


class Dmx5(Dmx):
    """Abstraction of the 5 Channel LED Cans in the Club."""

    def set_color(self, color):
        color = self._pad_color(color, "000000ff")
        self.color = color
        self.payload = bytearray.fromhex(color)


class Dmx7(Dmx):
    """Abstraction of the 7 Channel LED Cans in the Club."""

    def set_color(self, color):
        color = self._pad_color(color, "000000000000ff")
        self.color = color
        self.payload = bytearray.fromhex(color)


class C4Room:
    """Base class for Club rooms."""

    def interactive_switchctrl(self, userinput="NULL"):
        """Switch lamps in this rooms on and off."""
        import sys
        c4 = C4Interface()

        if userinput == "NULL":
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
            responce = c4.fetch(req)
            for sw in self.switches:
                for r in responce:
                    if r.topic == sw[1]:
                        state = state + str(int.from_bytes(r.payload,
                                byteorder="little"))
            print(state)

            try:
                userinput = sys.stdin.readline().rstrip('\n')
            except KeyboardInterrupt:
                print("\rInterrupted by user.")
                return False

        if len(userinput) != len(self.switches):
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
        return c4.update(cmd)

    def set_colorscheme(self, colorscheme):
        """Apply colorscheme to the LED Cans in this room."""
        cmd = []
        # Todo: this stuff would make sense when the Sink Light would be slave
        # to a master
        #if colorscheme.single_color:
        #    # Setting only master is more efficient here
        #    if colorscheme.color_for(self.master):
        #        self.master.set_color(colorscheme.color_for(self.master))
        #        cmd.append({
        #            "topic" : self.master.topic,
        #            "payload" : self.master.payload
        #        })
        #else:
        # Iterate over every light (including master!)
        for light in self.lights:
            if colorscheme.color_for(light.topic):
                light.set_color(colorscheme.color_for(light.topic))
                cmd.append({
                    "topic" : light.topic,
                    "payload" : light.payload
                })

        c4 = C4Interface()
        return c4.update(cmd)


class Wohnzimmer(C4Room):
    """The Wohnzimmer."""

    name = "Wohnzimmer"
    switches = [
            ("Tür", "licht/wohnzimmer/tuer"),
            ("Mitte", "licht/wohnzimmer/mitte"),
            ("Flur", "licht/wohnzimmer/gang"),
            ("Küche", "licht/wohnzimmer/kueche")
        ]
    master = Dmx7("dmx/wohnzimmer/master")
    lights = [
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
        ]


class Plenarsaal(C4Room):
    """The Plenarsaal."""

    name = "Plenarsaal"
    switches = [
            ("Vorne/Wand", "licht/plenar/vornewand"),
            ("Vorne/Fenster", "licht/plenar/vornefenster"),
            ("Hinten/Wand", "licht/plenar/hintenwand"),
            ("Hinten/Fenster", "licht/plenar/hintenfenster")
        ]
    master = Dmx7("dmx/plenar/master")
    lights = [
            Dmx7("dmx/plenar/master"),
            Dmx7("dmx/plenar/vorne1"),
            Dmx7("dmx/plenar/vorne2"),
            Dmx7("dmx/plenar/vorne3"),
            Dmx7("dmx/plenar/hinten1"),
            Dmx7("dmx/plenar/hinten2"),
            Dmx7("dmx/plenar/hinten3"),
            Dmx7("dmx/plenar/hinten4")
        ]


class Fnordcenter(C4Room):
    """The Fnordcenter."""

    name = "Fnordcenter"
    switches = [
            ("Links (Fairydust)", "licht/fnord/links"),
            ("Rechts (SCUMM)", "licht/fnord/rechts")
        ]
    master = Dmx5("dmx/fnord/master")
    lights = [
            Dmx5("dmx/fnord/master"),
            Dmx5("dmx/fnord/scummfenster"),
            Dmx5("dmx/fnord/schranklinks"),
            Dmx5("dmx/fnord/fairyfenster"),
            Dmx5("dmx/fnord/schrankrechts")
        ]


class Keller(C4Room):
    """The Keller."""

    name = "Keller"
    switches = [
            ("Außen", "licht/keller/aussen"),
            ("Innen", "licht/keller/innen"),
            ("Vorne", "licht/keller/vorne")
        ]
    master = ""
    lights = []


class Kitchenlight:
    """The Kitchenlight."""

    _available_modes = """
  off                   disable
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
            c4.update(cmd)
        else:
            c4 = C4Interface(self.topic)
            c4.update(data)

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
        # Evil strobo harms the Kitchenlight
        #if mode == "strobo":
        #    return self.strobo()
        if mode == "text":
            return self.text(*opts)
        if mode == "flood":
            return self.flood()
        if mode == "clock":
            return self.clock()
        print('Error: unknown mode "' + mode + '"!')
        return False

    def empty(self):
        """Set to mode "empty" and turn off Kitchenlight."""
        # Screen 0
        d = int(0).to_bytes(4, "little")
        self._switch(d, poweroff=True)

    def checker(self, delay=500, colA="0000ff", colB="00ff00"):
        """Set to mode "checker"."""
        # Kind of a hack: lets treat the two colors as DMX lights
        ca = Dmx("checker/a", colA.lstrip('#'))
        cb = Dmx("checker/b", colB.lstrip('#'))
        d = bytearray(20)
        v = memoryview(d)
        # Screen 1
        v[0:4] = int(1).to_bytes(4, "little")
        # Delay
        v[4:8] = int(delay).to_bytes(4, "little")
        # ColorA R/G/B
        v[8:10] = int(ca.color[0:2], base=16).to_bytes(2, "little")
        v[10:12] = int(ca.color[2:4], base=16).to_bytes(2, "little")
        v[12:14] = int(ca.color[4:6], base=16).to_bytes(2, "little")
        # ColorB R/G/B
        v[14:16] = int(cb.color[0:2], base=16).to_bytes(2, "little")
        v[16:18] = int(cb.color[2:4], base=16).to_bytes(2, "little")
        v[18:20] = int(cb.color[4:6], base=16).to_bytes(2, "little")
        self._switch(d)

    def matrix(self, lines=8):
        """Set to mode "matrix"."""
        d = bytearray(8)
        v = memoryview(d)
        # Screen 2
        v[0:4] = int(2).to_bytes(4, "little")
        v[4:8] = int(lines).to_bytes(4, "little")
        self._switch(d)

    def moodlight(self, mode=1):
        """Set to mode "moodlight"."""
        if mode == 1: # Mode "Colorwheel"
            d = bytearray(19)
            v = memoryview(d)
            # Screen 3
            v[0:4] = int(3).to_bytes(4, "little")
            # Mode
            v[4:5] = int(mode).to_bytes(1, "little")
            # Step
            v[5:9] = int(1).to_bytes(4, "little")
            # Fade delay
            v[9:13] = int(10).to_bytes(4, "little")
            # Pause
            v[13:17] = int(10000).to_bytes(4, "little")
            # Hue step
            v[17:19] = int(30).to_bytes(2, "little")
        else: # Mode "Random"
            d = bytearray(17)
            v = memoryview(d)
            # Screen 3
            v[0:4] = int(3).to_bytes(4, "little")
            # Mode
            v[4:5] = int(mode).to_bytes(1, "little")
            # Step
            v[5:9] = int(1).to_bytes(4, "little")
            # Fade delay
            v[9:13] = int(10).to_bytes(4, "little")
            # Pause
            v[13:17] = int(10000).to_bytes(4, "little")
        self._switch(d)

    def openchaos(self, delay=4000):
        """Set to mode "openchaos"."""
        d = bytearray(8)
        v = memoryview(d)
        # Screen 4
        v[0:4] = int(4).to_bytes(4, "little")
        v[4:8] = int(delay).to_bytes(4, "little")
        self._switch(d)

    def pacman(self):
        """Set to mode "pacman"."""
        # Screen 5
        d = int(5).to_bytes(4, "little")
        self._switch(d)

    def sine(self):
        """Set to mode "sine"."""
        # Screen 6
        d = int(6).to_bytes(4, "little")
        self._switch(d)

    # Screen 7 is Strobo, which is disabled because it seems to do harm to
    # the Kitchenlight. Evil strobo!

    def text(self, text="Hello World", delay=200):
        """Set to mode "text"."""
        d = bytearray(8 + len(text) + 1)
        v = memoryview(d)
        # Screen 8
        v[0:4] = int(8).to_bytes(4, "little")
        v[4:8] = int(delay).to_bytes(4, "little")
        for i in range(len(text)):
            v[i+8:i+9] = int(ord(text[i])).to_bytes(1, "little")
        v[len(d)-1:len(d)] = bytes(1)
        self._switch(d)

    def flood(self):
        """Set to mode "flood"."""
        # Screen 9
        d = int(9).to_bytes(4, "little")
        self._switch(d)

    def clock(self):
        """Set to mode "clock"."""
        # Screen 11
        d = int(11).to_bytes(4, "little")
        self._switch(d)


class ColorScheme:
    """Abstraction of a colorscheme."""

    # Virtual presets
    _virtual_presets = ["off", "random"]

    def __init__(self, autoinit=""):
        self.mapping = {}
        self.single_color = False
        self.return_random_color = False
        self.available = None # List of available presets
        if autoinit:
            # Load or generate preset
            if autoinit[0] == '#':
                if '/' in autoinit:
                    return self.from_color(autoinit.split('/'))
                else:
                    return self.from_color(autoinit)
            elif self._expand_preset(autoinit) == "off":
                # Special case. Sets masters to #000000
                return self.from_color("000000")
            elif self._expand_preset(autoinit) == "random":
                return self.from_random()
            else:
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
        """Returns a random 6 char hex color."""
        from random import randint
        color = ""
        for i in range(6):
            # Dont return smaller values than 11
            color = color + hex(randint(1, 15))[2:]
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
            if self._topic_is_master(topic): # 7 = len("/master")
                return None
            else:
                return self._random_color()
        else:
            return None

    def from_file(self, preset):
        """Load ColorScheme from file."""
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
        print("Available presets:")
        for entry in self.available:
            if entry[0] == '.' or entry[-1:] == '~': continue
            print(entry)
        print("PRESET may also be a color in hex notation (eg. #f06 or #ff0066).")

    def store(self, name):
        """Store the current state of all lights as preset."""
        # First of all, refuse to override virtual presets
        if name in self._virtual_presets:
            print("I'm sorry Dave. I'm afraid I can't do that. The name \"{}\" is reserved. Please choose a different one.".format(name))
            return False

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
        fd.write("# Thus, they have been commented out.\n")
        for room in Wohnzimmer, Plenarsaal, Fnordcenter: 
            topics = []
            for light in room.lights:
                topics.append(light.topic)

            responce = c4.fetch(topics)
            fd.write("\n# {}\n".format(room.name))
            for light in room.lights:
                for r in responce:
                    if r.topic == light.topic:
                        light.color_from_array(r.payload)
                        # Out comment master, as it would overre everything else
                        if self._topic_is_master(r.topic):
                            fd.write("#{} = {}\n".format(light.topic, light.color))
                        else:
                            fd.write("{} = {}\n".format(light.topic, light.color))

        fd.close()
        print("Wrote preset \"{}\"".format(name))


if __name__ == "__main__":
    import sys
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
        "-l", "--kl-list", action="store_true",
        help="list available Kitchenlight modes")
    # Ambient control
    group_cl = parser.add_argument_group(title="ambient color control")
    group_cl.add_argument(
        "-w", "--wohnzimmer", type=str, dest="w_color", metavar="PRESET",
        help="apply colorscheme PRESET to Wohnzimmer")
    group_cl.add_argument(
        "-p", "--plenarsaal", type=str, dest="p_color", metavar="PRESET",
        help="apply colorscheme PRESET to Plenarsaal")
    group_cl.add_argument(
        "-f", "--fnordcenter", type=str, dest="f_color", metavar="PRESET",
        help="apply colorscheme PRESET to Fnordcenter")
    group_cl.add_argument(
        "-i", "--list-presets", action="store_true",
        help="list available presets")
    group_cl.add_argument(
        "-o", "--store-preset", type=str, dest="store_as", metavar="NAME",
        help="store current state as preset NAME")
    # Switch control
    group_sw = parser.add_argument_group(title="light switch control",
        description="The optional [DIGIT_CODE] is a string of 0s or 1s for every light in the room. Works interactivly if missing.")
    group_sw.add_argument(
        "-W", nargs='?', dest="w_switch", const="NULL", metavar="DIGIT_CODE",
        help="switch lights in Wohnzimmer on/off")
    group_sw.add_argument(
        "-P", nargs='?', dest="p_switch", const="NULL", metavar="DIGIT_CODE",
        help="switch lights in Plenarsaal on/off")
    group_sw.add_argument(
        "-F", nargs='?', dest="f_switch", const="NULL", metavar="DIGIT_CODE",
        help="switch lights in Fnordcentter on/off")
    group_sw.add_argument(
        "-K", nargs='?', dest="k_switch", const="NULL", metavar="DIGIT_CODE",
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
    if args.kl_list:
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
        if preset: Wohnzimmer().set_colorscheme(preset)
    if args.p_color:
        preset = ColorScheme(autoinit=args.p_color)
        if preset: Plenarsaal().set_colorscheme(preset)
    if args.f_color:
        preset = ColorScheme(autoinit=args.f_color)
        if preset: Fnordcenter().set_colorscheme(preset)
    if args.list_presets:
        ColorScheme().list_available()

    # Light switches
    if args.w_switch:
        Wohnzimmer().interactive_switchctrl(args.w_switch)
    if args.p_switch:
        Plenarsaal().interactive_switchctrl(args.p_switch)
    if args.f_switch:
        Fnordcenter().interactive_switchctrl(args.f_switch)
    if args.k_switch:
        Keller().interactive_switchctrl(args.k_switch)

    # No command line options or only debug?
    if len(sys.argv) <= 1 or len(sys.argv) == 2 and args.debug:
        parser.print_help()

