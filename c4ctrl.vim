" This Vim plugin makes some functionality of the c4ctrl utility available
" from within Vim.
"
" Last Change: 2017 Mar 29
" Maintainer: Shy
" License: This file is placed in the public domain.
"
" Usage: C4ctrl [get | open PRESET | set [w] [p] [f] [-magic MODE] |
"                text | write]

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
  if exists("s:cfgdir")
    return s:cfgdir
  endif

  if expand("$XDG_CONFIG_DIR") != "$XDG_CONFIG_DIR"
    let s:cfgdir = expand("$XDG_CONFIG_DIR/c4ctrl/")
  else
    let s:cfgdir = expand("$HOME/.config/c4ctrl/")
  endif

  if !isdirectory(s:cfgdir)
    echo "Could not access config dir:" s:cfgdir
    return ""
  endif
  return s:cfgdir
endfunction


function C4ctrl(command, ...)
  " Valid commands are get,open,set,text and write

  " Our name
  let s:c4ctrl = "c4ctrl"

  " This function will be called after a preset file has been loaded
  " into the buffer.k
  function s:SynHighlight()
    syn match Identifier "^[ \t]*[0-9a-zA-Z/]*"
    " Match values like 03f with optional space between
    syn match Number "=\([ \t]*[0-9a-fA-F]\)\{3} *$"hs=s+1
    " Match values like 0033ff with optional space between bytes
    syn match Number "=\([ \t]*[0-9a-fA-F]\{2}\)\{3}"hs=s+1
    syn match Comment "^[ \t]*[#!\"].*" 
  endfunction

  " Check if we can excute c4ctrl or c4ctrl.py and modify the variable
  " s:c4ctrl accordingly
  if !executable(s:c4ctrl)
    " Maybe we judt need to add .py to the command?
    if executable(s:c4ctrl.".py")
      let s:c4ctrl = s:c4ctrl.".py"
    else
      echoerr "Executable not found! Please put \"".s:c4ctrl."\" into your $PATH."
      return
    endif
  endif

  if stridx("get", a:command) == 0
    " *********************************** "
    " Read current status into new buffer "
    " *********************************** "
    if getbufinfo("%")[0].changed
      vnew
    endif
    silent execute "0 read !" s:c4ctrl "-o -"
    call s:SynHighlight()

  elseif stridx("open", a:command) == 0
    " ********************** "
    " Edit an exiting preset "
    " ********************** "
    if !exists("a:1")
      echo "Missing filename!"
      return
    endif

    let s:cfgdir = s:FindConfigDir()
    if s:cfgdir == ""
      return
    endif
    let s:fn = s:cfgdir . a:1
    if !filereadable(s:fn)
      echoerr "Error: could not open file" s:fn
      return
    endif

    if getbufinfo("%")[0].changed
      vnew
    endif
    execute "edit" fnameescape(s:fn)
    call s:SynHighlight()

  elseif stridx("set", a:command) == 0
    " ****************************** "
    " Set preset from current buffer "
    " ****************************** "

    " Let's start by building a command line
    let s:command_line = s:c4ctrl
    if a:0 == 0
      " If no room is given, set colors for all rooms
      let s:command_line = s:command_line . " -w - -p - -f -"
    endif

    for s:i in range(a:0)
      let  s:arg = a:000[s:i]
      if strchars(s:arg) == 1
        if stridx("wpf", s:arg) != -1
          let s:command_line = printf("%s -%s -", s:command_line, s:arg)
        endif
      elseif stridx("-magic", s:arg) == 0
        try
          let s:command_line = printf("%s --magic %s", s:command_line, a:000[s:i+1])
        catch /^Vim\%((\a\+)\)\=:E684/
          " Catching list index out of range
          echoerr "Option -magic expects one argument!"
          continue
        endtry
      endif
    endfor

    silent let s:ret = system(s:command_line, bufnr("%"))

    unlet! s:arg s:i s:command_line s:txt

  elseif stridx("text", a:command) == 0
    " ********************************************** "
    " Send line under the cursor to the Kitchenlight "
    " ********************************************** "

    " Strip any ','
    let s:txt = substitute(getline("."), ",", "", "g")
    let s:ret = system(printf("%s -k text,%s", s:c4ctrl, shellescape(s:txt)))

    unlet! s:txt

  elseif stridx("write", substitute(a:command, "!$", "", "")) == 0
    " ********************************* "
    " Save preset into config directory "
    " ********************************* "
    if !exists("a:1")
      echo "Missing filename!"
      return
    endif

    let s:cfgdir = s:FindConfigDir()
    if s:cfgdir == ""
      return
    endif

    let s:fn = s:cfgdir . a:1

    if strridx(a:command, "!") + 1 == len(a:command)
      " Force if a '!' was appended to the command
      execute "saveas!" fnameescape(s:fn)
    else
      execute "saveas" fnameescape(s:fn)
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
    if exists("s:ret")
      echoerr s:ret
    endif
  endif

  unlet! s:c4ctrl s:ret s:cfgdir
  delfunction s:SynHighlight
endfunction


function s:C4ctrlCompletion(ArgLead, CmdLine, CursorPos)
  " ****************************** "
  " Custom command line completion "
  " ****************************** "

  " The name of the command we are adding to Vim
  let s:Name = "C4ctrl"
  " A list of current cmd line arguments excluding leading commands like
  " :vertical, :tab etc.
  let s:relCmdLine = split(a:CmdLine)
  let s:relCmdLine = s:relCmdLine[index(s:relCmdLine, s:Name):]

  try " We use the matching finally for cleaning up
    if stridx("open", get(s:relCmdLine, 1)) == 0
      " *************************** "
      " Complete the 'open' command "
      " *************************** "
      if a:ArgLead != ""
        if len(s:relCmdLine) == 2
          return "open"
        endif
      elseif len(s:relCmdLine) > 2
        " Do not return more than one file name
        return ""
      endif
      let s:cfgdir = s:FindConfigDir()
      if s:cfgdir == ""
        return ""
      endif
      return join(map(glob(s:cfgdir."*", 0, 1), "fnamemodify(v:val, ':t')"), "\n")

    elseif stridx("get", get(s:relCmdLine, 1)) == 0
      " ************************** "
      " Complete the 'get' command "
      " ************************** "
      if a:ArgLead != ""
        return "get"
      endif
      return ""

    elseif stridx("set", get(s:relCmdLine, 1)) == 0
      " ************************** "
      " Complete the 'set' command "
      " ************************** "
      if a:ArgLead != ""
        if stridx("-magic", get(s:relCmdLine, -2)) == 0
          return "none\nemp\nfade\nflash\npulse\nwave"
        endif
        return "set\n-magic"
      elseif stridx("-magic", get(s:relCmdLine, -1)) == 0
        return "none\nemp\nfade\nflash\npulse\nwave"
      endif
      return "w\np\nf\n-magic"

    elseif stridx("text", get(s:relCmdLine, 1)) == 0
      " *************************** "
      " Complete the 'text' command "
      " *************************** "
      if a:ArgLead != ""
        return "text"
      endif
      return ""

    elseif stridx("write", get(s:relCmdLine, 1)) == 0
      " **************************** "
      " Complete the 'write' command "
      " **************************** "
      if a:ArgLead != ""
        if len(s:relCmdLine) == 2 && a:ArgLead != ""
          return "write"
        endif
      elseif len(s:relCmdLine) > 2 && a:ArgLead == ""
        " Do not return more than one file name
        return ""
      endif
      let s:cfgdir = s:FindConfigDir()
      if s:cfgdir == ""
        return ""
      endif
      return join(map(glob(s:cfgdir."*", 0, 1), "fnamemodify(v:val, ':t')"), "\n")

    elseif get(s:relCmdLine, -1) == s:Name
      " ************************** "
      " Complete the first command "
      " ************************** "
      return "get\nopen\nset\ntext\nwrite"
    else
      return ""
    endif

  finally
    unlet! s:relCmdLine s:Name s:cfgdir
  endtry
endfunction


if !exists(":C4ctrl")
  " ********************** "
  " Add our command to Vim "
  " ********************** "
  command -nargs=+ -complete=custom,s:C4ctrlCompletion C4ctrl call C4ctrl(<f-args>)
endif

