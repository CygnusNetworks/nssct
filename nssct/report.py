# -*- encoding: utf-8 -*-

import decimal

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3

states = {}
for name in "OK WARNING CRITICAL UNKNOWN".split():
	states[name] = globals()[name]
	states[globals()[name]] = name
del name  # pylint: disable=W0631


class PerfRange(object):
	"""
	@see http://nagiosplug.sourceforge.net/developer-guidelines.html
	"""
	def __init__(self, high, low=0, invert=False):
		"""A PerfRange basically is an interval from low to high inclusively.
		A value being in this interval is considered a good thing iff the
		range is not inverted.
		"""
		assert high is None or low is None or low <= high
		self.high = high
		self.low = low
		self.invert = invert

	@classmethod
	def fromstr(cls, s):
		"""
		@type s: str
		@rtype: PerfRange

		>>> PerfRange.fromstr("@10.1")
		PerfRange(Decimal('10.1'), Decimal('0'), True)
		>>> PerfRange.fromstr("10.12")
		PerfRange(Decimal('10.12'))
		>>> PerfRange.fromstr("~:10.0")
		PerfRange(Decimal('10.0'), None)
		>>> PerfRange.fromstr("10:")
		PerfRange(None, Decimal('10'))
		"""
		invert = False
		if s.startswith("@"):
			s = s[1:]
			invert = True
		low, high = s.split(":") if ":" in s else (decimal.Decimal(0), decimal.Decimal(s))
		low = None if low == "~" else decimal.Decimal(low)
		high = None if high == "" else decimal.Decimal(high)
		return cls(high, low, invert)

	@classmethod
	def fromany(cls, obj):
		"""
		@param obj: may be a PerfRange, a numeric data type specifying the
				high limit and setting the low limit to 0, None to have no
				limits at all, or a valid string representation
		@rtype: PerfRange
		"""
		if obj is None:
			return cls(None, None)
		if isinstance(obj, PerfRange):
			return cls(obj.high, obj.low, obj.invert)
		if isinstance(obj, str) or isinstance(obj, unicode):
			return cls.fromstr(obj)
		return cls(obj)

	def alert(self, value):
		"""Checks whether the given value resides outside this range.

		@type value: int or float or decimal.Decimal
		@rtype: bool

		>>> PerfRange(10).alert(11)
		True
		>>> PerfRange(None, 0, True).alert(-1)
		False
		"""
		return ((self.low is not None and value < self.low) or
				(self.high is not None and value > self.high)) ^ self.invert

	def __str__(self):
		"""
		>>> str(PerfRange(10, 0, True))
		'@10'
		>>> str(PerfRange(10))
		'10'
		>>> str(PerfRange(10, None))
		'~:10'
		>>> str(PerfRange(None, 10))
		'10:'
		>>> str(PerfRange(decimal.Decimal('10.0')))
		'10.0'
		>>> str(PerfRange(None, None))
		''
		"""
		ret = "" if self.high is None else str(self.high)
		if self.low is None:
			if self.high is None and not self.invert:
				return ""
			ret = "~:" + ret
		elif self.low != 0:
			ret = "%s:%s" % (self.low, ret)
		if self.invert:
			ret = "@" + ret
		return ret

	def __repr__(self):
		if self.invert:
			return "PerfRange(%r, %r, %r)" % (self.high, self.low, self.invert)
		if self.low != 0:
			return "PerfRange(%r, %r)" % (self.high, self.low)
		return "PerfRange(%r)" % (self.high,)


def quote(s):
	"""
	>>> quote('spam')
	'spam'
	>>> quote("eggs' spam")
	"'eggs'' spam'"
	"""
	if s.replace("_", "").isalnum():
		return s
	return "'%s'" % s.replace("'", "''")


class Alert(object):
	"""A message with an alert state.
	@ivar state: is the state number
	@ivar message: is the message
	"""
	__slots__ = ("state", "message")

	def __init__(self, state, message):
		"""
		@type state: int
		@param state: one of (OK, WARNING, CRITICAL, UNKNOWN)
		@type message: str
		"""
		self.state = state
		self.message = message

	def __str__(self):
		return "%s - %s" % (states[self.state], self.message)

	def __repr__(self):
		return "Alert(%d, %r)" % (self.state, self.message)


class PerfMeasure(object):
	def __init__(self, label, uom="", warn=None, crit=None, minval=None, maxval=None):
		"""
		@type label: str
		@type uom: str
		@param uom: one out of "" (no unit), "%" (percentage), "s", "ms", "us" (time),
				"B", "KB", "MB", "TB", (size), "c" (monotonic counter)
		@param warn: see PerfRange.fromany
		@param crit: see PerfRange.fromany
		@type minval: int or float or decimal.Decimal or None
		@type maxval: int or float or decimal.Decimal or None
		"""
		self.label = label
		self.uom = uom
		self.warn = PerfRange.fromany(warn)
		self.crit = PerfRange.fromany(crit)
		self.minval = minval
		self.maxval = maxval

	def with_value(self, value):
		"""Create a PerfMetric from this measure and a value."""
		return PerfMetric(self.label, value, self.uom, self.warn, self.crit, self.minval, self.maxval)


class PerfMetric(PerfMeasure):
	"""A PerfMetric is a measured value in the context of a PerfMeasure."""
	def __init__(self, label, value, uom="", warn=None, crit=None, minval=None, maxval=None):
		"""
		@type label: str or PerfMeasure
		@param label: if this is a PerfMeasure, uom, warn, crit, minval and
				maxval are ignored
		@type value: int or float or decimal.Decimal
		@type uom: str
		@param uom: one out of "" (no unit), "%" (percentage), "s", "ms",
				"us" (time), "B", "KB", "MB", "TB", (size),
				"c" (monotonic counter)
		@param warn: see PerfRange.fromany
		@param crit: see PerfRange.fromany
		@type minval: int or float or decimal.Decimal or None
		@type maxval: int or float or decimal.Decimal or None
		"""
		if isinstance(label, PerfMeasure):
			uom = label.uom
			warn = label.warn
			crit = label.crit
			minval = label.minval
			maxval = label.maxval
			label = label.label
		PerfMeasure.__init__(self, label, uom, warn, crit, minval, maxval)
		self.value = value

	def state(self):
		"""
		@rtype: int
		"""
		if self.crit.alert(self.value):
			return CRITICAL
		elif self.warn.alert(self.value):
			return WARNING
		return OK

	def alert(self):
		"""
		@rtype: Alert
		"""
		return Alert(self.state(), "%s=%s%s" % (self.label, self.value, self.uom))

	def __str__(self):
		"""
		>>> str(PerfMetric("spam", 10, "%"))
		'spam=10%'
		"""
		tail = (self.warn, self.crit, self.minval, self.maxval)
		tail = ";".join("" if v is None else str(v) for v in tail)
		return ("%s=%s%s;%s" % (quote(self.label), self.value, self.uom, tail)).rstrip(";")


class Collector(object):
	"""An object collecting Alerts and Metrics."""
	def __init__(self):
		self.metrics = []
		self.alerts = {}

	def add_alert(self, alert):
		self.alerts.setdefault(alert.state, []).append(alert)

	def add_metric(self, metric):
		self.metrics.append(metric)
		self.add_alert(metric.alert())

	def state(self):
		for st in (CRITICAL, WARNING, OK, UNKNOWN):
			if st in self.alerts:
				return st
		return UNKNOWN

	def summary(self):
		st = self.state()
		if st not in self.alerts:
			return Alert(st, "no checks")
		if len(self.alerts[st]) > 1:
			return Alert(st, "%d subchecks" % (len(self.alerts[st])))
		return self.alerts[st][0]

	def __str__(self):
		main = self.summary()
		parts = [main]
		for st in (CRITICAL, WARNING, OK, UNKNOWN):
			for alert in self.alerts.get(st, ()):
				if alert is main:
					continue
				parts.append(alert)
		result = "\n".join(map(str, parts))
		if not self.metrics:
			return result
		return "%s | %s" % (result, " ".join(map(str, self.metrics)))
