# -*- encoding: utf-8 -*-

import decimal

from .. import future
from .. import engine

try:
	long
except NameError:
	long = int  # pylint: disable=W0622

all_oids = set()

def native_noop_plugin(*_):
	fut = future.Future()
	fut.set_result(None)
	return fut


@future.coroutine
def noop_plugin(*_):
	return iter(())  # tricky, be a generator, yield nothing


def as_decimal(intval, factor=1):
	"""
	@param intval: an integer-like value
	@param factor: a literal to be passed to Decimal
	@rtype: Decimal
	@returns: a Decimal representation of intval * factor retaining precision

	>>> as_decimal(20, "0.5")
	Decimal('10.0')
	"""
	return decimal.Decimal(long(intval)) * decimal.Decimal(factor)


def oid_startswith(oid, initialoid):
	"""Check whether oid starts with initialoid."""
	return oid[:len(initialoid)] == initialoid


@future.coroutine
def snmpwalk(controller, baseoid, startoid=None):
	"""Walk over all oids, that start with baseoid using getnext queries and
	use startoid as the first oid. The resulting future returns a tuple of
	(oid, value, fut) or None, if there are no more rows. The returned future
	gives the next row and so on. Typical usage in a coroutine:

	fut = snmpwalk(controller, baseoid)
	while (yield fut):
		oid, value, fut = fut.result()
		# do something with oid and value
	"""
	if startoid is None:
		startoid = baseoid
	try:
		nextoid, value = (yield controller.engine.getnext(startoid))
	except engine.EndOfMibError:
		future.return_(None)
	if not oid_startswith(nextoid, baseoid):
		future.return_(None)
	future.return_((nextoid, value, snmpwalk(controller, baseoid, nextoid)))


sysObjectID = (1, 3, 6, 1, 2, 1, 1, 2, 0)
all_oids.add(sysObjectID)
