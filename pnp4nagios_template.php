<?php
$ds_name=array();
foreach($this->DS as $KEY=>$VAL) {
	if(preg_match("/^(chas|agent).*temp$/", $VAL['NAME'])) {
		if(!array_key_exists("temperature", $ds_name)) {
			$ds_name["temperature"] = "Temperature";
			$opt["temperature"] = "--vertical-label °C --lower-limit 0";
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
}

?>
