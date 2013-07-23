# -*- encoding: utf-8 -*-

from .. import future
from .. import plugins
from .. import report
from . import brocade
from . import cisco
from . import hp

all_oids = set()
all_oids.update(plugins.all_oids)
all_oids.update(brocade.all_oids)
all_oids.update(cisco.all_oids)
all_oids.update(hp.all_oids)

allied_telesis = (1, 3, 6, 1, 4, 1, 207)

@future.coroutine
def detect(controller, collector):
	oid = (yield controller.engine.get(plugins.sysObjectID))
	if plugins.oid_startswith(oid, brocade.brcdIp):
		yield brocade.brocade_detect(controller, collector)
	elif plugins.oid_startswith(oid, cisco.cisco):
		yield cisco.cisco_detect(controller, collector)
	elif plugins.oid_startswith(oid, hp.hpmib):
		yield hp.hp_detect(controller, collector)
	elif plugins.oid_startswith(oid, allied_telesis):
		collector.add_alert(report.Alert(report.OK, "Allied Telesis does not report health"))
	else:
		collector.add_alert(report.Alert(report.UNKNOWN, "unknown device identified by %r" % oid))
