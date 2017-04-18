#!/usr/bin/python2
# -*- coding: utf-8 -*-
"""
watchtower - script looking for a file changes and executing actions.

Author: igrek51
License: Beerware
"""

import sys
import os
import subprocess
import time
import sets
import hashlib
from time import gmtime, strftime
import fnmatch

# Console text formatting characters
C_RESET = '\033[0m'
C_BOLD = '\033[1m'
C_DIM = '\033[2m'
C_ITALIC = '\033[3m'
C_UNDERLINE = '\033[4m'

C_BLACK = 0
C_RED = 1
C_GREEN = 2
C_YELLOW = 3
C_BLUE = 4
C_MAGENTA = 5
C_CYAN = 6
C_WHITE = 7


def textColor(colorNumber):
    """Return character changing console text colour."""
    return '\033[%dm' % (30 + colorNumber)


C_INFO = textColor(C_BLUE) + C_BOLD
C_OK = textColor(C_GREEN) + C_BOLD
C_WARN = textColor(C_YELLOW) + C_BOLD
C_ERROR = textColor(C_RED) + C_BOLD
T_INFO = C_INFO + '[info]' + C_RESET
T_OK = C_OK + '[OK]' + C_RESET
T_WARN = C_WARN + '[warn]' + C_RESET
T_ERROR = C_ERROR + '[ERROR]' + C_RESET


def info(message):
    """Print info message."""
    print(T_INFO + " " + message)


def ok(message):
    """Print success message."""
    print(T_OK + " " + message)


def warn(message):
    """Print warning message."""
    print(T_WARN + " " + message)


def error(message):
    """Print error message."""
    print(T_ERROR + " " + message)


def fatalError(message):
    """Print fatal error message and exits immediately."""
    error(message)
    sys.exit()


def shellExec(cmd):
    """Execute shell command."""
    errCode = subprocess.call(cmd, shell=True)
    if errCode != 0:
        fatalError('failed executing: %s' % cmd)


def shellExecErrorCode(cmd):
    """Execute shell command and returns error code."""
    return subprocess.call(cmd, shell=True)


def popArg(args):
    """Return first arg from args list and rest of the args."""
    if len(args) == 0:
        return (None, args)
    nextArg = args[0]
    args = args[1:]
    return (nextArg, args)


def nextArg(args):
    """Return first arg from args list."""
    if len(args) == 0:
        return None
    return args[0]


def clearConsole():
    """Clear console."""
    shellExec('tput reset')


def md5File(fname):
    """Return MD5 hash of file."""
    if not os.path.isfile(fname):
        fatalError('file does not exist: %s' % fname)
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def checksumFile(filename):
    """Calculate checksum of file."""
    return md5File(filename)


def printHelp():
    """Print help message."""
    print("""Monitor multiple files looking for a content change. \
When any change is detected execute given command.

Usage:
 %s [options] -f '<files>' [...] -e <command>

Options:
 -f, --files <file1> [<file2>] ['<pattern1>'] [...]\tmonitor single file, \
multiple files or shell-style wildcard patterns
  example patterns: file1, 'dir1/*', "*.tex", 'dir2/*.py', "*"
 -e, --exec <command>\texecute given command when any change is detected
 -i, --interval <seconds>\tset interval between subsequent changes checks \
(default 1 s)
 -h, --help\tdisplay this help and exit""" % sys.argv[0])


def currentTime():
    """Return current time as a string."""
    return strftime("%H:%M:%S", gmtime())


class ObservedFile:
    """Data structure containing file path with its last checksum."""

    def __init__(self, filePath):
        """Create ObservedFile.

        @param filePath: file path
        """
        self.filePath = filePath
        self.lastChecksum = None


class Main:
    """Main logic."""

    def __init__(self):
        """Create Main."""
        self.interval = 1  # seconds between subsequent changes checks
        self.executeCmd = None
        self.filePatterns = []
        self.observedFiles = []
        self.recursive = True

    def start(self):
        """Start application."""
        self._analyzeArgs()
        self._validateArgs()
        self._listObservedFiles()
        self._lookForChanges()

    def _analyzeArgs(self):
        args = sys.argv[1:]  # additional arguments list

        if not args:
            printHelp()
            sys.exit()

        while args:
            args = self._analyzeArg(*popArg(args))

    def _analyzeArg(self, arg, args):
        # help message
        if arg == '-h' or arg == '--help':
            printHelp()
            sys.exit()
        # interval set
        if arg == '-i' or arg == '--interval':
            (intervalStr, args) = popArg(args)
            self.interval = int(intervalStr)
        # execute command - everything after -e
        elif arg == '-e' or arg == '--exec':
            if not args:
                fatalError('not given command to execute')
            # pop all args
            self.executeCmd = ' '.join(args)
            args = []
        # select files to monitor
        elif arg == '-f' or arg == '--files':
            if nextArg(args) is None:
                fatalError('no file patterns specified')
            '''read params until there is no param'''
            ''' or param is from another option group'''
            while True:
                nextA = nextArg(args)  # just read next param, do not pop
                # if param is from another group
                if nextA is None or nextA.startswith('-'):
                    break
                (pattern, args) = popArg(args)
                self.filePatterns.append(pattern)
        else:
            fatalError('invalid parameter: %s' % arg)
        return args

    def _validateArgs(self):
        if self.interval < 1:
            fatalError('interval < 1')
        if len(self.filePatterns) == 0:
            fatalError('no file patterns specified')

    def _listObservedFiles(self):
        # collection of unique relative file paths
        filePaths = sets.Set()
        # walk over all files and subfiles
        for path, subdirs, files in os.walk('.'):
            for file in files:
                filePath = os.path.join(path, file)
                # cut './' from the beginning
                if filePath.startswith('./'):
                    filePath = filePath[2:]
                # check if file path is matching any pattern
                for pattern in self.filePatterns:
                    if fnmatch.fnmatch(filePath, pattern):
                        # add only if not present already
                        filePaths.add(filePath)
                        break

        # create list of unique observed files
        for filePath in filePaths:
            self.observedFiles.append(ObservedFile(filePath))
        # validate found files
        if not self.observedFiles:
            fatalError('no matching file found for specified patterns')

    def _lookForChanges(self):
        try:
            while True:
                changedFiles = self._findChangedFiles()
                # if anything has been changed
                if changedFiles:
                    clearConsole()
                    for changedFile in changedFiles:
                        info('%s - File has been changed: %s'
                             % (currentTime(), changedFile.filePath))
                    # execute given command
                    if self.executeCmd:
                        info('Executing: %s' % self.executeCmd)
                        errCode = shellExecErrorCode(self.executeCmd)
                        if errCode == 0:
                            ok('Success')
                        else:
                            error('failed executing: %s' % self.executeCmd)
                # wait some time before next check
                time.sleep(self.interval)

        except KeyboardInterrupt:
            # Ctrl + C handling without printing stack trace
            print  # new line

    def _findChangedFiles(self):
        """Check if some of the observed files has changed
        and return all changed files.
        """
        changedFiles = []
        # calculate and update checksums always for ALL files
        for observedFile in self.observedFiles:
            if os.path.isfile(observedFile.filePath):
                currentChecksum = checksumFile(observedFile.filePath)
            else:
                currentChecksum = None
            # different values with None value checking
            if ((observedFile.lastChecksum is None
                    and currentChecksum is not None)
                    or observedFile.lastChecksum != currentChecksum):
                changedFiles.append(observedFile)  # notify change
                observedFile.lastChecksum = currentChecksum  # update checksum

        return changedFiles


Main().start()
