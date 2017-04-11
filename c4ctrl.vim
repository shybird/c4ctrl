" This Vim plugin makes some functionality of the c4ctrl utility available
" from within Vim.
"
" Last Change: 2017 Apr 11
" Maintainer: Shy
" License: This file is placed in the public domain.
"
" Usage: C4ctrl [get | open PRESET | set [w] [p] [f] [-magic] | text | write]

if exists("g:loaded_c4ctrl")
  finish
endif
let g:loaded_c4ctrl = 1


function s:FindConfigDir()
  " ************************************************ "
  " Returns the path of the configuration directory, "
  " eg. '/home/somepony/.config/c4ctrl/'             "
  " ************************************************ "

  " Run only once
  if exists("s:config_dir")
    return s:config_dir
  endif

  if expand("$XDG_CONFIG_DIR") != "$XDG_CONFIG_DIR"
    let s:config_dir = expand("$XDG_CONFIG_DIR/c4ctrl/")
  else
    let s:config_dir = expand("$HOME/.config/c4ctrl/")
  endif

  if !isdirectory(s:config_dir)
    echo "Could not access config dir:" s:config_dir
    return ""
  endif
  return s:config_dir
endfunction


function C4ctrl(prev_cursor_pos, mods, first_line, last_line, command, ...) range
  " *********************************************************************** "
  " Make some functionality of the 'c4ctrl' command line utility available  "
  " from within Vim.                                                        "
  " Available commands are 'get', 'open', 'set', 'text' and 'write'.        "
  " Arguments:                                                              "
  "   prev_cursor_pos   -- cursor position as returned by getcurpos()       "
  "   mods              -- modifiers (:command variable <f-mods>)           "
  "   first_line        -- first line of range (:command <line1>            "
  "   last_line         -- last line of range (:command <line2>             "
  "   command           -- user command ('get', 'set' etc.)                 "
  "   [command options] -- optional command options                         "
  " *********************************************************************** "

  " Name of the executable.
  let s:c4ctrl = "c4ctrl"

  " This function will be called after a preset file has been loaded
  " into the buffer.
  function! s:SynHighlight()
    " Match topics
    syn match Identifier "\c^\s*[0-9a-z/]*\ze\s*="
    " Match color values with 3 digits
    syn match Number "\c=\s*\zs\(\s*[0-9a-f]\)\{3}"
    " Match color values with 6 digits
    syn match Number "\c=\s*\zs\(\s*[0-9a-f]\)\{6}"
    " Match comments
    syn match Comment "^\s*[#!\"].*" 
    " Match error: too few digits
    syn match Error "\c=\s*\zs[0-9a-f]\{1,2}$"
    " Match error: invalid chars as digit
    syn match Error "\c=\s*\zs.*[^ \t0-9a-f]\+.*"
  endfunction

  " Check if we can excute c4ctrl or c4ctrl.py and modify the variable
  " s:c4ctrl accordingly
  if !executable(s:c4ctrl)
    " Maybe we just need to add .py to the command?
    if executable(s:c4ctrl.".py")
      let s:c4ctrl .= ".py"
    else
      echoerr "Executable not found! Please put \"".s:c4ctrl."\" into your $PATH."
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
    normal 0gg
    call s:SynHighlight()

  elseif stridx("open", a:command) == 0
    " ********************** "
    " Edit an exiting preset "
    " ********************** "
    if !exists("a:1")
      echo "Missing filename!"
      return
    endif

    let s:config_dir = s:FindConfigDir()
    if s:config_dir == ""
      return
    endif
    let filename = s:config_dir . a:1
    if !filereadable(filename)
      echoerr "Error: could not open file" filename
      return
    endif

    execute a:mods "new"
    execute "edit" fnameescape(filename)
    call s:SynHighlight()

  elseif stridx("set", a:command) == 0
    " ****************************** "
    " Set preset from current buffer "
    " ****************************** "

    " Let's start by building a command line
    let command_line = s:c4ctrl
    if a:0 == 0
      " If no room is given, set colors for all rooms
      let command_line .= " -w - -p - -f -"
    endif

    for i in range(a:0)
      let  arg = a:000[i]
      if strchars(arg) == 1
        if stridx("wpf", arg) != -1
          let command_line = printf("%s -%s -", command_line, arg)
        endif
      elseif stridx("-magic", arg) == 0
        let command_line = printf("%s --magic", command_line)
      endif
    endfor

    silent let ret = system(command_line, getline(a:first_line, a:last_line))

    " Restore cursor position
    call setpos('.', a:prev_cursor_pos)

  elseif stridx("text", a:command) == 0
    " ********************************************** "
    " Send line under the cursor to the Kitchenlight "
    " ********************************************** "

    " Strip any ','
    let txt = substitute(getline("."), ",", "", "g")
    let ret = system(printf("%s -k text,%s", s:c4ctrl, shellescape(txt)))

  elseif stridx("write", substitute(a:command, "!$", "", "")) == 0
    " ********************************* "
    " Save preset into config directory "
    " ********************************* "
    if !exists("a:1")
      echo "Missing filename!"
      return
    endif

    let s:config_dir = s:FindConfigDir()
    if s:config_dir == ""
      return
    endif

    let filename = s:config_dir . a:1

    if strridx(a:command, "!") + 1 == len(a:command)
      " Force if a '!' was appended to the command
      execute "saveas!" fnameescape(filename)
    else
      execute "saveas" fnameescape(filename)
    endif

  else
    " ****************** "
    " Unknown command oO "
    " ****************** "
    echo "Unknown command:" a:command
    echo "Valid commands are get, open, set, text and write"
  endif

  " Echo return if shell exited with an error
  if v:shell_error
    if exists("ret")
      echoerr ret
    endif
  endif

  unlet! s:c4ctrl s:config_dir
  delfunction s:SynHighlight
endfunction


function s:C4ctrlCompletion(ArgLead, CmdLine, CursorPos)
  " ****************************** "
  " Custom command line completion "
  " ****************************** "

  " The name of the command we are adding to Vim
  let command_name = "C4ctrl"
  " A list of current cmd line arguments
  let command_line = split(a:CmdLine)
  " Check out if our name was abbreviated and modify accordingly
  while index(command_line, command_name) == -1
    let command_name = strpart(command_name, 0, len(command_name) - 1) 
    if len(command_name) == 0
      " This should never happen, but let's not risk an infinite loop anyway
      return ""
    endif
  endwhile
  " Position of our command in the command line
  let command_index = index(command_line, command_name)

  try " We use the matching finally for cleaning up
    if stridx("open", get(command_line, command_index + 1)) == 0 || (len(command_line) == command_index + 1 && a:ArgLead == command_name)
      " *************************** "
      " Complete the 'open' command "
      " *************************** "
      " ^ Note: the seconds part of the if rule (the part after '||') will
      " eval to true if a filename matches our command name better than the
      " actually given command name (eg. ':C4 open C4c')
      if a:ArgLead != ""
        if len(command_line) == command_index + 2
          return "open"
        endif
      elseif len(command_line) > command_index + 2
        " Do not return more than one file name
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
      if a:ArgLead != ""
        return "get"
      endif
      return ""

    elseif stridx("set", get(command_line, command_index + 1)) == 0
      " ************************** "
      " Complete the 'set' command "
      " ************************** "
      if a:ArgLead != ""
        return "set\n-magic"
      endif
      return "w\np\nf\n-magic"

    elseif stridx("text", get(command_line, command_index + 1)) == 0
      " *************************** "
      " Complete the 'text' command "
      " *************************** "
      if a:ArgLead != ""
        return "text"
      endif
      return ""

    elseif stridx("write", get(command_line, command_index + 1)) == 0 || (len(command_line) == command_index + 1 && a:ArgLead == command_name)
      " **************************** "
      " Complete the 'write' command "
      " **************************** "
      " ^ Note: the seconds part of the if rule (the part after '||') will
      " eval to true if a filename matches our command name better than the
      " actually given command name (eg. ':C4 open C4c')
      if a:ArgLead != ""
        if len(command_line) == command_index + 2
          return "write"
        endif
      elseif len(command_line) > command_index + 2
        " Do not return more than one file name
        return ""
      endif
      let s:config_dir = s:FindConfigDir()
      if s:config_dir == ""
        return ""
      endif
      return join(map(glob(s:config_dir."*", 0, 1), "fnamemodify(v:val, ':t')"), "\n")

    elseif len(command_line) == command_index + 1
      " ************************** "
      " Complete the first command "
      " ************************** "
      return "get\nopen\nset\ntext\nwrite"
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

