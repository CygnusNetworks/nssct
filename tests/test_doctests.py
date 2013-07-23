import doctest
import unittest

import nssct.backend.mock
import nssct.cache
import nssct.plugins
import nssct.report

def load_tests(loader, tests, ignore):
	suite = unittest.TestSuite()
	suite.addTests(doctest.DocTestSuite(nssct.backend.mock))
	suite.addTests(doctest.DocTestSuite(nssct.cache))
	suite.addTests(doctest.DocTestSuite(nssct.plugins))
	suite.addTests(doctest.DocTestSuite(nssct.report))
	return suite
