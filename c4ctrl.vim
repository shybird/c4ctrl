" Vim plugin to use some functionality of c4ctrl from within Vim.
"
" Last Change: 2017 Mar 28
" Maintainer: Shy
" License: This file is placed in the public domain.
"
" Usage: C4ctrl [get] [open $preset] [set [w][p][f]] [text] [write]

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
    new
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
    execute "new" fnameescape(s:fn)

  elseif stridx("set", a:cmd) == 0
    " Set preset from current buffer
    " Let's start by building a command line
    let s:cmd = s:c4ctrl
    if a:0 == 0
      " If no room is given, set colors for all rooms
      let s:cmd = s:cmd . " -w - -p - -f -"
    endif

    for s:arg in a:000
      " Ignore options which are longer than 1 char
      if strchars(s:arg) != 1
        continue
      endif
      " Ignore unknown chars 
      if stridx("wpf", s:arg) == -1
        continue
      endif
      let s:cmd = printf("%s -%s -", s:cmd, s:arg)
    endfor

    silent let s:ret = system(s:cmd, bufnr("%"))

    unlet! s:arg s:cmd s:txt

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
      " Force if a ! was appended to the command
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
  if stridx(a:CmdLine, "open") != -1
    let s:cfgdir = s:FindConfigDir()
    if s:cfgdir == ""
      return ""
    endif
    return join(map(glob(s:cfgdir."*", 0, 1), "fnamemodify(v:val, ':t')"), "\n")
  elseif stridx(a:CmdLine, "get") != -1
    return ""
  elseif stridx(a:CmdLine, "set") != -1
    return "w\np\nf"
  elseif stridx(a:CmdLine, "text") != -1
    return ""
  elseif stridx(a:CmdLine, "write") != -1
    let s:cfgdir = s:FindConfigDir()
    if s:cfgdir == ""
      return ""
    endif
    return join(map(glob(s:cfgdir."*", 0, 1), "fnamemodify(v:val, ':t')"), "\n")
  endif

  return "get\nopen\nset\ntext\nwrite"
endfunction

if !exists(":C4ctrl")
  command -nargs=+ -complete=custom,s:C4ctrlCompletion C4ctrl call C4ctrl(<f-args>)
endif

