#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import glob
import yaml
import codecs
import operator
from array import array
from collections import Counter
from collections import defaultdict

# example usage: $ ./transltr.py apply \*.s7i ~/Documents/seed7.yaml

#import pdb; pdb.set_trace()

SYMBOL_CHARS = ['=','>']

EXT_SYMBOLS = False

class Transl(yaml.YAMLObject):
	yaml_tag = u'!Transl'
	def __init__(self, fileName, identifiers):
		self.fileName = fileName
		self.identifiers = identifiers
	def __repr__(self):
		return "Transl(fileName=%r, ident=%d)" % (self.fileName, len(self.identifiers))

class IdentBuilder:
	def __init__(self, syntax, occurs):
		self.syntax = syntax
		self.occurs = occurs
		self.fname = None
	def start_file(self, fname):
		self.fname = fname
	def end_file(self, fname):
		self.fname = None
	def read_ident(self, chars, ln, col):
		if len(chars) > 1:
			token = reduce(operator.add, chars)
			syntax[token] += 1
			occurs[token].append((self.fname, ln, col))
	def read_char(self, ch, ln, col, squote, dquote):
		None
	
class IdentMapper:
	def __init__(self, syntax, fname, stream):
		self.syntax = syntax
		self.fname = fname
		self.stream = stream
		self.fromenc = 'en'
		self.toenc = 'ru'
	def read_ident(self, chars, ln, col, sysexpr):
		if sysexpr:
			self.stream.write("$ ")
			self.stream.write(reduce(operator.add, chars))
			return
		if len(chars) > 1:
			length = len(chars)
			startp = 0
			while startp < length:
				replaced = False
				for n in xrange(length, startp + 1, -1):
					token = reduce(operator.add, chars[startp:n])
					ident = self.find_ident(self.fname, token, self.fromenc)
					if ident == None:
						ident = self.find_ident('_', token, self.fromenc)
					if ident != None:
						self.stream.write(ident[self.toenc])
						replaced = True
						startp = n
						break
				if not replaced:
					while startp < length and chars[startp] != ' ':
						self.stream.write(chars[startp])
						startp += 1
				else:
					n = 0
				while startp < length and chars[startp] == ' ':
					self.stream.write(chars[startp])
					startp += 1
		else:
			ident = self.find_ident('_', '' + chars[0], self.fromenc)
			if ident != None:
				self.stream.write(ident[self.toenc])
			else:
				self.stream.write(chars[0])
				
	def read_char(self, ch, ln, col, squote, dquote):
		self.stream.write(ch)
		
	def find_ident(self, groupName, ident, enc):
		if groupName in self.syntax:
			for transl in self.syntax[groupName]:
				if transl[enc] == ident:
					return transl
		return None


def parse_file(visitor, fname, enc):
	l = 1
	with codecs.open(fname, mode="r", encoding=enc) as stream:
		try:
			comment = False
			squote = False
			dquote = False
			for line in stream:
				col = 1
				pc = ' '
				chars = []
				ident = False
				lcomment = False
				sysexpr = False
				escape = False
				for ch in line:
					if ident:
						if (ch.isalnum() or ch == '_'):
							chars.append(ch)
						elif EXT_SYMBOLS and ch in SYMBOL_CHARS:
							if not sysexpr:
								chars.append(ch)
							else:
								ident = False
						elif ch == ' ':
							if not sysexpr:
								chars.append(ch)
							elif len(chars) > 0:
								ident = False
						else:
							ident = False
						if len(chars) > 0 and not ident:
							visitor.read_ident(chars,l,col,sysexpr)
							chars = []
							sysexpr = False
							if ch == '$':
								ident = True
								sysexpr = True
					if squote:
						chars.append(ch)
					if ch == '#' and not comment:
						lcomment = True
					elif ch == '\\':
						escape = True
					elif ch == '*':
						if pc == '(' and not escape: comment = True
					elif ch == ')':
						if pc == '*' and comment and not escape: comment = False
					elif ch == '"' and not comment and not squote and not escape:
						if dquote == True: dquote = False
						else: dquote = True
					elif ch == "'" and not comment and not dquote:
						if squote == False:
							squote = True
						else:
							if len(chars) > 1:
								squote = False
								chars = []
							else:
								chars.append(ch)
					else:
						if not ident and not dquote and not squote and not comment and not lcomment:
							if ch.isalpha() or ch == '_' or (EXT_SYMBOLS and ch in SYMBOL_CHARS):
								ident = True
								chars.append(ch)
							elif ch == '$':
								ident = True
								sysexpr = True
					col+=1
					pc = ch
					if not ident:
						visitor.read_char(ch,l,col,squote,dquote)
					if ch != '\\':
						escape = False
				if len(chars) > 0 and ident:
					visitor.read_ident(chars,l,col,sysexpr)
					sysexpr = False
					ident = False
				l+=1
		finally:
			stream.close()

"""
Group all identifiers by file name.
Common identifiers that appear in
more than one file are put under '_'
"""
def file_bucket(syntax, occurs):
	fileBuckets = defaultdict(list)
	for token, count in syntax.most_common():
		uniqFiles = set()
		for (fname, l, col) in occurs[token]:
			uniqFiles.add(fname)
		# pdb.set_trace()
		if len(uniqFiles) == 1:
			fileBuckets[fname].append(token)
		else:
			fileBuckets['_'].append(token)
	return fileBuckets

"""
Read a list of yaml stream into a list of translations.
Combine all translations into a dictionary keyed by file name.
The values of dict are list of dictionaries of identifiers
"""
def read_syntax(fname):
	result = dict()
	with codecs.open(fname, mode='r', encoding='utf-8') as stream:
		try:
			data = yaml.load_all(stream)
			for transl in data:
				result[transl.fileName] = transl.identifiers
		except IOError:
			data = None
		finally:
			stream.close()
	if len(result) == 0:
		result['_'] = []
	return result

"""
Write full syntax into a single file.
Input is a dictionary of identifiers grouped by file name
"""
def write_syntax(fileBuckets, fullSyntax, fname):
	data = []
	for name in sorted(fileBuckets.keys()):
		transl = []
		for token in fileBuckets[name]:
			transl.append({'en':token, 'ru':token})
		data.append(Transl(name, transl))
	print data
	with open(fname, "w") as stream:
		try:
			yaml.dump_all(data, stream, default_flow_style=False, encoding='utf-8')
		finally:
			stream.close()

def main():
	syntax = Counter()
	occurs = defaultdict(list)
	args = sys.argv[1:]
	if not args:
		print 'usage: read|apply source_pattern [syntax_file]'
		sys.exit(1)
	syntax_file = 'seed7_syntax.yaml'
	if len(args) > 2 and args[2] != None:
		syntax_file = args[2]
	if args[0] == 'read':
		print 'Reading syntax...'
		visitor = IdentBuilder(syntax, occurs)
		for fname in glob.glob(args[1]):
			visitor.start_file(fname)
			parse_file(visitor, fname, 'latin-1')
			visitor.end_file(fname)
		fileBuckets = file_bucket(syntax, occurs)
		fullSyntax = read_syntax(syntax_file)
		write_syntax(fileBuckets, fullSyntax, 'output.yaml')
		# move file output.yaml to syntax_file
		# print occurs['in']
	elif args[0] == 'apply':
		print 'Applying syntax...'
		fullSyntax = read_syntax(syntax_file)
		for fname in glob.glob(args[1]):
			with codecs.open(fname + '.tmp', mode="w", encoding="utf-8", errors='replace') as stream:
				try:
					print "Processing", fname
					visitor = IdentMapper(fullSyntax, fname, stream)
					parse_file(visitor, fname, "utf-8")
					# move file fname.tmp to fname
				finally:
					stream.close()
	print "Done."

if __name__ == '__main__':
	main()
