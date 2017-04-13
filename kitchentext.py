#!/usr/bin/env python3
#
# kitchentext: Read text from stdin and put it on the Kitchenlight.

def kitchentext(delay=200, single=False, wait=False, restore=False, poweron=False,
        verbose=False, debug=False):

    import sys
    from c4ctrl import C4Interface, Kitchenlight

    charwidth = { # Width of characters.
        'a' : 5, 'A' : 5, 'b' : 4, 'B' : 5,
        'c' : 3, 'C' : 5, 'd' : 4, 'D' : 5,
        'e' : 4, 'E' : 5, 'f' : 3, 'F' : 5,
        'g' : 3, 'G' : 5, 'h' : 3, 'H' : 5,
        'i' : 1, 'I' : 5, 'j' : 2, 'J' : 5,
        'k' : 3, 'K' : 5, 'l' : 3, 'L' : 5,
        'm' : 5, 'M' : 5, 'n' : 4, 'N' : 5,
        'o' : 3, 'O' : 5, 'p' : 3, 'P' : 5,
        'q' : 3, 'Q' : 5, 'r' : 3, 'R' : 5,
        's' : 4, 'S' : 5, 't' : 3, 'T' : 5,
        'u' : 3, 'U' : 5, 'v' : 3, 'V' : 5,
        'w' : 5, 'W' : 5, 'x' : 3, 'X' : 5,
        'y' : 3, 'Y' : 5, 'z' : 3, 'Z' : 5,
        '0' : 5, '1' : 4, '2' : 5, '3' : 5,
        '4' : 5, '5' : 5, '6' : 5, '7' : 5,
        '8' : 5, '9' : 5, '@' : 5, '=' : 3,
        '!' : 1, '"' : 3, '_' : 5, '-' : 3,
        '.' : 2, ',' : 2, '*' : 5, ':' : 2,
        '\'' : 1, '/' : 5, '(' : 2, ')' : 2,
        '{' : 3, '}' : 3, '[' : 2, ']' : 2,
        '<' : 3, '>' : 4, '+' : 5, '#' : 5,
        '$' : 5, '%' : 5, '$' : 5, '~' : 5,
        '?' : 3, ';' : 2, '\\' : 5, '^' : 3,
        '|' : 1, '`' : 2, ' ' : 3, '\t' : 5
        }

    C4Interface.debug = debug
    kl = Kitchenlight(autopower=poweron)

    # Enforce wait=True if restore=True or single=False.
    wait = wait or restore or not single

    # Store previous state.
    if restore:
        c4 = C4Interface()
        safe = c4.pull([kl.topic, kl.powertopic])

    try:
        while True:

            try:
                text = sys.stdin.readline()
            except KeyboardInterrupt: # Exit a bit more graceful on CTRL-C.
                verbose and sys.stderr.write("\rInterrupted by user\n")
                sys.exit(1)

            if single and text.rstrip('\n') == "":
                verbose and sys.stderr.write("Error: empty input!\n")
                sys.exit(1)
            elif text == "\n": # Empty line.
                verbose and print("Info: skipping empty line")
                continue
            elif text == "": # EOF.
                break

            # Strip chars Kitchenlight can not display.
            text = text.rstrip('\n').encode("ascii", "ignore").decode("ascii")

            try: # We might well get interrupted while waiting.
                kl.text(text, delay)

                if wait:
                    from time import sleep
                    # How long shall we wait?
                    # Kitchenlight has 30 columns, each char uses 2-5 columns followed by an empty
                    # one. The traversal of one column takes 30 * <delay> ms.
                    twidth = 0
                    for c in text:
                        try:
                            twidth += (charwidth[c] + 1)
                        except KeyError:
                            twidth += 4 # Fallback
                    wait_for = ((30 * delay) + (twidth * delay))/1000
                    verbose and print("Waiting for {} seconds ...".format(wait_for))
                    sleep(wait_for)

            except KeyboardInterrupt:
                verbose and sys.stderr.write("\rInterrupted by user\n")
                sys.exit(1)

    finally:
        # Always restore privious state if "restore" is set.
        if restore:
            re = []
            for top in safe: re.append((top.topic, top.payload))
            c4.push(re)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Read text from stdin and put it on the Kitchenlight")
    parser.add_argument(
        "-d", "--delay", type=int, default=200,
        help="delay in ms (speed of the text, default is 200)")
    parser.add_argument(
        "-s", "--single", action="store_true",
        help="only read a single line")
    parser.add_argument(
        "-w", "--wait", action="store_true", default=False,
        help="wait until the text has been displayed")
    parser.add_argument(
        "-r", "--restore", action="store_true", default=False,
        help="restore the Kitchenlight to its prior state after the text has been displayed (implies --wait)")
    parser.add_argument(
        "-p", "--power-on", action="store_true", default=False,
        help="turn on Kitchenlight if it is powered off")
    parser.add_argument(
        "-f", "--fork", action="store_true",
        help="fork to background")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="be (not much) more verbose")
    parser.add_argument(
        "--debug", action="store_true",
        help="display what would be send to the MQTT broker, but do not actually connect")
    args = parser.parse_args()

    if args.fork:
        import sys
        from posix import fork

        child_pid = fork()
        if child_pid != 0:
            args.verbose and print("Forked to PID", child_pid)
            sys.exit()

    kitchentext(delay=args.delay,
                single=args.single,
                wait=args.wait,
                restore=args.restore,
                poweron=args.power_on,
                verbose=args.verbose,
                debug=args.debug)

