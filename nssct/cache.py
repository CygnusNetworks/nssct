# -*- encoding: utf-8 -*-

import bisect
import functools

import pysnmp.proto.rfc1905

__all__ = ["NotCached", "EndOfMib", "ObjectCache"]


class NotCached(Exception):
	"""Raised from an ObjectCache to signal that the requested object was not
	found in the cache."""


class EndOfMib(Exception):
	"""Internal exception used to signal the last oid. This exception should
	not leave this module."""


@functools.total_ordering
class NextEntry(object):
	"""A NextEntry is an assertion that the next oid after oid is noid. It is
	ordered by oid, not considering noid.
	"""
	__slots__ = ("oid", "noid")

	def __init__(self, oid, noid):
		self.oid = oid
		self.noid = noid

	def __eq__(self, other):
		return self.oid == other.oid

	def __lt__(self, other):
		return self.oid < other.oid

	def __hash__(self):
		return hash(("NextEntry", self.oid, self.noid))

	def __repr__(self):
		return "%s(%r, %r)" % (self.__class__.__name__, self.oid, self.noid)

class ObjectCache(object):
	"""An unlimited cache for SNMP GET and GETNEXT queries.

	@type oids: {(int,): object}
	@ivar oids: a mapping from oid to value
	@type nexts: [((int,), (int,))]
	@ivar nexts: an ordered list of oid pairs. Each pair implies that a getnext
			query for the first oid results in the latter.
	@type last: (int,) or None
	@ivar last: the last available oid, if known
	"""
	def __init__(self):
		self.oids = {}
		self.nexts = []
		self.last = None

	def get(self, oid):
		"""
		@returns: the value stored for the given oid
		@raises NotCached:
		"""
		oid = tuple(oid)
		try:
			return self.oids[oid]
		except KeyError:
			pass
		i = bisect.bisect_left(self.nexts, NextEntry(oid, None))
		if i > 0:
			pair = self.nexts[i - 1]
			assert pair.oid < oid
			if oid < pair.noid:
				return pysnmp.proto.rfc1905.noSuchObject
		raise NotCached(oid)

	def _getnextpointer(self, oid):
		"""
		@rtype: int, NextEntry
		@returns: the index of the NextEntry and the NextEntry pair
				[p.oid, p.noid) containing the given oid
		@raises: NotCached
		@raises: EndOfMib
		"""
		oid = tuple(oid)
		if self.last and oid >= self.last:
			raise EndOfMib
		i = bisect.bisect_right(self.nexts, NextEntry(oid, None))
		assert i == len(self.nexts) or self.nexts[i].oid > oid
		if i == 0:
			raise NotCached(oid)
		i -= 1
		pair = self.nexts[i]
		assert pair.oid <= oid
		if pair.noid <= oid:
			raise NotCached(oid)
		return i, pair

	def getnext(self, oid):
		"""
		@returns: a pair of the next oid and its value or the requested oid and
				an EndOfMibView object
		@raises NotCached:
		"""
		try:
			noid = self._getnextpointer(oid)[1].noid
		except EndOfMib:
			return (oid, pysnmp.proto.rfc1905.EndOfMibView())
		else:
			return (noid, self.get(noid))

	def set(self, oid, value):
		"""Associate the given oid with the given value.

		>>> c = ObjectCache()
		>>> c.get((1, 2)) # doctest: +IGNORE_EXCEPTION_DETAIL
		Traceback (most recent call last):
			....
		NotCached:
		>>> c.set((1, 2), 'spam')
		>>> c.get((1, 2))
		'spam'
		"""
		self.oids[tuple(oid)] = value

	def setnext(self, oid, nextoid):
		"""Remember that the nextgreater oid than oid is nextoid. Any
		previously remembered next relations, that contradict the new one, are
		removed.

		>>> c = ObjectCache()
		>>> c.setnext((1, 2), (1, 4))
		>>> c.get((1, 3)) # doctest: +ELLIPSIS
		NoSuchObject(...)
		"""
		new = NextEntry(tuple(oid), tuple(nextoid))
		assert new.oid < new.noid

		# clear last if the end of the interval is behind it
		if self.last and self.last < new.noid:
			self.last = None

		i = bisect.bisect_left(self.nexts, new)

		# remove all NextEntries where oid is in the new interval
		while i < len(self.nexts) and self.nexts[i].oid < new.noid:
			assert new.oid <= self.nexts[i].oid
			self.nexts.pop(i)

		# remove all NextEntries where noid is in the interval
		i -= 1
		while i >= 0 and self.nexts[i].noid > new.oid:
			assert new.oid > self.nexts[i].oid
			if self.nexts[i].noid == new.noid:
				return  # self.nexts[i] covers new. There is nothing to be done.
			self.nexts.pop(i)
			i -= 1
		i += 1

		self.nexts.insert(i, new)

	def setnextvalue(self, oid, nextoid, nextvalue):
		"""Same as .setnext(oid, nextoid) and .set(nextoid, nextvalue).

		>>> c = ObjectCache()
		>>> c.setnextvalue((1, 2), (3, 4), 'a')
		>>> c.getnext((2, 3))
		((3, 4), 'a')
		>>> c.getnext((1, 2))
		((3, 4), 'a')
		>>> c.setnextvalue((5, 6), (7, 8), 'b')
		>>> c.getnext((6, 7))
		((7, 8), 'b')
		>>> c.setnextvalue((6, 8), (7, 9), 'c')
		>>> c.getnext((6, 7)) # doctest: +IGNORE_EXCEPTION_DETAIL
		Traceback (most recent call last):
			....
		NotCached:
		>>> c.setnextvalue((0, 1), (2, 1), 'd')
		>>> c.getnext((2, 3)) # doctest: +IGNORE_EXCEPTION_DETAIL
		Traceback (most recent call last):
			....
		NotCached:
		>>> c.setnextvalue((1, 2), (2, 1), 'd')
		>>> c.getnext((0, 1))
		((2, 1), 'd')
		"""
		self.setnext(oid, nextoid)
		self.set(nextoid, nextvalue)

	def setend(self, oid):
		"""Remember that no oids follow the given oid. A lower end from a
		previous setend call may be retained.

		>>> c = ObjectCache()
		>>> c.getnext((1, 2)) # doctest: +IGNORE_EXCEPTION_DETAIL
		Traceback (most recent call last):
			....
		NotCached:
		>>> c.setend((1, 1))
		>>> c.getnext((1, 2)) # doctest: +ELLIPSIS
		((1, 2), EndOfMibView(...))
		"""
		oid = tuple(oid)
		if self.last is not None and self.last < oid:
			return

		# remove all NextEntries where noid is bigger than the end
		while self.nexts and self.nexts[-1].noid > oid:
			self.nexts.pop()

		self.last = oid

	def invalidate(self, oid):
		"""Punch a hole into the cache. Remove value associated with the given
		and discard the NextEntry containing the given oid."""
		oid = tuple(oid)
		try:
			del self.oids[oid]
		except KeyError:
			pass
		try:
			i = self._getnextpointer(oid)[0]
		except EndOfMib:
			self.last = None
		except NotCached:
			pass
		else:
			self.nexts.pop(i)

	def nextfromset(self):
		"""Clear the next cache and populate it from pairs passed to set."""
		self.nexts = []
		last = ()
		for oid in sorted(self.oids.keys()):
			self.setnext(last, oid)
			last = oid
		self.setend(last)

	@classmethod
	def frompairs(cls, pairs):
		"""Given an iterator yielding (oid, value) pairs, construct an
		ObjectCache containing all pairs and compute the next values from
		those pairs as well. The order of the iterable does not matter."""
		self = cls()
		for oid, value in pairs:
			self.set(oid, value)
		self.nextfromset()
		return self
