# c4ctrl
Command line client and utilities for AutoC4.

### Dependencies
* Python 3.?: [[https://www.python.org/]]
* Paho Python Client: [[https://github.com/eclipse/paho.mqtt.python]]

### Usage
```
$ c4ctrl.py -h
```

## kitchentext
Kitchenlight utility script.

```
$ kitchentext -h
```

## c4ctrl.vim
A vim plugin to help with the creation and editing of preset files.
Depends on *c4ctrl[.py]*. Install by putting *c4ctrl.vim* into your
*~/.vim/plugin/* directory.

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

## _c4ctrl

Completion script for zsh.

### Installation

Put *_c4ctrl* somewhere into *$fpath* (or alter *$fpath* in your *.zshrc*).
See also: [[http://zsh.sourceforge.net/Doc/Release/Completion-System.html#Completion-Directories]]

