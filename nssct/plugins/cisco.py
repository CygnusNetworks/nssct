# -*- encoding: utf-8 -*-

from .. import future
from .. import plugins
from .. import report

all_oids = set()

cisco = (1, 3, 6, 1, 4, 1, 9)
cisco_states = {
		1: (report.OK, "normal"),
		2: (report.WARNING, "warning"),
		3: (report.CRITICAL, "critical"),
		4: (report.CRITICAL, "shutdown"),
		5: (report.UNKNOWN, "notPresent"),
		6: (report.CRITICAL, "notFunctioning")
}

def cisco_state(numeric):
	return cisco_states.get(numeric, (report.CRITICAL, "unexpected code %d" % numeric))


ciscoEnvMonFanStatusDescr = cisco + (9, 13, 1, 4, 1, 2)
ciscoEnvMonFanState = cisco + (9, 13, 1, 4, 1, 3)
all_oids.update((ciscoEnvMonFanStatusDescr, ciscoEnvMonFanState))


@future.coroutine
def cisco_fan_table_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, ciscoEnvMonFanState)
	while (yield fut):
		oid, value, fut = fut.result()
		name = (yield controller.engine.get(ciscoEnvMonFanStatusDescr + (oid[-1],)))
		state, reason = cisco_state(value)
		collector.add_alert(report.Alert(state, "fan_%s is %s" % (name, reason)))


ciscoEnvMonSupplyStatusDescr = cisco + (9, 13, 1, 5, 1, 2)
ciscoEnvMonSupplyState = cisco + (9, 13, 1, 5, 1, 3)
all_oids.update((ciscoEnvMonSupplyStatusDescr, ciscoEnvMonSupplyState))

@future.coroutine
def cisco_psu_table_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, ciscoEnvMonSupplyState)
	while (yield fut):
		oid, value, fut = fut.result()
		name = (yield controller.engine.get(ciscoEnvMonSupplyStatusDescr + (oid[-1],)))
		state, reason = cisco_state(value)
		collector.add_alert(report.Alert(state, "psu_%s is %s" % (name, reason)))


ciscoMemoryPoolName = cisco + (9, 48, 1, 1, 1, 2)
ciscoMemoryPoolUsed = cisco + (9, 48, 1, 1, 1, 5)
ciscoMemoryPoolFree = cisco + (9, 48, 1, 1, 1, 6)
all_oids.update((ciscoMemoryPoolName, ciscoMemoryPoolUsed, ciscoMemoryPoolFree))

@future.coroutine
def cisco_mem_usage_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, ciscoMemoryPoolName)
	while (yield fut):
		oid, name, fut = fut.result()
		used = controller.engine.get(ciscoMemoryPoolUsed + (oid[-1],))
		free = controller.engine.get(ciscoMemoryPoolFree + (oid[-1],))
		used = plugins.as_decimal((yield used))
		total = used + plugins.as_decimal((yield free))
		collector.add_metric(report.PerfMetric("mem_%s" % name, used, uom="B", minval=0, maxval=total))


@future.coroutine
def cisco_detect(controller, collector):
	controller.start_plugin(collector, cisco_fan_table_plugin)
	controller.start_plugin(collector, cisco_psu_table_plugin)
	controller.start_plugin(collector, cisco_mem_usage_plugin)
	future.return_()
