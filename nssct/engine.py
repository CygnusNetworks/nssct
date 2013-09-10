# -*- encoding: utf-8 -*-

import functools
import logging

import pysnmp.proto.rfc1905

from . import backend
from . import cache
from . import future

logger = logging.getLogger(__name__)

class EngineError(Exception):
	pass

class NoSuchObjectError(EngineError):
	pass

class EndOfMibError(EngineError):
	pass

class AbstractEngine(object):
	"""An engine encapsulates the process of retrieving objects from a SNMP
	agent. It supports GET and GETNEXT operations and may be turning them into
	GETBULK operations internally. To use the engine schedule a number of GET
	and GETNEXT queries using the respective methods. Then issue a call to the
	step method. Some futures are now completed and can issue further GET and
	GETNEXT queries in their callbacks. Issue step calls until it returns
	False signalling the completion of all returned futures."""
	def __init__(self):
		pass

	def get(self, oid):
		"""
		@returns: a Future returning the object associated with the given oid
		@raises NoSuchObjectError:
		@raises EndOfMibError:
		"""
		raise NotImplementedError

	def getnext(self, oid):
		"""
		@returns: a Future returning a pair of the next greater oid and its
				value
		@raises EndOfMibError:
		"""
		raise NotImplementedError

	def step(self):
		"""Does some work towards completing Futures returned from get and
		getnext.
		@rtype: bool
		@returns: True if step should be called again
		"""
		raise NotImplementedError


def check_mib_value(value):
	if isinstance(value, pysnmp.proto.rfc1905.NoSuchObject):
		raise NoSuchObjectError
	if isinstance(value, pysnmp.proto.rfc1905.EndOfMibView):
		raise EndOfMibError
	return value

def check_mib_next_pair(pair):
	if isinstance(pair[1], pysnmp.proto.rfc1905.EndOfMibView):
		raise EndOfMibError
	return pair

class SimpleEngine(AbstractEngine):
	"""A synchronous engine turning every question into a direct call to the
	backend."""
	def __init__(self, back):
		AbstractEngine.__init__(self)
		self.backend = back

	def get(self, oid):
		logger.debug("%r: get %r", self.backend, oid)
		fut = future.Future()
		future.complete_with(fut, lambda oid=oid:
				check_mib_value(self.backend.get(oid)))
		return fut

	def getnext(self, oid):
		logger.debug("%r: getnext %r", self.backend, oid)
		fut = future.Future()
		future.complete_with(fut, lambda oid=oid:
				check_mib_next_pair(self.backend.getnext(oid)))
		return fut

	def step(self):
		return False


class CachingEngine(AbstractEngine):
	"""An engine caching the results of another engine."""
	def __init__(self, engine):
		AbstractEngine.__init__(self)
		self.engine = engine
		self.cache = cache.ObjectCache()
		self.pendingget = {}
		self.pendingnext = {}
		if hasattr(engine, "setcache"):
			engine.setcache(self)

	def _cacheget(self, oid, fut):
		exc = fut.exception()
		if exc:
			if isinstance(exc, EndOfMibError):
				self.storeend(oid)
			return  # we cannot cache exceptions, includes NoSuchObject
		value = fut.result()
		logger.debug("storing %r set %r", oid, value)
		self.cache.set(oid, value)
		try:
			del self.pendingget[oid]
		except KeyError:
			pass

	def get(self, oid):
		oid = tuple(oid)
		try:
			futvalue = self.pendingget[oid]
		except KeyError:
			pass
		else:
			logger.debug("get %r in pending cache", oid)
			return futvalue
		try:
			value = self.cache.get(oid)
		except cache.NotCached:
			logger.debug("get %r not in cache", oid)
			futvalue = self.engine.get(oid)
			futvalue.add_done_callback(functools.partial(self._cacheget, oid))
			return futvalue
		else:
			fut = future.Future()
			future.complete_with(fut, functools.partial(check_mib_value, value))
			return fut

	def _cachenext(self, oid, futnext):
		exc = futnext.exception()
		if exc:
			if isinstance(exc, EndOfMibError):
				self.storeend(oid)
			return  # we cannot cache other exceptions
		noid, value = futnext.result()
		self.storenext(oid, noid, value)
		try:
			del self.pendingnext[oid]
		except KeyError:
			pass

	def getnext(self, oid):
		oid = tuple(oid)
		try:
			futvalue = self.pendingnext[oid]
		except KeyError:
			pass
		else:
			logger.debug("next %r in pending cache", oid)
			return futvalue
		try:
			noid, value = self.cache.getnext(oid)
		except cache.NotCached:
			logger.debug("next %r not in cache", oid)
			futnext = self.engine.getnext(oid)
			self.pendingnext[oid] = futnext
			futnext.add_done_callback(functools.partial(self._cachenext, oid))
			return futnext
		else:
			fut = future.Future()
			future.complete_with(fut, functools.partial(check_mib_next_pair, (noid, value)))
			return fut

	def storenext(self, oid, noid, value):
		logger.debug("storing %r next %r value %r", oid, noid, value)
		self.cache.setnextvalue(oid, noid, value)

	def storeend(self, oid):
		logger.debug("storing end %r", oid)
		self.cache.setend(oid)

	def step(self):
		return self.engine.step()


def prev_oid(oid):
	"""Return an OID that is minimally smaller than the given OID."""
	assert len(oid)
	if oid[-1] == 0:
		return oid[:-1]
	return oid[:-1] + (oid[-1] - 1,)


class BulkEngine(AbstractEngine):
	"""An engine that collects requests and turns them into bulk requests when
	the step method is invoked."""
	def __init__(self, back, lookahead=0, bulkmax=64):
		AbstractEngine.__init__(self)
		self.backend = back
		self.cache = None
		self.pendingget = []
		self.pendingnext = []
		self.maxrep = 1 + lookahead
		self.bulkmax = bulkmax

	def setcache(self, objcache):
		self.cache = objcache

	def get(self, oid):
		fut = future.Future()
		self.pendingget.append((oid, fut))
		return fut

	def getnext(self, oid):
		fut = future.Future()
		self.pendingnext.append((oid, fut))
		return fut

	def step(self):
		completions = []
		maxrep = self.maxrep if self.cache else 1
		if len(self.pendingnext) == 0:
			if len(self.pendingget) == 0:
				logger.debug("nothing to do")
				return False
			if len(self.pendingget) == 1:
				oid, fut = self.pendingget.pop(0)
				logger.debug("single get query for %r", oid)
				future.complete_with(fut, lambda oid=oid:
						check_mib_value(self.backend.get(oid)))
				return bool(self.pendingget) or bool(self.pendingnext)
		if maxrep <= 1 and len(self.pendingnext) == 1 and len(self.pendingget) == 0:
			oid, fut = self.pendingnext.pop(0)
			logger.debug("single next query for %r", oid)
			future.complete_with(fut, lambda oid=oid:
					check_mib_next_pair(self.backend.getnext(oid)))
			return bool(self.pendingget) or bool(self.pendingnext)

		oids = [prev_oid(oid) for oid, _ in self.pendingget[:self.bulkmax]]
		nonrep = len(oids)
		noids = [oid for oid, _ in self.pendingnext[:self.bulkmax - nonrep]]
		logger.debug("bulk getting nonrep %r and %d rep %r", oids, maxrep, noids)
		result = self.backend.getbulk(oids + noids, nonrep, maxrep)
		logger.debug("bulk result %r", result)
		# processing up to nonrep items
		while result and self.pendingget:
			qoid, fut = self.pendingget.pop(0)
			noid, value = result.pop(0)
			logger.debug("bulk processing %r queried %r result %r", noid, qoid, value)
			if qoid < noid:
				logger.debug("bulk query %r smaller than result %r, masking to NoSuchObject", qoid, noid)
				completions.append((fut.set_exception, NoSuchObjectError()))
				if self.cache:
					self.cache.storenext(prev_oid(qoid), noid, value)
			elif isinstance(value, pysnmp.proto.rfc1905.EndOfMibView):
				logger.debug("bulk found endofmib at %r", noid)
				completions.append((fut.set_exception, EndOfMibError()))
				if self.cache:
					self.cache.storeend(noid)
			elif qoid != noid:
				completions.append((fut.set_exception, backend.BackendError("bad bulk result queried %r != %r returned" % (qoid, noid))))
			else:
				completions.append((fut.set_result, value))
				if self.cache:
					self.cache.storenext(prev_oid(qoid), noid, value)

		# processing the first row of len(oids) - nonrep items
		oids, noids = noids, []
		logger.debug("processing first row of length %d with %d results left", len(oids), len(result))
		while result and oids:
			oids.pop(0)  # only for counting
			qoid, fut = self.pendingnext.pop(0)
			noid, value = result.pop(0)
			if isinstance(value, pysnmp.proto.rfc1905.EndOfMibView):
				logger.debug("bulk processing next %r is endofmib", qoid)
				completions.append((fut.set_exception, EndOfMibError()))
			else:
				logger.debug("bulk processing next %r is %r value %r", qoid, noid, value)
				completions.append((fut.set_result, (noid, value)))
			noids.append(noid)
		if self.cache:
			# processing the remainig maxrep - 1 rows
			oids, noids = noids, []
			while result and oids:
				while result and oids:
					oid = oids.pop(0)
					noid, value = result.pop(0)
					if isinstance(value, pysnmp.proto.rfc1905.EndOfMibView):
						logger.debug("bulk caching end of mib at %r", noid)
						self.cache.storeend(noid)
					else:
						logger.debug("bulk caching next %r is %r value %r", oid, noid, value)
						self.cache.storenext(oid, noid, value)
					noids.append(noid)
				oids, noids = noids, []
		logger.debug("bulk signalling %d futures", len(completions))
		for setter, value in completions:
			setter(value)
		return bool(self.pendingget) or bool(self.pendingnext)
