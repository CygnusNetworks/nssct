import unittest

import nssct.controller
import nssct.engine
import nssct.plugins

class NoopTests(unittest.TestCase):
	def setUp(self):
		self.controller = nssct.controller.Controller(nssct.engine.SimpleEngine(None))

	def test_native_noop(self):
		self.controller.run(None, [nssct.plugins.native_noop_plugin])
		self.assertEqual(self.controller.pending_plugins, [])

	def test_gen_noop(self):
		self.controller.run(None, [nssct.plugins.noop_plugin])
		self.assertEqual(self.controller.pending_plugins, [])
