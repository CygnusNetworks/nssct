# -*- encoding: utf-8 -*-

from .. import future
from .. import plugins
from .. import report

all_oids = set()

hpmib = (1, 3, 6, 1, 4, 1, 11)

icfSensors = hpmib + (2, 3, 7, 8, 3)
all_oids.add(icfSensors)
icfSensorType = {1: "psu", 2: "fan", 3: "temp"}
hp_states = {
		1: (report.UNKNOWN, "unknown"),
		2: (report.CRITICAL, "bad"),
		3: (report.WARNING, "warning"),
		4: (report.OK, "good"),
		5: (report.UNKNOWN, "notPresent")
}

def hp_state(numeric):
	return hp_states.get(numeric, (report.CRITICAL, "unexpected code %d" % numeric))


hpicfSensorEntry = hpmib + (2, 14, 11, 1, 2, 6, 1)
all_oids.add(hpicfSensorEntry)

@future.coroutine
def hp_sensors_plugin(controller, collector):
	device_num = device_type = None
	for oid, value in (yield plugins.snmpwalk(controller, hpicfSensorEntry)):
		tail = oid[len(hpicfSensorEntry):]
		if tail[0] == 1:  # hpicfSensorIndex
			device_num = value
		elif tail[0] == 2:  # hpicfSensorObjectId
			if plugins.oid_startswith(value, icfSensors):
				device_type = icfSensorType.get(value[len(icfSensors)])
		elif tail[0] == 4:  # hpicfSensorStatus
			if device_num is not None and device_type is not None:
				state, message = hp_state(value)
				collector.add_alert(report.Alert(state, "%s_%d is %s" % (device_type, device_num, message)))
			device_num = device_type = None


hpGlobalMemTotalBytes = hpmib + (2, 14, 11, 5, 1, 1, 2, 2, 1, 1, 5)
hpGlobalMemAllocBytes = hpmib + (2, 14, 11, 5, 1, 1, 2, 2, 1, 1, 7)
all_oids.update((hpGlobalMemTotalBytes, hpGlobalMemAllocBytes))


@future.coroutine
def hp_mem_usage_plugin(controller, collector):
	for oid, value in (yield plugins.snmpwalk(controller, hpGlobalMemAllocBytes)):
		value = plugins.as_decimal(value)
		total = plugins.as_decimal((yield controller.engine.get(hpGlobalMemTotalBytes + (oid[-1],))))
		collector.add_metric(report.PerfMetric("mem_%d" % oid[-1], value, uom="B", minval=0, maxval=total))

@future.coroutine
def hp_detect(controller, collector):
	controller.start_plugin(collector, hp_sensors_plugin)
	controller.start_plugin(collector, hp_mem_usage_plugin)
	future.return_()
