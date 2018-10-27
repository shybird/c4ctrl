# c4ctrl
Command line client and utilities for AutoC4.

This repository consists of:
* *c4ctrl.py* - the command line client and python module
* *kitchentext* - a python script to display multiple lines of text on the Kitchenlight
* *c4ctrl.vim* - a plugin for the vim text editor
* *_c4ctrl* - command line completion file for zsh

### Dependencies
* Python 3.?: [[https://www.python.org/]]
* Paho Python Module: [[https://github.com/eclipse/paho.mqtt.python]]

### Installation
Install the *Paho Python Module* somewehere into *$PYTHONPATH* or run
*c4ctrl.py* with a modified *$PYTHONPATH* variable. Another way to run
*c4ctrl.py* without installing the Paho Module system-wide is to add the
following line of code at the start of *c4ctrl.py*, right after
*import sys*, and modify it to match your setup:
```
sys.path.append("/home/somepony/somedir/paho.mqtt.python/src")
```

You may want to create symbolic links to *c4ctrl.py* and *kitchentext* in a
directory in your *$PATH*. For example:
```
$ ln -s /home/somepony/somedir/c4ctrl/c4ctrl.py /home/somepony/bin/c4ctrl
$ ln -s /home/somepony/somedir/c4ctrl/kitchentext /home/somepony/bin/kitchentext
```

### Usage
Please run *c4ctrl.py* with the *-h* or *--help* flag to display all available
options.
```
$ c4ctrl.py -h
```

#### Usage example: switching lights
The best way to get used to the light switch control syntax is by giving either
the *-W*, *-P*, *-F* or *-K* flag without argument. This will display what bit
corresponds to which light. The string of 0s and 1s shows the current state of
every light in the room.
```
$ c4ctrl -W        
```
```
[Wohnzimmer]
Please enter 0 or 1 for every light:
,- Tür
|,- Mitte
||,- Flur
|||,- Küche
1011
```
Example input values:
* *0011*: sets every light to the given state
* *3* (Decimal representation of *0011*): same as the above
* *^2* or *^0010* (XOR operand): toggle light "Flur"
* *|9* or *|1001* (OR operand): turn on light "Tür" and "Küche"
* *&1* or *&0001* (AND operand): turn off every light but "Küche"

These values may be given directly on the command line:
```
$ c4ctrl -W ^2
```
NOTE: Remember to escape *|* and *&* characters when giving them on the command
line!

### Preset file location
*c4ctrl* searches for preset files in the directory *$XDG_CONFIG_HOME/c4ctrl/*,
defaulting to *$HOME/.config/c4ctrl/*. If you use the *-o* flag and this
directory does not exist, *c4ctrl* will ask if it shall create it for you.
Preset files have no suffix and the file name is the preset name.

### Preset file format
Preset files consist of *topics* and *payloads*, separated by a single equal
sign '='. Lines beginning with '#' are considered to be comments and are
ignored (in fact, every line beginning with a non-alphanumeric character is).
Spaces and tab characters will also be ignored. You may add them to structure
the preset file.

```
# The first three bytes of the payload are the values for red, green and blue.
# Some devices take up to 7 bytes.
# **Note:** 4 and 7 channel cans use the last byte for brightness. You most
# likely want to set this to 'ff' as shown below.

# Full notation for 7 channel dmx cans.
dmx/plenarsaal/vorne1 = 0033ff 000000ff
#                                    ^^ Brightness

# Normal notation.
dmx/plenarsaal/vorne2 = 0033ff

# Short notation (same as '0033ff').
dmx/plenarsaal/vorne3 = 03f
```

### Virtual presets
The presets *off* and *random* are built-ins and are always available. Note that
*random* is not really random, but a kind of 'colorful random'.


## kitchentext
Kitchenlight utility script. *kitchentext* is written in python and depends on
*c4ctrl.py*.

```
$ kitchentext -h
```

## c4ctrl.vim
A vim plugin to help with the creation and editing of preset files. Depends on
*c4ctrl[.py]*. Install by putting *c4ctrl.vim* into your *~/.vim/plugin/*
directory or create a symbolic link there.
```
$ mkdir -p ~/.vim/plugin
$ ln -s /home/somepony/somedir/c4ctrl/c4ctrl.vim ~/.vim/plugin/c4ctrl.vim
```

### Usage
```
:C4ctrl get                    -- Read current state into buffer.
:C4ctrl open $name             -- Open local preset $name.
:C4ctrl set [w|p|f] [-magic]   -- Apply current buffer or range/selection as
                                  preset to room [w]ohnzimmer, [p]lenarsaal or
                                  [f]nordcenter. Default is all rooms.
:C4ctrl kitchentext [register] -- Display text in register, selected text or
                                  text in range on the Kitchenlight.
:C4ctrl write $name            -- Save current buffer as preset $name.
```

Commands and options (excluding preset names) may be abbreviated as long as
they stay unambiguous (e.g. *:C4 s w -m* is a valid command). Completion works
for commands, options and preset names. The recommended workflow looks like
this:

Read the current state of all ambient lights into a new buffer.
```
:C4 g
```

Make some edits. **Note:** Dmx cans taking 4 or 7 bytes use the last byte for
brightness. You most likely want this to be 'ff' (as seen below).
```
dmx/wohnzimmer/tuer1 = 00ff00 000000ff
                                    ^^
```

The *set* command optionally takes a range or selection. This way you can apply
changes to a subset of lights or a single light only. Alternatively you can
give a room name as option.
```
:.C4 s      <-- apply changes in the current line only (note the dot)
:'<,'>C4 s  <-- apply selected lines (use with <SHIFT>-V)
:C4 p       <-- apply all changes to plenarsaal
```

You can write your preset into *c4ctrl*s config directory with the *write*
command. **Note:** c4ctrl stores it's presets in *$XDG_CONFIG_HOME/c4ctrl/*
(likely *$HOME/.config/c4ctrl*). The vim plugin will **not** create this
directory for you if it doesn't exist. *c4ctrl* will. Either create the
directory by hand or run *c4ctrl -o pony* on the command line after applying
your changes.
```
:C4 w pony
```

You may open existing presets with *open*.
```
:C4 o pony
```

## _c4ctrl

Completion script for zsh.

### Installation

Put *_c4ctrl* somewhere into *$fpath* (or alter *$fpath* in your *~/.zshrc*).
See also: [[http://zsh.sourceforge.net/Doc/Release/Completion-System.html#Completion-Directories]]

For example:
Add the following lines to your *~/.zshrc* **before** any 'compinstall' stuff:
```
# Add custom zsh script directory to fpath
fpath=($fpath ~/.local/share/zsh)
```

Then create the directory and put a link to *_c4ctrl* there.
```
$ mkdir -p ~/.local/share/zsh
$ ln -s /home/somepony/somedir/c4ctrl/_c4ctrl ~/.local/share/zsh/_c4ctrl
```

