# c4ctrl
Command line client and utilities for AutoC4.

### Dependencies
* Python 3.?: [[https://www.python.org/]]
* Paho Python Client: [[https://github.com/eclipse/paho.mqtt.python]]

### Usage
```
c4ctrl.py -h
```

## kitchentext.py
Kitchenlight utility script.

```
kitchentext.py -h
```

## c4ctrl.vim
A vim plugin to help with the creation and editing of preset files.
Depends on *c4ctrl[.py]*. Install by putting *c4ctrl.vim* into your
*~/.vim/plugin/* directory.

### Usage
```
:C4ctrl get                 -- Read current state into buffer.
:C4ctrl open $name          -- Open local preset $name.
:C4ctrl set [w|p|f]         -- Apply current buffer as preset to room
            [-magic $mode]     [w]ohnzimmer, [p]lenarsaal or [f]nordcenter.
                               Default is all rooms.
:C4ctrl text                -- Put line under cursor on the Kitchenlight.
:C4ctrl write $name         -- Save current buffer as preset $name.
```
