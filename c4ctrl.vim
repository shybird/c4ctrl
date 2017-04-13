" c4ctrl.vim: This Vim plugin makes some functionality of the c4ctrl command
"             line utility available from within Vim.
"
" Last Change: 2017 Apr 13
" Maintainer: Shy
" License: This file is placed in the public domain.
"
" Usage: C4ctrl [get | kitchentext | open PRESET | set [w] [p] [f] [-magic] |
"                write PRESET]

if exists("g:loaded_c4ctrl")
  finish
endif
let g:loaded_c4ctrl = 1


function s:FindConfigDir()
  " ************************************************************************ "
  " Returns the path of c4ctrl configuration directory as string,            "
  " eg. '/home/somepony/.config/c4ctrl/'.                                    "
  " ************************************************************************ "

  " Return early if we already know it from an earlier invocation.
  if exists("s:config_dir")
    return s:config_dir
  endif

  if expand("$XDG_CONFIG_DIR") != "$XDG_CONFIG_DIR"
    let s:config_dir = expand("$XDG_CONFIG_DIR/c4ctrl/")
  else
    let s:config_dir = expand("$HOME/.config/c4ctrl/")
  endif

  if !isdirectory(s:config_dir)
    redraw | echohl WarningMsg
    echo "Error: could not access config directory:" s:config_dir."!"
    echohl None
    return ""
  endif
  return s:config_dir
endfunction


function C4ctrl(prev_cursor_pos, mods, first_line, last_line, command, ...) range
  " ************************************************************************ "
  " Make some functionality of the 'c4ctrl' command line utility available   "
  " from within Vim.                                                         "
  " Available commands are 'get', 'kitchentext', 'open', 'set' and 'write'.  "
  " Arguments:                                                               "
  "   prev_cursor_pos   -- cursor position as returned by getcurpos()        "
  "   mods              -- modifiers (:command variable <f-mods>)            "
  "   first_line        -- first line of range (:command <line1>)            "
  "   last_line         -- last line of range (:command <line2>)             "
  "   command           -- user command ('get', 'set' etc.)                  "
  "   [...]             -- optional command options                          "
  " ************************************************************************ "

  try " We utilize the finally section to delete some variables and functions.
    " Name of the executable.
    let s:c4ctrl = "c4ctrl"
  
    function! s:SynHighlight()
      " ******************************************************************** "
      " This function will be called after a preset has been loaded into the "
      " buffer. It will be deleted at the end of C4ctrl().                   "
      " ******************************************************************** "
  
      syn clear
      " Match topics
      syn match Identifier "^\s*[[:alnum:]/]\+\ze\s*="
      " Match color values with 3 digits
      syn match Number "=\s*\zs\%(\s*\x\)\{3}"
      " Match color values with 6 digits
      syn match Number "=\s*\zs\%(\s*\x\)\{6}"
      " Match comments
      syn match Comment "^\s*#.*" 
      " Match error: too few digits
      syn match Error "=\s*\zs\x\{1,2}\s*$"
      " Match error: invalid chars as digit
      syn match Error "=\s*\zs.*[^[:blank:][:xdigit:]]\+.*"
      "syn match Error "=\s*\zs.*\%(\S\&\X\)\+.*"

      " Move the cursor somewhere more practical.
      call cursor(1,1)
      call search("^[^#].*=[ \t]*[0-9a-fA-F]", 'eW')
    endfunction
  
    " Check if we can excute c4ctrl or c4ctrl.py and modify the variable
    " s:c4ctrl accordingly.
    if !executable(s:c4ctrl)
      " Maybe we just need to add .py to the command?
      if executable(s:c4ctrl.".py")
        let s:c4ctrl .= ".py"
      else
        redraw | echohl WarningMsg
        echo "Executable not found! Please put \"".s:c4ctrl."\" into your $PATH."
        echohl None
        unlet s:c4ctrl
        return
      endif
    endif
  
    if stridx("get", a:command) == 0
      " *********************************** "
      " Read current status into new buffer "
      " *********************************** "
      execute a:mods "new"
      silent execute "0 read !" s:c4ctrl "-o -"
      if v:shell_error == 0
        call s:SynHighlight()
        set nomodified " Mark as unmodified.
      else
        redraw | echohl WarningMsg
        echo printf("Error: %s returned exit code %d!", s:c4ctrl, v:shell_error)
        echohl None
      endif
  
    elseif stridx("kitchentext", a:command) == 0
      " ************************************** "
      " Send text in range to the Kitchenlight "
      " ************************************** "
      let kitchentext = "kitchentext"
      if !executable(kitchentext)
        redraw | echohl WarningMsg
        echo "Executable not found! Please put \"".kitchentext."\" into your $PATH."
        echohl None
        return
      endif

      let command_line = "kitchentext -f -d 150 -r -p"
      " Strip leading white spaces.
      let text = getline(a:first_line, a:last_line)
      call map(text, "substitute(v:val, '^[ \t]*', '', '')")
      let ret = system(command_line, text)
  
    elseif stridx("open", a:command) == 0
      " ********************** "
      " Edit an exiting preset "
      " ********************** "
      if !exists("a:1")
        redraw | echohl WarningMsg
        echo "Missing filename!"
        echohl None
        return
      endif
  
      let s:config_dir = s:FindConfigDir()
      if s:config_dir == ""
        return
      endif
      let filename = s:config_dir . a:1
      if !filereadable(filename)
        redraw | echohl WarningMsg
        echo "Error: could not open file" filename
        echohl None
        return
      endif
  
      execute a:mods "new"
      execute "edit" fnameescape(filename)
      call s:SynHighlight()
  
    elseif stridx("set", a:command) == 0
      " ****************************** "
      " Set preset from current buffer "
      " ****************************** "
      " Let's start by building a command line.
      let command_line = s:c4ctrl
      let rooms_given = 0
  
      for i in range(a:0)
        let  arg = a:000[i]
        for room in ["wohnzimmer", "plenarsaal", "fnordcenter"]
          if stridx(room, arg) == 0
            let command_line = printf("%s -%s -", command_line, arg[0])
            let rooms_given = 1
          endif
        endfor
        if stridx("-magic", arg) == 0
          let command_line = printf("%s --magic", command_line)
        endif
      endfor
  
      if rooms_given == 0
        " If no room is given, set colors for all rooms.
        let command_line .= " -w - -p - -f -"
      endif
  
      silent let ret = system(command_line, getline(a:first_line, a:last_line))
  
      " Restore cursor position.
      call setpos('.', a:prev_cursor_pos)
  
    elseif stridx("write", substitute(a:command, "!$", "", "")) == 0
      " ********************************* "
      " Save preset into config directory "
      " ********************************* "
      if !exists("a:1")
        redraw | echohl WarningMsg
        echo "Missing filename!"
        echohl None
        return
      endif
  
      let s:config_dir = s:FindConfigDir()
      if s:config_dir == ""
        return
      endif
  
      let filename = s:config_dir . a:1
  
      if strridx(a:command, "!") + 1 == len(a:command)
        " Force if a '!' was appended to the command.
        execute "saveas!" fnameescape(filename)
      else
        execute "saveas" fnameescape(filename)
      endif
      call s:SynHighlight()
  
    else
      " ****************** "
      " Unknown command oO "
      " ****************** "
      redraw | echohl WarningMsg
      echo "Unknown command:" a:command
      echohl None
      echo "Valid commands are get, kitchentext, open, set and write"
    endif
  
    " Echo return if shell exited with an error.
    if v:shell_error
      if exists("ret")
        echoerr ret
      endif
    endif
  
  finally
    unlet! s:c4ctrl s:config_dir
    delfunction s:SynHighlight
  endtry
endfunction


function s:C4ctrlCompletion(ArgLead, CmdLine, CursorPos)
  " ************************************************************************ "
  " Custom command line completion.                                          "
  " ************************************************************************ "

  " The name of the command we are adding to Vim.
  let command_name = "C4ctrl"
  " A list of current cmd line arguments, stripping everything up to the
  " first capital.
  let command_line = split(strpart(a:CmdLine, match(a:CmdLine, "[A-Z]")))
  " Check out if our name was abbreviated and modify accordingly
  while index(command_line, command_name) == -1
    let command_name = strpart(command_name, 0, len(command_name) - 1) 
    if len(command_name) == 0
      " This should never happen, but let's not risk an infinite loop anyway
      return ""
    endif
  endwhile
  " Position of our command in the command line.
  let command_index = index(command_line, command_name)

  try " We use the matching finally for cleaning up.
    if len(command_line) == command_index + 1 || (len(command_line) == command_index + 2 && a:ArgLead != "")
      " ************************** "
      " Complete the prime command "
      " ************************** "
      return "get\nkitchentext\nopen\nset\nwrite"
    endif

    if stridx("open", get(command_line, command_index + 1)) == 0 || (len(command_line) == command_index + 1 && a:ArgLead == command_name)
      " *************************** "
      " Complete the 'open' command "
      " *************************** "
      " ^ Note: the seconds part of the if rule above (the part after '||')
      " will eval to true whenever a filename matches our command name better
      " than the actually given command name (eg. ':C4 open C4c').
      if len(command_line) > command_index + 3 || (len(command_line) == command_index + 3 && a:ArgLead == "")
        " Do not return more than one file name.
        return ""
      endif
      let s:config_dir = s:FindConfigDir()
      if s:config_dir == ""
        return ""
      endif
      return join(map(glob(s:config_dir."*", 0, 1), "fnamemodify(v:val, ':t')"), "\n")

    elseif stridx("get", get(command_line, command_index + 1)) == 0
      " ************************** "
      " Complete the 'get' command "
      " ************************** "
      return ""

    elseif stridx("kitchentext", get(command_line, command_index + 1)) == 0
      " ********************************** "
      " Complete the 'kitchentext' command "
      " ********************************** "
      return ""

    elseif stridx("set", get(command_line, command_index + 1)) == 0
      " ************************** "
      " Complete the 'set' command "
      " ************************** "
      return "wohnzimmer\nplenarsaal\nfnordcenter\n-magic"

    elseif stridx("write", get(command_line, command_index + 1)) == 0 || (len(command_line) == command_index + 1 && a:ArgLead == command_name)
      " **************************** "
      " Complete the 'write' command "
      " **************************** "
      " ^ Note: the seconds part of the if rule above (the part after '||')
      " will eval to true whenever a filename matches our command name better
      " than the actually given command name (eg. ':C4 open C4c').
      if len(command_line) > command_index + 3 || (len(command_line) == command_index + 3 && a:ArgLead == "")
        " Do not return more than one file name.
        return ""
      endif
      let s:config_dir = s:FindConfigDir()
      if s:config_dir == ""
        return ""
      endif
      return join(map(glob(s:config_dir."*", 0, 1), "fnamemodify(v:val, ':t')"), "\n")

    else
      return ""
    endif

  finally
    unlet! s:config_dir
  endtry
endfunction


if !exists(":C4ctrl")
  " ********************** "
  " Add our command to Vim "
  " ********************** "
  command -nargs=+ -complete=custom,s:C4ctrlCompletion -range=% C4ctrl call C4ctrl(getcurpos(), <f-mods>, <line1>, <line2>, <f-args>)
endif

