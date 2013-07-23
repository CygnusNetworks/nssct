# -*- encoding: utf-8 -*-

import decimal

from .. import future

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
def snmpwalk(controller, oid):
	"""
	@returns: a list of variable binding pairs (as the result of the Future)
	"""
	baseoid = oid
	lastoid = None
	varbinds = []
	while True:
		oid, value = (yield controller.engine.getnext(oid))
		if not oid_startswith(oid, baseoid):
			break
		if lastoid and lastoid >= oid:
			break
		varbinds.append((oid, value))
		lastoid = oid
	future.return_(varbinds)

sysObjectID = (1, 3, 6, 1, 2, 1, 1, 2, 0)
all_oids.add(sysObjectID)
