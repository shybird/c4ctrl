" Vim plugin to use some functionality of c4ctrl from within Vim.
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

function C4ctrl(cmd, ...)
  let s:c4ctrl = "c4ctrl"

  " Check if we can excute c4ctrl
  if !executable(s:c4ctrl)
    " Maybe we judt need to add .py to the command?
    if executable(s:c4ctrl.".py")
      let s:c4ctrl = s:c4ctrl.".py"
    else
      echoerr "Executable not found:" s:c4ctrl
      finish
    endif
  endif

  if stridx("get", a:cmd) == 0
    " Read current status into new buffer
    if getbufinfo("%")[0].changed
      vnew
    endif
    set filetype=conf
    silent execute "0 read !" s:c4ctrl "-o -"

  elseif stridx("open", a:cmd) == 0
    " Edit an exiting preset
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

  elseif stridx("set", a:cmd) == 0
    " Set preset from current buffer
    " Let's start by building a command line
    let s:cmd = s:c4ctrl
    if a:0 == 0
      " If no room is given, set colors for all rooms
      let s:cmd = s:cmd . " -w - -p - -f -"
    endif

    for s:i in range(a:0)
      let  s:arg = a:000[s:i]
      if strchars(s:arg) == 1
        if stridx("wpf", s:arg) != -1
          let s:cmd = printf("%s -%s -", s:cmd, s:arg)
        endif
      elseif stridx("-magic", s:arg) == 0
        try
          let s:cmd = printf("%s --magic %s", s:cmd, a:000[s:i+1])
        catch /^Vim\%((\a\+)\)\=:E684/
          " Catching list index out of range
          echoerr "Option -magic expects one argument!"
          continue
        endtry
      endif
    endfor

    silent let s:ret = system(s:cmd, bufnr("%"))

    unlet! s:arg s:i s:cmd s:txt

  elseif stridx("text", a:cmd) == 0
    " Send line under the cursor to the Kitchenlight
    " Strip any ','
    let s:txt = substitute(getline("."), ",", "", "g")
    let s:ret = system(printf("%s -k text,%s", s:c4ctrl, shellescape(s:txt)))

    unlet! s:txt

  elseif stridx("write", substitute(a:cmd, "!$", "", "")) == 0
    " Save preset to config directory
    if !exists("a:1")
      echo "Missing filename!"
      return
    endif

    let s:cfgdir = s:FindConfigDir()
    if s:cfgdir == ""
      return
    endif

    let s:fn = s:cfgdir . a:1

    if strridx(a:cmd, "!") + 1 == len(a:cmd)
      " Force if a '!' was appended to the command
      execute "saveas!" fnameescape(s:fn)
    else
      execute "saveas" fnameescape(s:fn)
    endif

  else
    " Unknown command oO
    echo "Unknown command:" a:cmd
    echo "Valid commands are get, open, set, text and write"
  endif

  " Echo return if shell exited with an error
  if v:shell_error
    if exists("s:ret")
      echoerr s:ret
    endif
  endif

  unlet! s:c4ctrl s:ret s:cfgdir
endfunction

" Custom command line completion
function s:C4ctrlCompletion(ArgLead, CmdLine, CursorPos)
  let s:Name = "C4ctrl"
  " A list of current cmd line arguments excluding leading commands like
  " :vertical etc.
  let s:relCmdLine = split(a:CmdLine)
  let s:relCmdLine = s:relCmdLine[index(s:relCmdLine, s:Name):]

  try " Just for the clean up in the finally statement
    if stridx("open", get(s:relCmdLine, 1)) == 0
      if a:ArgLead != ""
        return "open"
      elseif len(s:relCmdLine) > 2 " Do not return more than one name
        return ""
      endif
      let s:cfgdir = s:FindConfigDir()
      if s:cfgdir == ""
        return ""
      endif
      return join(map(glob(s:cfgdir."*", 0, 1), "fnamemodify(v:val, ':t')"), "\n")

    elseif stridx("get", get(s:relCmdLine, 1)) == 0
      if a:ArgLead != ""
        return "get"
      endif
      return ""

    elseif stridx("set", get(s:relCmdLine, 1)) == 0
      if a:ArgLead != ""
        return "set"
      endif
      if stridx("-magic", get(s:relCmdLine, -1)) == 0
        return "none\nemp\nfade\nflash\nwave"
      endif
      return "w\np\nf\n-magic"

    elseif stridx("text", get(s:relCmdLine, 1)) == 0
      if a:ArgLead != ""
        return "text"
      endif
      return ""

    elseif stridx("write", get(s:relCmdLine, 1)) == 0
      if a:ArgLead != ""
        return "write"
      elseif len(s:relCmdLine) > 2 " Do not return more than one name
        return ""
      endif
      let s:cfgdir = s:FindConfigDir()
      if s:cfgdir == ""
        return ""
      endif
      return join(map(glob(s:cfgdir."*", 0, 1), "fnamemodify(v:val, ':t')"), "\n")

    elseif get(s:relCmdLine, -1) == s:Name
      return "get\nopen\nset\ntext\nwrite"
    else
      return ""
    endif

  finally
    unlet! s:relCmdLine s:Name s:cfgdir
  endtry
endfunction

if !exists(":C4ctrl")
  command -nargs=+ -complete=custom,s:C4ctrlCompletion C4ctrl call C4ctrl(<f-args>)
endif

