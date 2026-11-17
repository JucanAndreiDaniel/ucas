#!/usr/bin/env python3
# Reset SIGINT/SIGQUIT to default disposition, then exec the given command.
# Background jobs started with '&' inherit SIG_IGN for INT/QUIT from bash;
# this restores the disposition a foreground process would have.
import os, signal, sys
signal.signal(signal.SIGINT, signal.SIG_DFL)
signal.signal(signal.SIGQUIT, signal.SIG_DFL)
os.execvp(sys.argv[1], sys.argv[1:])
