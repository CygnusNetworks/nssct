<?php
$ds_name=array();
foreach($this->DS as $KEY=>$VAL) {
	if(preg_match("/^(chas|agent).*temp$/", $VAL['NAME'])) {
		if(!array_key_exists("temperature", $ds_name)) {
			$ds_name["temperature"] = "Temperature";
			$opt["temperature"] = "--vertical-label °C --lower-limit 15";
			$def["temperature"] = "";
		}
		$def["temperature"] .= rrd::def($VAL['NAME'], $VAL['RRDFILE'], $VAL["DS"], "AVERAGE");
		$def["temperature"] .= rrd::line1($VAL['NAME'], rrd::color(1+$KEY), sprintf("%-15s", $VAL['NAME']));
		$def["temperature"] .= rrd::gprint($VAL['NAME'], array("MAX", "AVERAGE", "LAST"), "%3.1lf °C");
	}
	if(preg_match("/^(dyn)?mem/", $VAL['NAME'])) {
		if(!array_key_exists("memory", $ds_name)) {
			$ds_name["memory"] = "Memory usage";
			$opt["memory"] = "--vertical-label B --lower-limit 0 --upper-limit $VAL[MAX]";
			$def["memory"] = "";
		}
		$def["memory"] .= rrd::def($VAL['NAME'], $VAL['RRDFILE'], $VAL["DS"], "AVERAGE");
		$def["memory"] .= rrd::area($VAL['NAME'], rrd::color($KEY), sprintf("%-15s", $VAL['NAME']));
		$def["memory"] .= rrd::gprint($VAL['NAME'], array("MAX", "AVERAGE", "LAST"), "%3.1lf %sB");
	}
	if(preg_match("/^cpu/", $VAL['NAME'])) {
		if(!array_key_exists("cpu", $ds_name)) {
			$ds_name["cpu"] = "CPU usage";
			$opt["cpu"] = "--vertical-label % --lower-limit 0 --upper-limit 100 --rigid";
			$def["cpu"] = "";
		}
		$def["cpu"] .= rrd::def($VAL['NAME'], $VAL['RRDFILE'], $VAL["DS"], "AVERAGE");
		$def["cpu"] .= rrd::area($VAL['NAME'], rrd::color($KEY), sprintf("%-15s", $VAL['NAME']));
		$def["cpu"] .= rrd::gprint($VAL['NAME'], array("MAX", "AVERAGE", "LAST"), "%3.1lf %%");
	}
	if(preg_match("/^uptime/", $VAL['NAME'])) {
		if(!array_key_exists("uptime", $ds_name)) {
			$ds_name["uptime"] = "Uptime";
			$opt["uptime"] = "--vertical-label days --lower-limit 0 --rigid";
			$def["uptime"] = "";
		}
		$def["uptime"] .= rrd::def($VAL['NAME'], $VAL['RRDFILE'], $VAL["DS"], "MAX");
		$def["uptime"] .= rrd::cdef('days', "uptime,86400,/");
		$def["uptime"] .= rrd::area('days', '#80f000', "Uptime (days)");
		$def["uptime"] .= rrd::line1('days', '#408000');
		$def["uptime"] .= rrd::gprint('days', array("LAST", "MAX"), "%7.2lf days");
		if ($VAL['WARN'] != "" && is_numeric($VAL['WARN']) ){
			$warning = $VAL['WARN'] / 86400;
			$def["uptime"] .= rrd::hrule($warning, '#FFFF00', sprintf('Warning %s days', $warning));
		}
		if ($VAL['CRIT'] != "" && is_numeric($VAL['CRIT']) ){
			$critical = $VAL['CRIT'] / 86400;
			$def["uptime"] .= rrd::hrule($critical, '#FF0000', sprintf('Critical %s days', $critical));
		}
	}}

?>
