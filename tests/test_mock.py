import unittest
from StringIO import StringIO

import pysnmp.proto.rfc1905

import nssct.controller
import nssct.engine
import nssct.backend.mock
import nssct.plugins.detect
import nssct.report

class MockTests(unittest.TestCase):
	def setUp(self):
		dump = StringIO(".1.3.6.1.2.1.1.2.0 = OID: 0.1.2.3")
		self.backend = nssct.backend.mock.MockBackend(dump)

	def test_undetected(self):
		engine = nssct.engine.SimpleEngine(self.backend)
		cont = nssct.controller.Controller(engine)
		collector = nssct.report.Collector()
		cont.run(collector, [nssct.plugins.detect.detect])
		self.assertEqual(cont.pending_plugins, [])
		self.assertIn(nssct.report.UNKNOWN, collector.alerts)
		self.assertIn("unknown device", collector.alerts[nssct.report.UNKNOWN][0].message)

	def test_nosuchobject(self):
		result = self.backend.get((1, 2, 3, 4))
		self.assertIsInstance(result, pysnmp.proto.rfc1905.NoSuchObject)
