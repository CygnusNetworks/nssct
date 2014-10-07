What is nssct?
==============

The acronym stands for Nagios SNMP Switch Check Tool. The idea is that all you
need to pass to the tool is an IP address and a community string and it should
figure out what kind of device it is talking to and determine the health
(temperature, fan, CPU usage, memory usage, etc.) of the device. It generates
performance data when available, so it can also be used for graphing resources.

Using nssct
===========

The package will ship a `nssct` script. It can be used as a nagios plugin.
Refer to `nssct --help` for information on how to invoke it.

When using it in conjunction with Nagios a service configuration will likely
look like following.

    define service{
        use                 generic-service
        host_name           MONITORED_DEVICE
        check_command       check_nssct!PUBLIC_COMMUNITY
        service_description nssct
        }

If you are using pnp4nagios, use `generic-service-perfdata` instead of
`generic-service`.

Reporting issues
================

If your device does not work with nssct, please create a machine readable dump.
Use the following parameters to do that:

    snmpwalk -Onx --hexOutputLength=1024 ...
