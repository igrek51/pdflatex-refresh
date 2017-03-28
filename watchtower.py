#!/usr/bin/python2
# -*- coding: utf-8 -*-

import sys
import re
import subprocess
import threading
import string
import os
import time
import sets
import glob
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
	print(T_INFO + " " + message)

def ok(message):
	print(T_OK + " " + message)

def warn(message):
	print(T_WARN + " " + message)

def error(message):
	print(T_ERROR + " " + message)

def fatalError(message):
	error(message)
	sys.exit()


def shellExec(cmd):
	errCode = subprocess.call(cmd, shell=True)
	if errCode != 0:
		fatalError('failed executing: %s' % cmd)

def shellExecErrorCode(cmd):
	return subprocess.call(cmd, shell=True)


def popArg(argsDict):
	args = argsDict['args']
	if len(args) == 0:
		return None
	next = args[0]
	argsDict['args'] = args[1:]
	return next

def nextArg(argsDict):
	args = argsDict['args']
	if len(args) == 0:
		return None
	return args[0]

def clearConsole():
	shellExec('tput reset')

def checksumFile(filename):
	return md5File(filename)

def md5File(fname):
	if not os.path.isfile(fname):
		fatalError('file does not exist: %s' % fname)
	hash_md5 = hashlib.md5()
	with open(fname, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()

def printHelp():
	print('Monitors multiple files looking for a content change. When detected executes given command.')
	print('Usage:')
	print(' %s [options] -f \'<files>\' [...] -e <command>' % sys.argv[0])
	print('\nOptions:')
	print(' -f, --files <file1> [<file2>] [\'<pattern1>\'] [...]\t' + 'monitor file, multiple files or shell-style wildcard patterns')
	print('  example patterns (quotes necessary): file1, \'dir1/*\', \'*.tex\', "dir2/*.py", "*"')
	print('')
	print(' -e, --exec <command>\t' + 'execute given command when change is detected')
	print(' -i, --interval <seconds>\t' + 'set interval between subsequent changes checks')
	print(' -h, --help\t' + 'display this help and exit')

def currentTime():
	return strftime("%H:%M:%S", gmtime())

class ObservedFile:
	def __init__(self, filePath):
		self.filePath = filePath
		self.lastChecksum = None

class Main:

	def __init__(self):
		self.interval = 1 # seconds between subsequent changes checks
		self.executeCmd = None
		self.filePatterns = []
		self.observedFiles = []
		self.recursive = True

	def start(self):
		self.readParams()
		self.validateParams()
		self.listObservedFiles()
		self.lookForChanges()

	def readParams(self):
		argsDict = {'args': sys.argv[1:]}

		if len(argsDict['args']) == 0:
			printHelp()
			sys.exit()

		while len(argsDict['args']) > 0:
			arg = popArg(argsDict)
			# help message
			if arg == '-h' or arg == '--help':
				printHelp()
				sys.exit()
			# interval set
			if arg == '-i' or arg == '--interval':
				intervalStr = popArg(argsDict)
				self.interval = int(intervalStr)
			# execute command - all after -e
			elif arg == '-e' or arg == '--exec':
				# pop all args
				execs = argsDict['args']
				argsDict['args'] = []
				if len(execs) == 0:
					fatalError('no command to execute given')
				self.executeCmd = ' '.join(execs)
			# select files to monitor
			elif arg == '-f' or arg == '--files':
				if nextArg(argsDict) is None:
					fatalError('no file patterns specified')
				# read params until there is no param or param is from another group
				while True:
					nextA = nextArg(argsDict) # just read next param, do not pop
					# if param is from another group
					if nextA is None or nextA.startswith('-'):
						break
					self.filePatterns.append(popArg(argsDict))
			else:
				fatalError('invalid parameter: %s' % arg)

	def validateParams(self):
		if self.interval < 1:
			fatalError('interval < 1')
		if len(self.filePatterns) == 0:
			fatalError('no file patterns specified')

	def listObservedFiles(self):
		# collection of unique relative file paths
		filePaths = sets.Set()
		# walk over all files and subfiles
		for path, subdirs, files in os.walk('.'):
			for file in files:
				filePath = os.path.join(path, file)
				# cut './' from the beginning
				if filePath.startswith('./'):
					filePath = filePath[2:]
				# for all patterns
				for pattern in self.filePatterns:
					# check if file path is matching pattern
					if fnmatch.fnmatch(filePath, pattern):
						# file is matching the pattern
						filePaths.add(filePath)
						break

		# create list of unique observed files
		for filePath in filePaths:
			self.observedFiles.append(ObservedFile(filePath))
		# validate found files
		if not self.observedFiles:
			fatalError('no matching file found for specified patterns')

	def lookForChanges(self):
		try:
			while True:
				changedFiles = self.filesChanged()
				if changedFiles:
					clearConsole()
					for changedFile in changedFiles:
						info('%s - File has been changed: %s' % (currentTime(), changedFile.filePath))
					# execute given command
					if self.executeCmd is not None:
						info('Executing: %s' % self.executeCmd)
						errCode = shellExecErrorCode(self.executeCmd)
						if errCode == 0:
							ok('Success')
						else:
							error('failed executing: %s' % self.executeCmd)
				# wait some time before next check
				time.sleep(self.interval)

		except KeyboardInterrupt: # Ctrl + C handling without printing stack trace
			print # new line

	def filesChanged(self):
		"""checks if some of the observed files has changed and returns all changed files"""
		changedFiles = []
		# calculate and update checksums always for ALL files
		for observedFile in self.observedFiles:
			if os.path.isfile(observedFile.filePath):
				currentChecksum = checksumFile(observedFile.filePath)
			else:
				currentChecksum = None	
			if (observedFile.lastChecksum is None and currentChecksum is not None) or observedFile.lastChecksum != currentChecksum:
				changedFiles.append(observedFile) # notify change
				observedFile.lastChecksum = currentChecksum # update checksum

		return changedFiles

Main().start()
