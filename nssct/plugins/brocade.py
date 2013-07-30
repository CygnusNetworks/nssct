# -*- encoding: utf-8 -*-

import logging

from .. import future
from .. import plugins
from .. import report

logger = logging.getLogger(__name__)

all_oids = set()

brcdIp = (1, 3, 6, 1, 4, 1, 1991)

snChasActualTemperature = brcdIp + (1, 1, 1, 1, 18, 0)
snChasWarningTemperature = brcdIp + (1, 1, 1, 1, 19, 0)
snChasShutdownTemperature = brcdIp + (1, 1, 1, 1, 20, 0)
all_oids.update((snChasActualTemperature, snChasWarningTemperature, snChasShutdownTemperature))

def brcd_temp(value):
	return plugins.as_decimal(value, "0.5")

@future.coroutine
def brocade_temperature_plugin(controller, collector):
	act = controller.engine.get(snChasActualTemperature)
	warn = controller.engine.get(snChasWarningTemperature)
	act = brcd_temp((yield act))
	warn = brcd_temp((yield warn))
	if act < warn:
		collector.add_metric(report.PerfMetric("chastemp", act, warn=warn, minval=-110, maxval=250))
		future.return_()
	logger.debug("temperature is %s, checking shutdown point", act)
	crit = brcd_temp((yield controller.engine.get(snChasShutdownTemperature)))
	collector.add_metric(report.PerfMetric("chastemp", act, warn=warn, crit=crit, minval=-110, maxval=250))

snChasUnitActualTemp = brcdIp + (1, 1, 1, 4, 1, 1, 4)
snChasUnitWarningTem = brcdIp + (1, 1, 1, 4, 1, 1, 5)
snChasUnitShutdownTemperature = brcdIp + (1, 1, 1, 4, 1, 1, 5)
all_oids.update((snChasUnitActualTemp, snChasUnitWarningTem, snChasUnitShutdownTemperature))

@future.coroutine
def brocade_unit_temperature_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, snChasUnitActualTemp)
	while (yield fut):
		oid, value, fut = fut.result()
		unit = oid[-1]
		act = brcd_temp(value)
		warn = brcd_temp((yield controller.engine.get(snChasUnitWarningTem + (unit,))))
		if act < warn:
			collector.add_metric(report.PerfMetric("chasunit%dtemp" % unit, act, warn=warn, minval=-110, maxval=250))
			future.return_()
		logger.debug("unit %d temperature is %s, checking shutdown point", unit, act)
		crit = brcd_temp((yield controller.engine.get(snChasUnitShutdownTemperature + (unit,))))
		collector.add_metric(report.PerfMetric("chasunit%dtemp" % unit, act, warn=warn, crit=crit, minval=-110, maxval=250))


snAgentTempValue = brcdIp + (1, 1, 2, 13, 1, 1, 4)
all_oids.add(snAgentTempValue)

@future.coroutine
def brocade_agent_temperature_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, snAgentTempValue)
	while (yield fut):
		oid, value, fut = fut.result()
		ident = oid[len(snAgentTempValue):]
		ident = "_".join(map(str, ident))
		act = brcd_temp(value)
		collector.add_metric(report.PerfMetric("agent_%s_temp" % ident, act, minval=-110, maxval=250))


snChasFanOperStatus = brcdIp + (1, 1, 1, 3, 1, 1, 3)
all_oids.add(snChasFanOperStatus)

@future.coroutine
def brocade_fan_table_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, snChasFanOperStatus)
	while (yield fut):
		oid, value, fut = fut.result()
		value = int(value)
		if value == 2:
			msg = "fan %d is ok" % oid[-1]
			collector.add_alert(report.Alert(report.OK, msg))
		else:
			msg = "fan %d is critical with status %d" % (oid[-1], value)
			collector.add_alert(report.Alert(report.CRITICAL, msg))


snChasPwrSupplyDescription = brcdIp + (1, 1, 1, 2, 1, 1, 2)
snChasPwrSupplyOperStatus = brcdIp + (1, 1, 1, 2, 1, 1, 3)
all_oids.update((snChasPwrSupplyDescription, snChasPwrSupplyOperStatus))

@future.coroutine
def brocade_psu_table_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, snChasPwrSupplyOperStatus)
	while (yield fut):
		oid, value, fut = fut.result()
		value = int(value)
		index = oid[-1]
		if value == 2: # normal
			alert = report.Alert(report.OK, "psu %d is ok" % index)
		elif value == 3: # failure
			msg = str((yield controller.engine.get(snChasPwrSupplyDescription + (index,))))
			logger.debug("failed psu %d described as %r", index, msg)
			if msg.rstrip().endswith(" not present"):
				alert = report.Alert(report.OK, "psu %d is not present" % index)
			else:
				alert = report.Alert(report.CRITICAL, "psu %d has failed" % index)
		else:
			msg = "psu %d has unexpected status %d" % (index, value)
			alert = report.Alert(report.CRITICAL, msg)
		collector.add_alert(alert)


snAgentCpuUtilValue = brcdIp + (1, 1, 2, 11, 1, 1, 4)
all_oids.add(snAgentCpuUtilValue)

@future.coroutine
def brocade_cpu_usage_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, snAgentCpuUtilValue)
	while (yield fut):
		oid, value, fut = fut.result()
		if oid[-1] != 300:  # select 5min interval
			continue
		slot = oid[-3]
		cpu = oid[-2]
		value = plugins.as_decimal(value, "0.01")
		collector.add_metric(report.PerfMetric("cpu_%d_%d" % (slot, cpu), value, "%"))


snAgGblDynMemTotal = brcdIp + (1, 1, 2, 1, 54, 0)
snAgGblDynMemFree = brcdIp + (1, 1, 2, 1, 55, 0)
all_oids.update((snAgGblDynMemTotal, snAgGblDynMemFree))

@future.coroutine
def brocade_mem_usage_plugin(controller, collector):
	total = controller.engine.get(snAgGblDynMemTotal)
	free = controller.engine.get(snAgGblDynMemFree)
	total = plugins.as_decimal((yield total))
	free = plugins.as_decimal((yield free))
	collector.add_metric(report.PerfMetric("dynmem", total - free, uom="B", minval=0, maxval=total))


snBigIronRXFamily = brcdIp + (1, 3, 40)

@future.coroutine
def brocade_detect(controller, collector):
	controller.start_plugin(collector, brocade_unit_temperature_plugin)
	controller.start_plugin(collector, brocade_agent_temperature_plugin)
	controller.start_plugin(collector, brocade_fan_table_plugin)
	controller.start_plugin(collector, brocade_psu_table_plugin)
	controller.start_plugin(collector, brocade_cpu_usage_plugin)
	controller.start_plugin(collector, brocade_mem_usage_plugin)
	oid = (yield controller.engine.get(plugins.sysObjectID))
	if not plugins.oid_startswith(oid, snBigIronRXFamily):
		controller.start_plugin(collector, brocade_temperature_plugin)
