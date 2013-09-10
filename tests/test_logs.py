# -*- encoding: utf-8 -*-

import glob
import logging
import unittest

import nssct.backend.mock
import nssct.controller
import nssct.engine
import nssct.log
import nssct.plugins.detect
import nssct.report

class CheckHandler(logging.Handler):
	def __init__(self):
		logging.Handler.__init__(self)
		self.formatter = nssct.log.ExceptionFormatter("%(message)s")

	def emit(self, record):
		if record.levelno > logging.DEBUG:
			raise AssertionError("non-debug message: %s" % self.formatter.format(record))
		if "swallow" in record.msg.lower() and "exception" in record.msg.lower():
			raise AssertionError("exception message: %s" % self.formatter.format(record))

class LogTests(unittest.TestCase):
	methods = ("verify_simple", "verify_bulk", "verify_simple_cache", "verify_bulk_cache")

	def __init__(self, method, filename):
		unittest.TestCase.__init__(self, method)
		self.method = method
		self.filename = filename

	def shortDescription(self):
		return "%s:%s" % (self.method, self.filename)

	def setUp(self):
		self.handler = CheckHandler()
		logging.getLogger("nssct").addHandler(self.handler)
		logging.getLogger("nssct").setLevel(logging.DEBUG)
		self.backend = nssct.backend.mock.MockBackend(self.filename)
		self.collector = nssct.report.Collector()

	def tearDown(self):
		logging.getLogger("nssct").removeHandler(self.handler)

	def run_plugin(self):
		self.controller = nssct.controller.Controller(self.engine)
		self.controller.run(self.collector, [nssct.plugins.detect.detect])
		self.assertEqual(self.controller.pending_plugins, [])
		self.collector.state()

	def verify_simple(self):
		self.engine = nssct.engine.SimpleEngine(self.backend)
		self.run_plugin()

	def verify_bulk(self):
		self.engine = nssct.engine.BulkEngine(self.backend)
		self.run_plugin()

	def verify_simple_cache(self):
		self.engine = nssct.engine.SimpleEngine(self.backend)
		self.engine = nssct.engine.CachingEngine(self.engine)
		self.run_plugin()

	def verify_bulk_cache(self):
		self.engine = nssct.engine.BulkEngine(self.backend)
		self.engine = nssct.engine.CachingEngine(self.engine)
		self.run_plugin()

def load_tests(loader, tests, ignore):
	suite = unittest.TestSuite()
	for filename in glob.glob("cases/*.log"):
		for method in LogTests.methods:
			suite.addTest(LogTests(method, filename))
	return suite
