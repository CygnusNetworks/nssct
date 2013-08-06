# -*- encoding: utf-8 -*-

import cStringIO
import unittest

import nssct.walkfilter

class WalkfilterTests(unittest.TestCase):
	def test_check_line(self):
		assert nssct.walkfilter.check_line(".1.2.3 = foo", ((1, 2),))
		assert not nssct.walkfilter.check_line(".1.2.3 = bar", ((1, 1), (2, 2)))

	def test_check_stream(self):
		valid = ".1.3.6.1.2.1.1.2.0 = bar\n"
		inp = [".999.2.3 = foo\n", valid]
		outp = cStringIO.StringIO()
		nssct.walkfilter.check_stream(inp, outp)
		self.assertEqual(outp.getvalue(), valid)
