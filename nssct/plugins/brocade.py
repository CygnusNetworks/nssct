# -*- encoding: utf-8 -*-

import distutils.version
import logging
import re

from .. import engine
from .. import future
from .. import plugins
from .. import report

logger = logging.getLogger(__name__)

all_oids = set()

brcdIp = (1, 3, 6, 1, 4, 1, 1991)

MIN_VERSIONS = {
	'FWS-X424': '05.1.00',
	'FWS-X448': '05.1.00',
	'FWS-648G': '07.2.02',
	'FWS-624G': '07.2.02',
	'ICX6430-24': '08.0.20',
	'ICX6430-48': '08.0.20',
	'ICX7150-48': '08.0.92b',
}
SWITCH_TYPE_REGEX = r"^(Foundry Networks, Inc\..|Brocade Communications Systems, Inc\..|Ruckus Wireless, Inc\. (Stacking System )?)(?P<type>.*),.*"

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
snChasUnitShutdownTemperature = brcdIp + (1, 1, 1, 4, 1, 1, 6)
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


snChasFan2OperStatus = brcdIp + (1, 1, 1, 3, 2, 1, 4)
all_oids.add(snChasFan2OperStatus)

@future.coroutine
def brocade_stack_fan_table_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, snChasFan2OperStatus)
	while (yield fut):
		oid, value, fut = fut.result()
		index = "_".join(map(str, oid[len(snChasFan2OperStatus):]))
		value = int(value)
		if value == 2:
			alert = report.Alert(report.OK, "stack fan %s is ok" % index)
		else:
			msg = "stack fan %s is critical with status %d" % (index, value)
			alert = report.Alert(report.CRITICAL, msg)
		collector.add_alert(alert)


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
		elif value == 1:  # other
			alert = report.Alert(report.OK, "psu %d is state other (possibly not present)" % index)
		else:
			msg = "psu %d has unexpected status %d" % (index, value)
			alert = report.Alert(report.CRITICAL, msg)
		collector.add_alert(alert)


snChasPwrSupply2Description = brcdIp + (1, 1, 1, 2, 2, 1, 3)
snChasPwrSupply2OperStatus = brcdIp + (1, 1, 1, 2, 2, 1, 4)
all_oids.update((snChasPwrSupply2Description, snChasPwrSupply2OperStatus))

@future.coroutine
def brocade_stack_psu_table_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, snChasPwrSupply2OperStatus)
	while (yield fut):
		oid, value, fut = fut.result()
		value = int(value)
		index_tuple = oid[len(snChasPwrSupply2OperStatus):]
		index = "_".join(map(str, index_tuple))
		if value == 2: # normal
			alert = report.Alert(report.OK, "stack psu %s is ok" % index)
		elif value == 3: # failure
			msg = str((yield controller.engine.get(snChasPwrSupply2Description + index_tuple)))
			logger.debug("failed stack psu %s described as %r", index, msg)
			if msg.rstrip().endswith(" not present"):
				alert = report.Alert(report.OK, "stack psu %s is not present" % index)
			else:
				alert = report.Alert(report.CRITICAL, "stack psu %s has failed" % index)
		elif value == 1:  # other
			alert = report.Alert(report.OK, "stack psu %s is state other (possibly not present)" % index)
		else:
			msg = "stack psu %s has unexpected status %d" % (index, value)
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


sysDescr = (1, 3, 6, 1, 2, 1, 1, 1, 0)
snmpEngineTime = (1, 3, 6, 1, 6, 3, 10, 2, 1, 3, 0)
all_oids.add((sysDescr, snmpEngineTime))

@future.coroutine
def brocade_uptime_plugin(controller, collector):
	warn = None
	crit = None

	descr = yield controller.engine.get(sysDescr)
	match = re.match(SWITCH_TYPE_REGEX, str(descr))

	if match:
		switch_type = match.groupdict()['type']
		if switch_type.startswith('ICX6430'):
			warn = 1100 * 86400
			crit = 1200 * 86400

	uptime = yield controller.engine.get(snmpEngineTime)
	uptime_days = round(float(uptime)/86400, 2)

	collector.add_metric(report.PerfMetric("uptime", uptime, uom="s", warn=warn, crit=crit, msg="uptime=%4.2f days" % uptime_days))


snAgImgVer = brcdIp + (1, 1, 2, 1, 11, 0)
snAgFlashImgVer = brcdIp + (1, 1, 2, 1, 12, 0)
all_oids.add(snAgImgVer)

@future.coroutine
def brocade_version_plugin(controller, collector):
	alert = None
	img_ver = yield controller.engine.get(snAgImgVer)
	flash_img_ver = yield controller.engine.get(snAgImgVer)
	descr = yield controller.engine.get(sysDescr)
	img_ver = str(img_ver)
	flash_img_ver = str(flash_img_ver)

	if img_ver != flash_img_ver:
		alert = report.Alert(report.WARNING, "running image version %s is not primary flash version %s" % (img_ver, flash_img_ver))
		collector.add_alert(alert)

	match = re.match(SWITCH_TYPE_REGEX, str(descr))
	if match:
		switch_type = match.groupdict()['type']
		if switch_type in MIN_VERSIONS:
			if distutils.version.LooseVersion(img_ver) < distutils.version.LooseVersion(MIN_VERSIONS[switch_type]):
				alert = report.Alert(report.WARNING, "image version %s is too old - require version %s" % (img_ver, MIN_VERSIONS[switch_type]))
				collector.add_alert(alert)

	if alert is None:
		alert = report.Alert(report.OK, "image version is %s" % img_ver)
		collector.add_alert(alert)


snStackingGlobalTopology = brcdIp + (1, 1, 3, 31, 1, 5, 0)
all_oids.add(snStackingGlobalTopology)

@future.coroutine
def brocade_stacking_topology_plugin(controller, collector):
	fut = plugins.snmpwalk(controller, snStackingConfigUnitPriority)
	count = 0
	while (yield fut):
		_, _, fut = fut.result()
		count += 1

	value = yield controller.engine.get(snStackingGlobalTopology)
	value = int(value)
	if value == 3:  # ring
		alert = report.Alert(report.OK, "stacking topology is ring")
	elif value == 2:  # chain
		logger.debug("stacking topology is chain")
		if count > 2:
			alert = report.Alert(report.WARNING, "stacking topoplogy is chain with %s devices" % count)
		else:
			alert = report.Alert(report.OK, "stacking topoplogy is chain")
	elif value == 4:  # standalone
		logger.debug("stacking topology is standalone")
		alert = report.Alert(report.CRITICAL, "stacking topoplogy is standalone")
	elif value == 1:  # other
		logger.debug("stacking topology is other")
		alert = report.Alert(report.CRITICAL, "stacking topology is other")
	else:
		msg = "stacking topology has unexpected status %d" % value
		alert = report.Alert(report.CRITICAL, msg)

	collector.add_alert(alert)


snStackingConfigUnitState = brcdIp + (1, 1, 3, 31, 2, 1, 1, 6)
all_oids.add(snStackingConfigUnitState)

@future.coroutine
def brocade_stacking_unit_state(controller, collector):
	fut = plugins.snmpwalk(controller, snStackingConfigUnitState)

	while (yield fut):
		oid, value, fut = fut.result()
		value = int(value)
		index = oid[len(snStackingConfigUnitState):]

		if value == 1:
			alert = report.Alert(report.OK, "unit %s state is local" % index)
		if value == 2:
			alert = report.Alert(report.OK, "unit %s state is remote" % index)
		if value == 3:
			alert = report.Alert(report.CRITICAL, "unit %s state is reserved" % index)
		if value == 4:
			alert = report.Alert(report.CRITICAL, "unit %s state is empty" % index)

		collector.add_alert(alert)


snStackingOperUnitImgVer = brcdIp + (1, 1, 3, 31, 2, 2, 1, 13)
snStackingOperUnitBuildlVer = brcdIp + (1, 1, 3, 31, 2, 2, 1, 14)
all_oids.update((snStackingOperUnitImgVer, snStackingOperUnitBuildlVer))

@future.coroutine
def brocade_stacking_version_plugin(controller, collector):
	def __check_versions(version_type, versions):
		expected = next(iter(versions.values()))
		if all(value == expected for value in versions.values()):
			alert = report.Alert(report.OK, "stack %s version is %s" % (version_type, expected))
		else:
			version_strings = []
			for index in versions:
				version_strings.append("unit %d: %s" % (index, versions[index]))
			alert = report.Alert(report.WARNING, "stack %s versions not equal - %s" % (version_type, ", ".join(version_strings)))
		collector.add_alert(alert)

	fut = plugins.snmpwalk(controller, snStackingOperUnitImgVer)

	img_version = dict()
	build_version = dict()
	while (yield fut):
		oid, value, fut = fut.result()
		index = oid[len(snStackingOperUnitImgVer)]
		img_version[index] = value

	__check_versions('image', img_version)

	fut = plugins.snmpwalk(controller, snStackingOperUnitBuildlVer)
	while (yield fut):
		oid, value, fut = fut.result()
		index = oid[len(snStackingOperUnitBuildlVer)]
		build_version[index] = value

	__check_versions('build', build_version)


snStackingGlobalConfigSt = brcdIp + (1, 1, 3, 31, 1, 1, 0)
snStackingConfigUnitPriority = brcdIp + (1, 1, 3, 31, 2, 1, 1, 2)
all_oids.update((snStackingGlobalConfigSt, snStackingConfigUnitPriority))

@future.coroutine
def brocade_stack_plugin(controller, collector):
	try:
		stackcfg = (yield controller.engine.get(snStackingGlobalConfigSt))
	except (engine.NoSuchObjectError, engine.EndOfMibError):
		alert = report.Alert(report.OK, "stacking not available")
	else:
		if stackcfg != 1:  # enabled
			alert = report.Alert(report.OK, "stacking not enabled")
		else:
			# start stack-specific plugins
			controller.start_plugin(collector, brocade_stacking_topology_plugin)
			controller.start_plugin(collector, brocade_stacking_version_plugin)
			controller.start_plugin(collector, brocade_stacking_unit_state)

			fut = plugins.snmpwalk(controller, snStackingConfigUnitPriority)
			count = 0
			while (yield fut):
				_, _, fut = fut.result()
				count += 1
			if count == 0:
				alert = report.Alert(report.CRITICAL, "stacking switch without units")
			elif count == 1:
				alert = report.Alert(report.CRITICAL, "stacking switch with only one unit")
			else:
				alert = report.Alert(report.OK, "stacking switch with %d units" % count)

	collector.add_alert(alert)

snBigIronRXFamily = brcdIp + (1, 3, 40)

@future.coroutine
def brocade_detect(controller, collector):
	controller.start_plugin(collector, brocade_unit_temperature_plugin)
	controller.start_plugin(collector, brocade_agent_temperature_plugin)
	controller.start_plugin(collector, brocade_fan_table_plugin)
	controller.start_plugin(collector, brocade_stack_fan_table_plugin)
	controller.start_plugin(collector, brocade_psu_table_plugin)
	controller.start_plugin(collector, brocade_stack_psu_table_plugin)
	controller.start_plugin(collector, brocade_cpu_usage_plugin)
	controller.start_plugin(collector, brocade_mem_usage_plugin)
	controller.start_plugin(collector, brocade_stack_plugin)
	controller.start_plugin(collector, brocade_uptime_plugin)
	controller.start_plugin(collector, brocade_version_plugin)
	oid = (yield controller.engine.get(plugins.sysObjectID))
	if not plugins.oid_startswith(oid, snBigIronRXFamily):
		controller.start_plugin(collector, brocade_temperature_plugin)
