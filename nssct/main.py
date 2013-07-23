# -*- encoding: utf-8 -*-

import cStringIO
import logging
import socket
import sys
import traceback

import argparse

from . import controller
from . import engine
from .plugins import detect
from . import report
from .backend import mock, network

loglevels = dict(
		DEBUG=logging.DEBUG,
		INFO=logging.INFO,
		WARNING=logging.WARNING,
		ERROR=logging.ERROR,
		CRITICAL=logging.CRITICAL)

class ExceptionFormatter(logging.Formatter):
	def formatException(self, exc_info):
		sio = cStringIO.StringIO()
		type_, exception, trace = exc_info
		while True:
			if trace is not None:
				traceback.print_exception(type_, exception, trace, None, sio)
				if hasattr(exception, "__traceback__"):
					sio.write("original traceback\n")
					traceback.print_exception(type_, exception, exception.__traceback__, None, sio)
			elif hasattr(exception, "__traceback__"):
				traceback.print_exception(type_, exception, exception.__traceback__, None, sio)
			else:
				sio.write("%s\n" % exception)
			if not hasattr(exception, "__cause__"):
				break
			sio.write("caused by\n")
			exception = exception.__cause__
			type_ = type(exception)
			trace = None
		return sio.getvalue().rstrip("\n")

def setup_logging(levelname):
	rootlogger = logging.getLogger()
	rootlogger.setLevel(loglevels[levelname])
	handler = logging.StreamHandler(sys.stderr)
	handler.setFormatter(ExceptionFormatter(logging.BASIC_FORMAT))
	rootlogger.addHandler(handler)

class CustomParser(argparse.ArgumentParser):
	def exit(self, status=0, message=None):
		if message:
			sys.stderr.write(message)
		sys.exit(report.UNKNOWN)  # We must mask every exit to UNKNOWN for nagios.

def finish(collector):
	sys.stdout.write(str(collector) + "\n")
	sys.exit(collector.state())


def main():
	parser = CustomParser()
	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument("--mock")
	group.add_argument("--agent")
	parser.add_argument("--community", default="public")
	parser.add_argument("--level", choices=loglevels.keys(), default="DEBUG")
	parser.add_argument("--bulk", nargs='?', type=int, default=-1, const=0)
	parser.add_argument("--cache", action="store_true")
	args = parser.parse_args()
	setup_logging(args.level)
	collector = report.Collector()
	if args.mock:
		backend = mock.MockBackend(args.mock)
	else:
		try:
			backend = network.NetworkBackend(args.agent, args.community)
		except socket.gaierror as err:
			collector.add_alert(report.Alert(report.UNKNOWN, "resolution of %s failed: %s" % (args.agent, err.strerror)))
			finish(collector)
	if args.bulk >= 0:
		eng = engine.BulkEngine(backend, lookahead=args.bulk)
	else:
		eng = engine.SimpleEngine(backend)
	if args.cache:
		eng = engine.CachingEngine(eng)
	control = controller.Controller(eng)
	control.run(collector, [detect.detect])
	finish(collector)

if __name__ == "__main__":
	main()
