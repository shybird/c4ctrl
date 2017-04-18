#!/usr/bin/env python3
#     ____ __
#    / __// /
#   / /  / /___  ____
#   \ \__\_   / / __/____ __ _
#    \___\ |_| / / |_   _|  \ |
#              \ \__ | ||   / |_
#               \___\|_||_\_\___\
#
# c4ctrl: A command line client for Autoc4.
#
# Author: Shy
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.

"""
A command line client for Autoc4, the home automation system of the C4.

Run 'c4ctrl -h' for usage information.

Dependencies:
    * Paho Python Client
      (available from https://github.com/eclipse/paho.mqtt.python).
    * Some parts will work on UNIX-like operating systems only.
"""

import sys
from random import choice # For client_id generation.


class C4Interface():
    """ Interaction with AutoC4, the C4 home automation system. """

    broker = "autoc4.labor.koeln.ccc.de"
    port = 1883
    qos = 2
    retain = True
    # Generate a (sufficiently) unique client id.
    client_id = "c4ctrl-" + "".join(
        choice("0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
            for unused in range(16))
    debug = False

    def on_permission_error(self, error):
        """ Called when catching a PermissionDenied exception while connecting. """

        print("Error: You don't have permission to connect to the broker.", file=sys.stderr)
        print("Maybe you're not connected to the internal C4 network?", file=sys.stderr)
        print(error, file=sys.stderr)
        sys.exit(1)

    def on_os_error(self, error):
        """ Called when catching a OSError exception while connecting. """

        print("Error: unable to open a network socket.", file=sys.stderr)
        print(error, file=sys.stderr)
        sys.exit(1)

    def push(self, message, topic=None, retain=None):
        """ Send a message to the MQTT broker.

            message may be a byte encoded payload or a list of either dict()s
            or tuples()s. If message is a byte encoded payload, topic= must be
            given. dict()s and tuple()s should look like:
                dict("topic": str(topic), "payload": bytes(payload))
                tuple(str(topic), bytes(payload)) """

        from paho.mqtt import publish

        # Skip empty messages.
        if message == [] or message == "": return

        # Set defaults.
        if retain == None: retain = self.retain

        if type(message) == list:
            # Add <qos> and <retain> to every message.
            for item in message.copy():
                if type(item) == dict:
                    item["qos"] = self.qos
                    item["retain"] = retain
                elif type(item) == tuple:
                    new_item = (
                        item[0] or topic, # topic
                        item[1], # payload
                        self.qos, # qos
                        retain # retain
                        )
                    message.remove(item)
                    message.append(new_item)

            if self.debug: return print("[DEBUG] inhibited messages:",
                message, file=sys.stderr)

            try:
                publish.multiple(message,
                        hostname=self.broker,
                        port=self.port,
                        client_id=self.client_id)

            except PermissionError as error:
               self.on_permission_error(error)

            except OSError as error:
               self.on_os_error(error)

        else: # Message is not a list.
            if self.debug:
                return print("[DEBUG] inhibited message to '{}': '{}'".format(
                        topic, message), file=sys.stderr)

            try:
                publish.single(topic,
                        payload=message,
                        qos=self.qos,
                        retain=retain,
                        hostname=self.broker,
                        port=self.port,
                        client_id=self.client_id)

            except PermissionError as error:
               self.on_permission_error(error)

            except OSError as error:
               self.on_os_error(error)

    def pull(self, topic=[]):
        """ Return the state of a topic.

            topic may be a list of topics or a single topic given as string.
            Returns a paho message object or list of message objects. """

        from paho.mqtt import subscribe

        # Convert topics of type string to a single item list.
        if type(topic) == str:
            topic = [topic]

        # Skip empty queries.
        if topic == []: return

        if self.debug:
            print("[DEBUG] inhibited query for:", topic, file=sys.stderr)
            return []

        try:
            return subscribe.simple(topic,
                    msg_count=len(topic),
                    qos=self.qos,
                    hostname=self.broker,
                    port=self.port,
                    client_id=self.client_id)

        except PermissionError as error:
           self.on_permission_error(error)

        except OSError as error:
           self.on_os_error(error)

    def status(self):
        """ Returns current status (string "open" or "closed") of the club. """

        club_status = self.pull("club/status")

        # Create a fake result to prevent errors if in debug mode.
        if C4Interface.debug:
            print("[DEBUG] Warning: handing over fake data to allow for further execution!",
                file=sys.stderr)
            class club_status: pass
            club_status.payload = b'\x00'

        if club_status.payload == b'\x01':
            return "open"
        else:
            return "closed"

    def open_gate(self):
        """ Open the gate. """

        self.push(None, topic="club/gate", retain=False)

    def shutdown(self, force=False):
        """ Invoke the shutdown routine. """ 

        if force:
            payload = b'\x44'
        else:
            payload = b'\x00'
        self.push(payload, topic="club/shutdown", retain=False)


class Kitchenlight:
    """ Interface to the Kitchenlight and its functions. """

    _END = "little" # Kitchenlight endianess.

    def __init__(self, topic="kitchenlight/change_screen",
                       powertopic="power/wohnzimmer/kitchenlight",
                       autopower=True):
        self.topic = topic # Kitchenlight topic.
        self.powertopic = powertopic # Topic for power on.
        self.autopower = autopower # Power on on every mode change?

    def _switch(self, data, poweron=False, poweroff=False):
        """ Send commands via a C4Interface to the MQTT broker. """

        if self.autopower or poweron or poweroff:
            c4 = C4Interface()
            command = []
            command.append({
                "topic" : self.topic,
                "payload" : data })
            if poweroff:
                command.append({
                    "topic" : self.powertopic,
                    "payload" : b'\x00'})
            elif self.autopower or poweron:
                command.append({
                    "topic" : self.powertopic,
                    "payload" : b'\x01'})
            c4.push(command)
        else:
            c4 = C4Interface()
            c4.push(data, topic=self.topic)

    def list_available(self):
        """ Print a list of available Kitchenlight modes. """

        print("Available Kitchenlight modes (options are optional):")
        print("""
  off                                   turn off Kitchenlight
  checker [DELAY] [COLOR_1] [COLOR_2]   Checker
  matrix [LINES]                        Matrix
  mood [1|2] (1=Colorwheel, 2=Random)   Moodlight
  oc [DELAY]                            Open Chaos
  pacman                                Pacman
  sine                                  Sine
  text [TEXT] [DELAY]                   Text
  flood                                 Flood
  clock                                 Clock""")

    def set_mode(self, mode, opts=[]):
        """ Switch to given mode. """

        mode = mode.lower()
        if mode == "off":
            return self.empty()
        if mode == "checker":
            return self.checker(*opts)
        if mode == "matrix":
            return self.matrix(*opts)
        if mode == "mood":
            return self.moodlight(*opts)
        if mode == "oc":
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
        """ Set to mode "empty" and turn off Kitchenlight. """

        # Screen 0
        d = int(0).to_bytes(4, self._END)
        self._switch(d, poweroff=True)

    def checker(self, delay=500, colA="0000ff", colB="00ff00"):
        """ Set to mode "checker".

            delay = delay in ms (default 500)
            colA = first color (default 0000ff)
            colB = second color (default 00ff00) """

        # Kind of a hack: lets treat the two colors as DMX lights.
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
        """ Set to mode "matrix".

            lines (>0, <32) = number of lines (default 8) """

        if int(lines) > 31: lines = 31 # Maximal line count.
        d = bytearray(8)
        v = memoryview(d)
        # Screen 2
        v[0:4] = int(2).to_bytes(4, self._END)
        v[4:8] = int(lines).to_bytes(4, self._END)
        self._switch(d)

    def moodlight(self, mode=1):
        """ Set to mode "moodlight".

            mode [1|2] = colorwheel(1) or random(2) """

        if mode == 1: # Mode "Colorwheel".
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
        else: # Mode "Random".
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
        """ Set to mode "openchaos".

            delay = delay in milliseconds (default 1000). """

        d = bytearray(8)
        v = memoryview(d)
        # Screen 4
        v[0:4] = int(4).to_bytes(4, self._END)
        v[4:8] = int(delay).to_bytes(4, self._END)
        self._switch(d)

    def pacman(self):
        """ Set to mode "pacman". """

        # Screen 5
        d = int(5).to_bytes(4, self._END)
        self._switch(d)

    def sine(self):
        """ Set to mode "sine". """

        # Screen 6
        d = int(6).to_bytes(4, self._END)
        self._switch(d)

    # Screen 7 is Strobo, which is disabled because it seems to do harm to
    # the Kitchenlight. Evil strobo.

    def text(self, text="Hello World", delay=250):
        """ Set to mode "text".

            text (str < 256 bytes) = text to display (default "Hello World").
            delay = delay in milliseconds (default 250). """

        text = text.encode("ascii", "ignore")
        if len(text) > 255: # Maximum text length.
            print("Warning: text length must not exceed 255 characters!", file=sys.stderr)
            text = text[:255]
        d = bytearray(8 + len(text) + 1)
        v = memoryview(d)
        # Screen 8
        v[0:4] = int(8).to_bytes(4, self._END)
        v[4:8] = int(delay).to_bytes(4, self._END)
        v[8:8 + len(text)] = text
        v[len(d) - 1:len(d)] = bytes(1)
        self._switch(d)

    def flood(self):
        """ Set to mode "flood". """
        # Screen 9
        d = int(9).to_bytes(4, self._END)
        self._switch(d)

    def clock(self):
        """ Set to mode "clock". """
        # Screen 11
        d = int(11).to_bytes(4, self._END)
        self._switch(d)


class Dmx:
    """ Abstraction of the 3 channel LED cans in the club. """

    # 3 bytes for color, one each for red, green and blue.
    template = "000000"

    def __init__(self, topic, color=None):
        self.topic = topic
        self.set_color(color or self.template)
        self.is_master = topic.rfind("/master") == len(topic)-7 # 7 = len("/master").

    def _pad_color(self, color):
        """ Merge hex color values or payloads into the template.

            Expand 4 bit hex code notation (eg. #f0f) and pad with template
            to get a fitting payload for this kind of light. """

        if len(color) > len(self.template):
            # Silently truncate bytes exceeding template length.
            return color[:len(self.template)]

        # Expand 3 char codes and codes of half the required length.
        # Yet, let's presume that a 6-char code is alway meant to be
        # interpreted as a color and should never be expanded.
        if len(color) != 6 and len(color) == 3 or len(color) == (len(self.template) / 2):
            color = "".join(char*2 for char in color)

        if len(color) == len(self.template): # Nothing more to do.
            return color

        # Add padding.
        color = color + self.template[len(color):]
        return color

    def set_color(self, color):
        """ Set color (hex) for this instance.

            The color is then available via its color variable. """

        color = self._pad_color(color)

        self.color = color
        self.payload = bytearray.fromhex(color)


class Dmx4(Dmx):
    """ Abstraction of the 4 channel LED cans in the club. """

    # 3 bytes for color plus 1 byte for brightness.
    template = "000000ff"


class Dmx7(Dmx):
    """ Abstraction of the 7 channel LED cans in the club. """

    # 3 bytes for color, another 3 bytes for special functions and 1 byte
    # for brightness.
    template = "000000000000ff"


class C4Room:
    """ Methods of rooms in the club. """

    def __init__(self):
        self.c4 = C4Interface()
        # get_switch_state() will store its result and a timestamp to reduce
        # requests to the broker.
        self._switch_state = ("", 0.0)

    def _interactive_light_switch(self):
        """ Interactively ask for input.

            Returns str(userinput). Will not write to stdout if sys.stdin is
            no tty. """

        if sys.stdin.isatty():
            print("[{}]".format(self.name))
            print("Please enter 0 or 1 for every light:")
            for level in range(len(self.switches)):
                print((level * '|') + ",- " + self.switches[level][0])

            switch_state = self.get_switch_state()
            print(switch_state) # Present current state.

        try:
            userinput = sys.stdin.readline().rstrip('\n')
        except KeyboardInterrupt:
            print("\rInterrupted by user.")
            return ""

        return userinput

    def get_switch_state(self, max_age=5):
        """ Returns current state of switches as a string of 1s and 0s.

            max_age specifies how old (in seconds) a cached responce from a
            previously done request may be before it is considered outdated. """

        from time import time

        # We store switch states in self._switch_state to reduce requests to
        # the broker. If this variable is neither empty nor too old, use it!
        if self._switch_state[0] != "":
            if time() - self._switch_state[1] <= max_age:
                return self._switch_state[0]

        state = ""
        req = []
        for topic in self.switches:
            req.append(topic[1])
        responce = self.c4.pull(req)

        for sw in self.switches:
            for r in responce:
                if r.topic == sw[1]:
                    state += str(int.from_bytes(r.payload, sys.byteorder))

        if C4Interface.debug:
            print("[DEBUG] Warning: handing over fake data to allow for further execution!",
                file=sys.stderr)
            state = '0' * len(self.switches)

        self._switch_state = (state, time())
        return state

    def light_switch(self, userinput=""):
        """ Switch lamps in a room on or off. """

        if not userinput:
            # Derive user input from stdin.
            userinput = self._interactive_light_switch()
            if userinput == "": return

        # Let's support some geeky binary operations!
        mode = 'n' # n = normal, a = AND, o = OR, x = XOR.
        if not userinput.isdecimal():
            if userinput == '-':
                print(self.get_switch_state())
                return
            elif userinput[0] == '&' and userinput[1:].strip().isdecimal():
                # AND operator, applied later after doing some more validation.
                userinput = userinput[1:].strip()
                mode = 'a'

            elif userinput[0] == '|' and userinput[1:].strip().isdecimal():
                # OR operator, applied later after doing some more validation.
                userinput = userinput[1:].strip()
                mode = 'o'

            elif userinput[0] == '^' and userinput[1:].strip().isdecimal():
                # XOR operator, applied later after doing some more validation.
                userinput = userinput[1:].strip()
                mode = 'x'

            elif (userinput[:2] == ">>" or userinput[:2] == "<<") \
                    and (userinput[2:].strip() == "" or userinput[2:].strip().isdecimal()):
                # Left or right shift
                # How far shall we shift?
                if userinput[2:].strip().isdecimal():
                    shift_by = int(userinput[2:])
                else:
                    shift_by = 1

                # Retrieve the current state of switches.
                switch_state = self.get_switch_state()
                if userinput[:2] == ">>":
                    # Right shift. '[2:]' removes the leading 'b0...'.
                    new_state = bin(int(switch_state, base=2) >> shift_by)[2:]
                else:
                    # Left shift. '[2:]' removes the leading 'b0...'.
                    new_state = bin(int(switch_state, base=2) << shift_by)[2:]
                    # Cut any exceeding leftmost bits.
                    new_state = new_state[-len(self.switches):]
                # Pad with leading zeroes.
                userinput = new_state.rjust(len(self.switches), '0')

            else:
                # Oh no, input contained non-decimal characters which we could
                # not parse. :(
                print("Error: could not parse input!", file=sys.stderr)
                return

        if len(userinput) != len(self.switches):
            # First try to convert from decimal if userinput's length doesn't
            # match.
            if len(bin(int(userinput))) <= len(self.switches)+2:
                # ^ +2 because bin() returns strings like 'b0...'.
                binary = bin(int(userinput))[2:] # Strip leading 'b0'.
                # Pad with leading zeroes.
                userinput = binary.rjust(len(self.switches), '0')
            else:
                print("Error: wrong number of digits (expected {}, got {})!".format(
                        len(self.switches), len(userinput)), file=sys.stderr)
                return False

        # Now that everything special is expanded it's time to check if
        # userinput really consists of 1s and 0s only.
        for digit in userinput:
            if digit not in "01":
                print("Error: invalid digit: " + digit, file=sys.stderr)
                return False

        if mode == 'a': # AND operator.
            switch_state = self.get_switch_state()
            userinput = "".join(map(lambda x, y: str(int(x) & int(y)),
                                    userinput, switch_state))
        elif mode == 'o': # OR operator.
            switch_state = self.get_switch_state()
            userinput = "".join(map(lambda x, y: str(int(x) | int(y)),
                                    userinput, switch_state))
        elif mode == 'x': # XOR operator.
            switch_state = self.get_switch_state()
            userinput = "".join(map(lambda x, y: str(int(x) ^ int(y)),
                                    userinput, switch_state))

        command=[]
        for i in range(len(self.switches)):
            # Skip unchanged switches if we happen to know their state.
            if "switch_state" in dir():
                if switch_state[i] == userinput[i]: continue

            command.append({
                "topic" : self.switches[i][1],
                "payload" : bytes([int(userinput[i])])
            })

        return self.c4.push(command)

    def set_colorscheme(self, colorscheme, magic):
        """ Apply colorscheme to the LED Cans in this room. """

        command = []
        for light in self.lights:
            if colorscheme.get_color_for(light.topic):

                # Update internal state of this Dmx object, so we can query
                # <object>.payload later.
                light.set_color(colorscheme.get_color_for(light.topic))

                if magic:
                    # Send color to ghost instead of the "real" light.
                    # Generate the ghost topic for topic.
                    ghost = "ghosts" + light.topic[light.topic.find('/'):]

                    command.append({
                        "topic" : ghost,
                        "payload" : light.payload
                    })
                else:
                    # Send data to the real lanterns, not fluffyd.
                    command.append({
                        "topic" : light.topic,
                        "payload" : light.payload
                    })

        # Nothing to do. May happen if a preset defines no color for a room.
        if command == []: return

        if magic: # Do not retain "magic" messages.
          return self.c4.push(command, retain=False)
        else:
          return self.c4.push(command)


class Wohnzimmer(C4Room):
    """ Description of the Wohnzimmer. """

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
    """ Description of the Plenarsaal. """

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
    """ Description of the Fnordcenter. """

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
    """ Description of the Keller. """

    name = "Keller"
    switches = (
            ("Außen", "licht/keller/aussen"),
            ("Innen", "licht/keller/innen"),
            ("Vorne", "licht/keller/vorne")
        )
    master = None
    lights = ()


class ColorScheme:
    """ Abstraction of a colorscheme. """

    # Names of virtual presets. These are always listed as available and the
    # user may not save presets under this name.
    _virtual_presets = ["off", "random"]

    def __init__(self, init=""):
        self.mapping = {}
        self.single_color = False
        self.return_random_color = False
        self.available = None # List of available presets.
        if init:
            # Load or generate preset.
            if init[0] == '#':
                return self.from_color(init)
            elif self._expand_preset(init) == "off":
                # Virtual preset: set masters to #000000.
                return self.from_color("000000")
            elif self._expand_preset(init) == "random":
                # Virtual preset: return random color on every query.
                return self.from_random()
            else:
                # Load preset file.
                return self.from_file(init)

    def __bool__(self):
        # Return true if get_color_for has a chance to present anything useful.
        if self.mapping: return True
        if self.single_color: return True
        if self.return_random_color: return True
        else: return False

    def _get_config_dir(self, ignore_missing=False, create=False):
        """ Returns path of the config dir. """

        import os
        # The name of our config directory.
        _NAME = "c4ctrl"

        # Get XDG_CONFIG_HOME from environment or set default.
        if "XDG_CONFIG_HOME" in os.environ:
            XDG_CONFIG_HOME = os.environ["XDG_CONFIG_HOME"]
        else:
            XDG_CONFIG_HOME = os.path.expanduser(os.path.join("~", ".config"))

        # Does our config dir exist?
        config_dir = os.path.join(XDG_CONFIG_HOME, _NAME)
        if not os.path.isdir(config_dir):
            if create:
                print("Creating config directory \"{}\"".format(config_dir))
                os.mkdir(config_dir)
            elif ignore_missing:
                return None
            else:
                print("Warning: config dir \"{}\" does not exist!".format(
                    config_dir), file=sys.stderr)
                return None

        return config_dir

    def _expand_preset(self, preset):
        """ Tries to expand given string to a valid preset name. """
        import os
        if not self.available:
            config_dir = self._get_config_dir(ignore_missing=True)
            if not config_dir:
                self.available = self._virtual_presets.copy()
            else:
                self.available = os.listdir(config_dir)
                self.available.extend(self._virtual_presets)
        # Search for an exact match first.
        for a in self.available:
            if a == preset: return a
        # Return anything which begins with the name given.
        for a in self.available:
            if a.find(preset) == 0: return a
        # Fallback.
        return preset

    def _topic_is_master(self, topic):
        """ Does the given topic look like a master topic? """

        return topic.lower().rfind("/master") == len(topic)-7 # 7 = len("/master").

    def _random_color(self):
        """ Returns a 3*4 bit pseudo random color in 6 char hex notation. """

        from random import randint, sample
        channels = [15]
        channels.append(randint(0,15))
        channels.append(randint(0,15) - channels[1])
        if channels[2] < 0: channels[2] = 0

        color = ""
        for ch in sample(channels, k=3):
            color += hex(ch)[2:]*2
        return color

    def get_color_for(self, topic):
        """ Returns color for topic.

            Returns the color (in hexadecimal notation) this ColorScheme
            associates with for the given topic. """

        if self.mapping:
            if topic in self.mapping.keys():
                return self.mapping[topic]
        elif self.single_color:
            if not self._topic_is_master(topic):
                return self.single_color
        elif self.return_random_color:
            # We need to take care not to return colors for both "normal" and
            # master topics.
            if not self._topic_is_master(topic):
                return self._random_color()
        # Fallback.
        return None

    def from_file(self, preset):
        """ Load ColorScheme from file. """

        if preset == '-':
            fd = sys.stdin
        else:
            import os
            config_dir = self._get_config_dir()
            if not config_dir:
                print("Error: could not load preset!")
                return

            # Expand preset name.
            preset = self._expand_preset(preset)
            # Try to open the preset file.
            fn = os.path.join(config_dir, preset)
            try:
                fd = open(fn)
            except OSError:
                print("Error: could not load preset \"{}\" (file could not be accessed)!".format(preset))
                return

        # Parse the preset file.
        self.mapping = {}
        self.name = preset
        for line in fd.readlines():
            # Skip every line which does not begin with an alphabetic character.
            try:
                if not line.lstrip()[0].isalpha(): continue
            except IndexError: continue # Empty line.

            # Strip spaces and split.
            k, v = line.replace(' ','').replace('\t','').split('=')
            # Convert #fff to fff and remove trailing comments, nl and cr chars.
            vl = v.rstrip("\n\r").split('#')
            v = vl[0] or vl[1]

            # Validate hex code.
            for c in v.lower():
                if c not in "0123456789abcdef":
                    print("Error: invalid color code \"{}\" in preset \"{}\"!".format(v, preset), file=sys.stderr)
                    sys.exit(1)
            self.mapping[k] = v

        fd.close()

    def from_color(self, color):
        """ Derive ColorScheme from a single hex color. """

        self.single_color = color.lstrip('#')

    def from_random(self):
        """ Derive ColorScheme from random colors. """

        self.return_random_color = True

    def list_available(self):
        """ List available presets. """

        import os

        config_dir = self._get_config_dir()
        if not config_dir:
            self.available = self._virtual_presets.copy()

        if not self.available:
            self.available = os.listdir(config_dir)
            self.available.extend(self._virtual_presets)
        self.available.sort()
        print("Available presets:\n")
        for entry in self.available:
            if entry[0] == '.' or entry[-1:] == '~': continue
            print("  " + entry)

    def store(self, name):
        """ Store the current state of all lights as preset. """

        # Refuse to save under a name used by virtual presets. Let's also
        # refuse to save as "config" or "c4ctrl.conf", as we may use one these
        # file names in the future.
        if name in self._virtual_presets or name in ["config", "c4ctrl.conf"]:
            print("I'm sorry Dave. I'm afraid I can't do that. The name \"{}\" \
is reserved. Please choose a different one.".format(name))
            return False

        if name == '-':
            fd = sys.stdout
        else:
            import os

            # Put preset in our config directory, create it if necessary.
            config_dir = self._get_config_dir(create=True)
            # Strip any path elements.
            name = os.path.split(name)[1]
            fn = os.path.join(config_dir, name)

            try:
                fd = open(fn, 'xt') # x = new file (writing), t = text mode.
            except FileExistsError:
                print("A preset with this name already exists, overwrite? [y/N]",
                        end=' ', flush=True)
                if sys.stdin.read(1).lower() == 'y':
                    fd = open(fn, 'wt')
                else:
                    return False

        # Get current states.
        c4 = C4Interface()

        if name == '-':
            fd.write("# c4ctrl preset (auto generated)\n".format(name))
        else:
            fd.write("# c4ctrl preset \"{}\" (auto generated)\n".format(name))
        fd.write("#\n")
        fd.write("# Note: Topics ending with \"/master\" override all other topics in a room.\n")
        fd.write("#       All spaces will be stripped and lines beginning with \'#\' ignored.\n")
        for room in Wohnzimmer, Plenarsaal, Fnordcenter: 
            topics = []
            max_topic_len = 0

            for light in room.lights:
                topics.append(light.topic)
                if len(light.topic) > max_topic_len:
                    max_topic_len = len(light.topic)

            responce = c4.pull(topics)
            fd.write("\n# {}\n".format(room.name))
            for light in room.lights:
                for r in responce:
                    if r.topic == light.topic:
                        light.set_color(r.payload.hex())
                        # Format payload more nicely.
                        color = light.color
                        if len(color) > 6:
                            color = color[:6] + ' ' + color[6:]
                        topic = light.topic.ljust(max_topic_len)
                        # Out comment master, as it would override everything else.
                        if self._topic_is_master(r.topic):
                            fd.write("#{} = {}\n".format(topic, color))
                        else:
                            fd.write("{} = {}\n".format(topic, color))

        # Do not close stdout.
        if name != '-':
            fd.close()
            print("Wrote preset \"{}\"".format(name))


class RemotePresets:
    """ Remote preset control. """

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
        """ Returns a valid room name expanded from the given name. """

        if name in self.map.keys():
            # Return on exact match.
            return name

        for room in self.map.keys():
            if room.find(name) == 0:
                return room
        # Fallback.
        return name

    def _expand_preset_name(self, name, rooms, available):
        """ Returns a valid preset name expanded from the given name.

            Takes care to match only presets which are available for all rooms
            specified.

            rooms is a list of rooms for which the preset should be a valid
            option.
            available is a dict containing valid presets for rooms as returned
            by query_available(). """

        # Strip every "global" out of the room list. We take special care of
        # "global" later on.
        while "global" in rooms:
            rooms.remove("global")

        matchtable = {}
        if "global" not in rooms:
            for preset in available["global"]:
                # Candidate?
                if preset == name or preset.find(name) == 0:
                    # Presets in "global" are available everywhere.
                    matchtable[preset] = len(rooms)

        for room in rooms:
            for preset in available[room]:
                # Candidate?
                if preset == name or preset.find(name) == 0:
                    if preset in matchtable.keys():
                        matchtable[preset] += 1
                    else:
                        matchtable[preset] = 1

        # First check if there is an exact match in all rooms.
        if name in matchtable.keys() and matchtable[name] >= len(rooms):
            return name
        # Return first preset available in all rooms.
        for match in matchtable.keys():
            if matchtable[match] >= len(rooms):
                return match
            elif match in available["global"]:
                return match
        # Fallback.
        return name

    def query_available(self, rooms=["global"]):
        """ Returns a dict of remotely available presets for [rooms]. """

        import json

        # Presets in "global" are available everywhere and should always be included.
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
        # Make responce iterable.
        if type(responce) != list: responce = [responce]

        available = {}
        for room in rooms:
            for r in responce:
                if r.topic == self.map[room]["list_topic"]:
                    available[room] = json.decoder.JSONDecoder().decode(r.payload.decode())

        return available

    def list_available(self, room="global"):
        """ Print a list of available Presets. """

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
        """ Apply preset to given rooms. """

        # Strip spaces and expand rooms names.
        for i in range(len(rooms)):
            rooms[i] = self._expand_room_name(rooms[i].strip())

        available = self.query_available(rooms.copy())
        # Produce some fake data to prevent KeyErrors if in debug mode.
        if C4Interface.debug:
            print("[DEBUG] Warning: handing over fake data to allow for further execution!",
                file=sys.stderr)
            available = {
                "global" : [preset],
                "wohnzimmer" : [preset],
                "plenar" : [preset],
                "fnord" : [preset],
                "keller" : [preset]
            }
        # Expand preset name (stripping spaces).
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
        help="display what would be send to the MQTT broker, but do not \
        actually connect")

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
        "-k", "--kl-mode", nargs='+', type=str, metavar=("MODE", "OPTIONS"),
        help="set Kitchenlight to MODE")
    group_kl.add_argument(
        "-i", "--list-kl-modes", action="store_true",
        help="list available Kitchenlight modes and their options")

    # Ambient control
    group_cl = parser.add_argument_group(title="ambient color control",
        description="PRESET may be either a preset name (which may be \
        abbreviated), '#' followed by a color value in hex notation (e.g. \
        \"#ff0066\") or '-' to read from stdin.")
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
        "-m", "--magic", action="store_true",
        help="EXPERIMENTAL: use fluffyd to change colors")
    group_cl.add_argument(
        "-l", "--list-presets", action="store_true",
        help="list locally available presets")
    group_cl.add_argument(
        "-o", "--store-preset", type=str, dest="store_as", metavar="NAME",
        help="store current state as preset NAME ('-' to write to stdout)")

    # Switch control
    group_sw = parser.add_argument_group(title="light switch control",
        description="BINARY_CODE is a string of 0s or 1s for every light in a \
        room. May be given as decimal. May be prepended by '&', '|' or '^' as \
        AND, OR and XOR operators. Current switch states will be printed to \
        stdout if BINARY_CODE is '-'. Will show usage information and ask for \
        input if BINARY_CODE is omitted. Will read from stdin if BINARY_CODE \
        is omitted and stdin is not connected to a TTY.")
    group_sw.add_argument(
        "-W", nargs='?', dest="w_switch", const="", metavar="BINARY_CODE",
        help="switch lights in Wohnzimmer on/off")
    group_sw.add_argument(
        "-P", nargs='?', dest="p_switch", const="", metavar="BINARY_CODE",
        help="switch lights in Plenarsaal on/off")
    group_sw.add_argument(
        "-F", nargs='?', dest="f_switch", const="", metavar="BINARY_CODE",
        help="switch lights in Fnordcentter on/off")
    group_sw.add_argument(
        "-K", nargs='?', dest="k_switch", const="", metavar="BINARY_CODE",
        help="switch lights in Keller on/off")

    # Remote presets
    group_rp = parser.add_argument_group(title="remote preset functions",
        description="Available room names are \"wohnzimmer\", \"plenar\", \
        \"fnord\" and \"keller\". Preset and room names may be abbreviated.")
    group_rp.add_argument(
        "-r", "--remote-preset", nargs='+', type=str, metavar=("PRESET", "ROOM"),
        help="activate remote PRESET for ROOM(s). Activates preset globally \
        if ROOM is omitted.")
    group_rp.add_argument(
        "-R", "--list-remote", nargs='?', const="global", metavar="ROOM",
        help="list remote presets for ROOM. Will list global presets if ROOM \
        is omitted.")
    args = parser.parse_args()

    # Debug, gate, status and shutdown.
    if args.debug:
        C4Interface.debug = True
    if args.status:
        status = C4Interface().status()
        print("Club is", status)
    if args.gate:
        C4Interface().open_gate()
    if args.shutdown:
        if args.shutdown >= 2:
            C4Interface().shutdown(force=True)
        else:
            C4Interface().shutdown()

    # Kitchenlight
    if args.list_kl_modes:
        Kitchenlight().list_available()
    if args.kl_mode:
        kl = Kitchenlight()
        if len(args.kl_mode) == 1:
            kl.set_mode(args.kl_mode[0])
        else:
            kl.set_mode(args.kl_mode[0], args.kl_mode[1:])

    # Colorscheme
    if args.store_as:
        ColorScheme().store(args.store_as)
    presets = {} # Store and reuse initialized presets.
    if args.w_color:
        if args.w_color not in presets:
            presets[args.w_color] = ColorScheme(args.w_color)
        if presets[args.w_color]: Wohnzimmer().set_colorscheme(presets[args.w_color], args.magic)
    if args.p_color:
        if args.p_color not in presets:
            presets[args.p_color] = ColorScheme(args.p_color)
        if presets[args.p_color]: Plenarsaal().set_colorscheme(presets[args.p_color], args.magic)
    if args.f_color:
        if args.f_color not in presets:
            presets[args.f_color] = ColorScheme(args.f_color)
        if presets[args.f_color]: Fnordcenter().set_colorscheme(presets[args.f_color], args.magic)
    if args.list_presets:
        ColorScheme().list_available()

    # Light switches
    if args.w_switch != None:
        Wohnzimmer().light_switch(args.w_switch)
    if args.p_switch != None:
        Plenarsaal().light_switch(args.p_switch)
    if args.f_switch != None:
        Fnordcenter().light_switch(args.f_switch)
    if args.k_switch != None:
        Keller().light_switch(args.k_switch)

    # Remote presets
    if args.list_remote:
        RemotePresets().list_available(args.list_remote.lower())
    if args.remote_preset:
        if len(args.remote_preset) == 1:
            RemotePresets().apply_preset(args.remote_preset[0].strip())
        else:
            RemotePresets().apply_preset(args.remote_preset[0].strip(),
                                         args.remote_preset[1:])

    # No or no useful command line options?
    if len(sys.argv) <= 1 or len(sys.argv) == 2 and args.debug:
        parser.print_help()

