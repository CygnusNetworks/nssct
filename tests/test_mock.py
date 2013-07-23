import unittest
from StringIO import StringIO

import nssct.controller
import nssct.engine
import nssct.backend.mock
import nssct.plugins.detect
import nssct.report

class MockTests(unittest.TestCase):
	def test_undetected(self):
		dump = StringIO(".1.3.6.1.2.1.1.2.0 = OID: 0.1.2.3")
		backend = nssct.backend.mock.MockBackend(dump)
		engine = nssct.engine.SimpleEngine(backend)
		cont = nssct.controller.Controller(engine)
		collector = nssct.report.Collector()
		cont.run(collector, [nssct.plugins.detect.detect])
		self.assertEqual(cont.pending_plugins, [])
		self.assertIn(nssct.report.UNKNOWN, collector.alerts)
		self.assertIn("unknown device", collector.alerts[nssct.report.UNKNOWN][0].message)
