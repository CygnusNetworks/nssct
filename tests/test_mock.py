import io
import unittest

import pysnmp.proto.rfc1905

import nssct.controller
import nssct.engine
import nssct.backend.mock
import nssct.plugins.detect
import nssct.report

class MockTests(unittest.TestCase):
	def setUp(self):
		dump = io.StringIO(u".1.3.6.1.2.1.1.2.0 = OID: 0.1.2.3")
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

	def test_simple_nosuchobject(self):
		engine = nssct.engine.SimpleEngine(self.backend)
		res = engine.get((1, 2, 3, 4))
		engine.step()
		self.assertTrue(res.done())
		self.assertRaises(nssct.engine.NoSuchObjectError, res.result)

	def test_bulk_nosuchobject(self):
		engine = nssct.engine.BulkEngine(self.backend)
		# non-bulk
		res = engine.get((1, 2, 3, 4))
		engine.step()
		self.assertTrue(res.done())
		self.assertRaises(nssct.engine.NoSuchObjectError, res.result)
		# need to do two queries to trigger bulk mode
		res1 = engine.get((1, 2, 3, 4))
		res2 = engine.get((1, 2, 3, 4))
		engine.step()
		self.assertTrue(res1.done())
		self.assertRaises(nssct.engine.NoSuchObjectError, res1.result)
