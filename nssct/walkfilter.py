# -*- encoding: utf-8 -*-

"""This script allows to reduce an snmpwalk to a test case by removing all oids
not queried by any plugin. It expects the walk on its standard input or in a
file passed and emits the filtered walk to stdout. A filtered walk should be
safe for publishing even if the original walk contains confidential data, but
this does not remove the need to apply common sense."""

import fileinput
import re
import sys

from .backend import mock
from . import plugins
from .plugins import detect

def check_line(line, include_oids):
	match = re.match(r'^([0-9.]+?)\s*=', line)
	if not match:
		raise ValueError("non-assignment line: %r" % line)
	oid = match.groups()[0]
	oid = mock.parse_oid(oid)
	return any(plugins.oid_startswith(oid, checkoid)
				for checkoid in include_oids)

def main():
	for line in fileinput.input():
		if check_line(line, detect.all_oids):
			sys.stdout.write(line)

if __name__ == "__main__":
	main()
