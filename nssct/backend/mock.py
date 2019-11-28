# -*- encoding: utf-8 -*-

import binascii
import re

import pysnmp.proto.rfc1902
import pysnmp.proto.rfc1905

from .. import backend
from .. import cache

try:
	long
except NameError:
	long = int  # pylint: disable=W0622


def parse_oid(oid):
	"""
	>>> parse_oid(".1.2.3")
	(1, 2, 3)
	"""
	oid = oid.split(".")
	if oid and not oid[0]:
		oid.pop(0)
	oid = map(int, oid)
	return tuple(oid)


def parse_hexstring(string):
	"""
	>>> bytes(parse_hexstring("66 6f 6f")) == b"foo"
	True
	"""
	string = string.replace(" ", "")
	if not isinstance(string, bytes):
		string = string.encode("ascii")
	return pysnmp.proto.rfc1902.OctetString(binascii.unhexlify(string))


def parse_timeticks(string):
	match = re.search(r'\((\d+)\)', string)
	if match is None:
		raise ValueError("invalid timeticks value %r" % string)
	return pysnmp.proto.rfc1902.TimeTicks(long(match.groups()[0]))


def parse_integer(string):
	match = re.search(r'\(?(\d+)\)?', string)
	if match is None:
		raise ValueError("invalid integer value %r" % string)
	return pysnmp.proto.rfc1902.Integer(long(match.groups()[0]))

type_map = {
		"Counter32":	lambda s: pysnmp.proto.rfc1902.Counter32(long(s)),
		"Counter64":	lambda s: pysnmp.proto.rfc1902.Counter64(long(s)),
		"Gauge32":		lambda s: pysnmp.proto.rfc1902.Gauge32(long(s)),
		"Hex-STRING":   parse_hexstring,
		"INTEGER":		parse_integer,
		"IpAddress":	pysnmp.proto.rfc1902.IpAddress,
		"OID":			lambda s: pysnmp.proto.rfc1902.ObjectName(parse_oid(s)),
		"Timeticks":	parse_timeticks,
}


def parse_snmpwalk_line(line):
	"""
	@type line: str
	@returns: (oid, object)
	@raises ValueError: when the parse fails

	>>> parse_snmpwalk_line(".1.2 = INTEGER: 3")[1] == pysnmp.proto.rfc1902.Integer(3)
	True
	>>> bytes(parse_snmpwalk_line('.1.3 = ""')[1]) == b""
	True
	>>> parse_snmpwalk_line('.1.4 = OID: .3.4')[1] == pysnmp.proto.rfc1902.ObjectName("3.4")
	True
	"""
	match = re.match(r'^([0-9.]+?)\s*=\s*(.*?)\s*$', line)
	if not match:
		raise ValueError("non-assignment line: %r" % line)
	oid, value = match.groups()
	oid = parse_oid(oid)
	if ':' in value:
		match = re.match(r'(.*?):\s*(.*)', value)
		if not match:
			raise ValueError("untagged value: %r" % value)
		kind, value = match.groups()
		try:
			conv = type_map[kind]
		except KeyError:
			raise ValueError("unknown kind: %r" % kind)
		else:
			value = conv(value)
	elif value == '""':
		value = pysnmp.proto.rfc1902.OctetString("")
	else:
		raise ValueError("unknown special value: %r" % value)
	return (oid, value)


def parse_snmpwalk(lineiterable):
	"""
	@param lineiterable: an iterable yielding lines such as a file object
	@returns: a generator yielding (oid, value) pairs
	@raises ValueError: for parse errors
	"""
	for line in lineiterable:
		yield parse_snmpwalk_line(line)


def cache_snmpwalk(obj):
	"""
	@param obj: a filename or file-like
	@rtype: ObjectCache
	"""
	if isinstance(obj, str):
		with open(obj) as fhandle:
			return cache.ObjectCache.frompairs(parse_snmpwalk(fhandle))
	return cache.ObjectCache.frompairs(parse_snmpwalk(obj))


class MockBackend(backend.BackendBase):
	def __init__(self, snmpwalklog):
		backend.BackendBase.__init__(self)
		self.cache = cache_snmpwalk(snmpwalklog)

	def get(self, oid):
		try:
			return self.cache.get(oid)
		except cache.NotCached:
			return pysnmp.proto.rfc1905.noSuchObject

	def getnext(self, oid):
		return self.cache.getnext(oid)
