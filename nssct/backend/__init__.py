# -*- encoding: utf-8 -*-

class BackendError(Exception):
	pass

class BackendBase(object):
	"""The backend classes encapsulate the actual query invocation in a
	synchronous way that permits replaying captured snmp dumps.  """
	def __init__(self):
		pass

	def get(self, oid):
		"""Given an OID return the associated value.
		@type oid: (int,)
		@raises BackendError:
		"""
		raise NotImplementedError

	def getnext(self, oid):
		"""Given an OID return a pair of the next greater OID and the
		associated value.
		@type oid: (int,)
		@returns: (oid, value)
		@rtype: ((int,), object)
		@raises BackendError:
		"""
		raise NotImplementedError

	def getbulk(self, oids, nonrep, maxrep):
		"""Given a list of oids, do getnext queries for the first nonrep oids
		and do maxrep getnext queries for the remaining oids.

		The default implementation unless overriden is backed by the getnext
		method.

		@type oids: [(int,)]
		@param oids: a list of oids
		@type nonrep: int
		@param nonrep: a number from 0 to len(oids)
		@type maxrep: int
		@param maxrep: a positive number
		@rtype: [((int,), object)]
		"""
		res = []
		for oid in oids[:nonrep]:
			res.append(self.getnext(oid))
		oids, nextoids = oids[nonrep:], []
		for _ in range(maxrep):
			for oid in oids:
				noid, value = self.getnext(oid)
				nextoids.append(noid)
				res.append((noid, value))
			oids, nextoids = nextoids, []
		return res
