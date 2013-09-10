# -*- encoding: utf-8 -*-

"""This script allows to reduce an snmpwalk to a test case by removing all oids
not queried by any plugin. If given --filter, it expects the walk on its
standard input and emits the filtered walk to stdout. A filtered walk should be
safe for publishing even if the original walk contains confidential data, but
this does not remove the need to apply common sense. If given --transform, it
parses the passed mapping file in a similar way to Makefile rules and applies
the filter to each rule."""

import os
import re
import sys

import argparse
try:
	from concurrent.futures import ProcessPoolExecutor as Executor
except ImportError:
	Executor = None

from .backend import mock
from . import plugins
from .plugins import detect

if Executor is None:
	import functools
	from . import future
	class Executor(object):  # pylint: disable=E0102
		def submit(self, fn, *args):
			fut = future.Future()
			future.complete_with(fut, functools.partial(fn, *args))
			return fut

def check_line(line, include_oids):
	match = re.match(r'^([0-9.]+?)\s*=', line)
	if not match:
		raise ValueError("non-assignment line: %r" % line)
	oid = match.groups()[0]
	oid = mock.parse_oid(oid)
	return any(plugins.oid_startswith(oid, checkoid)
				for checkoid in include_oids)

def check_stream(inp, outp):
	for line in inp:
		if check_line(line, detect.all_oids):
			outp.write(line)

def transform(source, destination):
	print("filtering %s to %s" % (source, destination))
	tmpfile = "%s.tmp" % destination
	try:
		with open(source) as inp:
			with open(tmpfile, "w") as outp:
				check_stream(inp, outp)
		os.rename(tmpfile, destination)
	finally:
		try:
			os.unlink(tmpfile)
		except OSError:
			pass

def main():
	parser = argparse.ArgumentParser()
	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument("--filter", action="store_true", help="act as a filter")
	group.add_argument("--transform", metavar="MAPPING", type=argparse.FileType("r"), help="transform all files given in the mapping file")
	parser.add_argument("--srcprefix", metavar="PREFIX", default="", help="when transforming data files prepend this PREFIX to source paths")
	parser.add_argument("--dstprefix", metavar="PREFIX", default="", help="when transforming data files prepend this PREFIX to destination paths")
	args = parser.parse_args()
	if args.filter:
		check_stream(sys.stdin, sys.stdout)
	else:
		exe = Executor()
		res = []
		for lineno, line in enumerate(args.transform):
			line = line.split('#', 1)[0]  # comment
			line = line.rstrip()  # trailing space or newline
			match = re.match(r'^(\S+):\s*(\S+)$', line)
			if not match:
				raise ValueError("syntax error on line %d" % (lineno + 1))
			destination, source = match.groups()
			source = os.path.join(args.srcprefix, source)
			destination = os.path.join(args.dstprefix, destination)
			res.append(exe.submit(transform, source, destination))
		while res:
			res.pop(0).result()  # propagate exceptions


if __name__ == "__main__":
	main()
