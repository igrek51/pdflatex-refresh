#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import time
import hashlib

# Znaki formatowania tekstu
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
C_ERROR = textColor(C_RED) + C_BOLD
T_INFO = C_INFO + '[info]' + C_RESET
T_ERROR = C_ERROR + '[ERROR]' + C_RESET

def info(message):
	print(T_INFO + " " + message)

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

def clearConsole():
	shellExec('tput reset')

def md5File(fname):
	if not os.path.isfile(fname):
		fatalError("file does not exist: " + fname)
	hash_md5 = hashlib.md5()
	with open(fname, "rb") as f:
		for chunk in iter(lambda: f.read(4096), b""):
			hash_md5.update(chunk)
	return hash_md5.hexdigest()

def fileContent(filename):
	if not os.path.isfile(filename):
		fatalError("file does not exist: " + filename)
	with open(filename, 'rb') as f:
		content = f.read()
	return content.decode('utf-8')

def saveFile(filename, content):
	f = open(filename, 'wb')
	f.write(bytes(content, 'utf-8'))
	f.close()

interval = 1
TEX_FILE = None
lastMd5 = None

argsDict = {'args': sys.argv[1:]}

if len(argsDict['args']) == 0:
	print('commands:')
	print('\t' + '[--interval <n>] <file.tex>')
	sys.exit()

while len(argsDict['args']) > 0:
	arg = popArg(argsDict)
	# zmiana interwału
	if arg == "--interval":
		intervalStr = popArg(argsDict)
		interval = int(intervalStr)
	else:
		if len(argsDict['args']) > 0:
			fatalError('too many command line arguments')
		TEX_FILE = arg

if TEX_FILE is None:
	fatalError('No input tex file')

try:

	while True:
		currentMd5 = md5File(TEX_FILE)

		# zmiana w pliku (lub pierwsze uruchomienie) - wykonanie kompilacji
		if lastMd5 is None or lastMd5 != currentMd5:
			clearConsole()
			cmd = 'pdflatex -interaction nonstopmode -halt-on-error -file-line-error "' + TEX_FILE + '"'
			if lastMd5 is None:
				info("compiling: " + cmd + " ...")
			else:
				info("file "+TEX_FILE+" changed, recompiling: " + cmd + " ...")

			# TODO czyszczenie pozostałych plików śmieciowych uniemożliwiających zbudowanie

			errCode = shellExecErrorCode(cmd)
			if errCode == 0:
				info(TEX_FILE+' compiled.')
			else:
				error(TEX_FILE + ' compilation failed.')

			lastMd5 = currentMd5

		# odczekanie
		time.sleep(interval)

except KeyboardInterrupt: # obsługa wciśnięcia Ctrl + C - brak stack trace
	print