#!/usr/bin/python

from setuptools import setup

setup(
		name="nssct",
		version="0.18",
		author="Helmut Grohne",
		author_email="h.grohne@cygnusnetworks.de",
		maintainer="Cygnus Networks GmbH",
		maintainer_email="info@cygnusnetworks.de",
		license="GPL-2",
		packages=["nssct", "nssct.backend", "nssct.plugins"],
		test_suite="unittest2.collector",
		entry_points=dict(console_scripts=["nssct=nssct.main:main"]),
	)
