# -*- encoding: utf-8 -*-

import io
import logging
import logging.handlers
import sys
import traceback

if str is bytes:
	StringIO = io.BytesIO
else:
	StringIO = io.StringIO

class ExceptionFormatter(logging.Formatter):
	"""A formatter that looks at Python3-ish __traceback__ and __cause__
	attributes on exceptions and prints them in addition to the normal
	traceback."""
	def formatException(self, exc_info):
		seen = set()
		sio = StringIO()
		type_, exception, trace = exc_info
		while True:
			if id(exception) in seen:
				sio.write("circular cause sequence\n")
				break
			seen.add(id(exception))
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
			if exception.__cause__ is None:
				break
			sio.write("caused by\n")
			exception = exception.__cause__
			type_ = type(exception)
			trace = None
		return sio.getvalue().rstrip("\n")

loglevels = dict(
		DEBUG=logging.DEBUG,
		INFO=logging.INFO,
		WARNING=logging.WARNING,
		ERROR=logging.ERROR,
		CRITICAL=logging.CRITICAL)

def add_log_options(parser):
	group = parser.add_argument_group("logging", "configuration of log messages")
	group.add_argument("--level",
						choices=loglevels.keys(),
						default="DEBUG",
						help="specify log level")
	group.add_argument("--syslog",
						nargs='?',
						choices=logging.handlers.SysLogHandler.facility_names.keys(),
						default=None,
						const="daemon",
						metavar="FACILITY",
						help="Log to syslog instead of stderr. Use given facility or %(const)s.")

def setup_logging(namespace):
	logger = logging.getLogger("nssct")
	logger.setLevel(loglevels[namespace.level])
	facility = namespace.syslog
	if facility is None:
		handler = logging.StreamHandler(sys.stderr)
		fmt = logging.BASIC_FORMAT
	else:
		handler = logging.handlers.SysLogHandler(address="/dev/log", facility=facility)
		fmt = "nssct[%(process)d]: %(levelname)s:%(name)s:%(lineno)d: %(message)s"
	handler.setFormatter(ExceptionFormatter(fmt))
	logger.addHandler(handler)
