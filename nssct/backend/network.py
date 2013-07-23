# -*- encoding: utf-8 -*-

import logging

import pysnmp.entity.rfc3413.oneliner.cmdgen

from .. import backend
from .. import future

# We are using the naming conventions from pysnmp here, but pylint does not
# like cAmElCaSe.
# pylint: disable=C0103

logger = logging.getLogger(__name__)

def check_pysnmp_errors(errorIndication, errorStatus, errorIndex):
	if errorIndication:  # this is an object from pysnmp.proto.errind
		logger.error(errorIndication)
		raise future.attach_cause(backend.BackendError("pysnmp error: %s" % errorIndication), errorIndication)
	if errorStatus:
		raise backend.BackendError("pysnmp PDU error: %s (%d) at index %d" % (errorStatus.prettyPrint(), int(errorStatus), int(errorIndex)))


class NetworkBackend(backend.BackendBase):
	"""A backend that queries agents using SNMPv2c."""
	def __init__(self, agent, community, engine=None):
		"""
		@type agent: str or (str, int)
		@param agent: is the ip address or name of the agent. If a port is to
			be specified, it must be given as a tuple.
		@type community: str
		@param community: community string used to identify to the agent
		@type engine: None or pysnmp.entity.engine.SnmpEngine
		@raises socket.gaierror: if name resolution fails
		"""
		backend.BackendBase.__init__(self)
		if isinstance(agent, str):
			agent = (agent, 161)
		self.authdata = pysnmp.entity.rfc3413.oneliner.cmdgen.CommunityData("unused parameter", community)
		self.agent = pysnmp.entity.rfc3413.oneliner.cmdgen.UdpTransportTarget(agent)
		self.cmdgen = pysnmp.entity.rfc3413.oneliner.cmdgen.AsynCommandGenerator(engine)

	def get(self, oid):
		fut = future.Future()
		@future.future_completer(fut)
		def handle_get_result(sendRequestHandle, errorIndication, errorStatus, errorIndex, varBinds, oid):
			check_pysnmp_errors(errorIndication, errorStatus, errorIndex)
			if not varBinds:
				raise backend.BackendError("no variable bindings returned")
			retoid, retval = varBinds[0]
			if retoid != oid:
				raise backend.BackendError("requested oid %r, but got oid %r" % (oid, retoid))
			return retval
		self.cmdgen.asyncGetCmd(self.authdata, self.agent, (oid,), (handle_get_result, oid))
		self.cmdgen.snmpEngine.transportDispatcher.runDispatcher()
		return fut.result()

	def getnext(self, oid):
		fut = future.Future()
		@future.future_completer(fut)
		def handle_next_result(sendRequestHandle, errorIndication, errorStatus, errorIndex, varBinds, _):
			check_pysnmp_errors(errorIndication, errorStatus, errorIndex)
			if not varBinds:
				raise backend.BackendError("no variable bindings returned")
			if not varBinds[0]:
				raise backend.BackendError("the first row of variable bindings is empty")
			return varBinds[0][0]
		self.cmdgen.asyncNextCmd(self.authdata, self.agent, (oid,), (handle_next_result, None))
		self.cmdgen.snmpEngine.transportDispatcher.runDispatcher()
		return fut.result()

	def getbulk(self, oids, nonrep, maxrep):
		"""For the first nonrep oids, do a getnext query, then maxrep times do
		a getnext query for the remaining oids."""
		fut = future.Future()
		# The decorated function returns None and thereby tells pysnmp not to
		# continue requesting another bulkget.
		@future.future_completer(fut)
		def handle_bulk_result(sendRequestHandle, errorIndication, errorStatus, errorIndex, varBinds, params):
			check_pysnmp_errors(errorIndication, errorStatus, errorIndex)
			oids, nonrep = params
			if not varBinds:
				raise backend.BackendError("no variable bindings returned")
			# pysnmp prepends the nonrepeaters to every row
			retbinds = varBinds.pop(0)
			if len(retbinds) > len(oids):
				raise backend.BackendError("pysnmp returned too many bindings. requested %d got %d" % (len(oids), len(retbinds)))
			if len(retbinds) < len(oids):
				return retbinds
			for binds in varBinds:
				if len(binds) > len(oids):
					raise backend.BackendError("pysnmp returned too many bindings. requested %d got %d" % (len(oids), len(binds)))
				retbinds.extend(binds[nonrep:])
				if len(binds) < len(oids):
					return retbinds
			return retbinds
		self.cmdgen.asyncBulkCmd(self.authdata, self.agent, nonrep, maxrep, oids, (handle_bulk_result, (oids, nonrep)))
		self.cmdgen.snmpEngine.transportDispatcher.runDispatcher()
		return fut.result()
