# -*- encoding: utf-8 -*-

import logging

from . import report

logger = logging.getLogger(__name__)

class Controller(object):
	"""The controller keeps the pieces (engine, collector, and plugins)
	together. The collector is just passed on to the plugins, the controller
	does not operate itself on a collector. A plugin is a function that takes
	references to the controller and the collector and returns a future.
	Plugins will access the engine attribute of the controller to query SNMP
	OIDs. They can also use the start_plugin method to start further plugins.

	The main reason to use a controller object instead of just starting
	plugins is to notice when a plugin fails to complete. Without the
	controller, a missing callback invocation could abort a plugin without
	anything noticing.
	"""

	def __init__(self, engine):
		self.engine = engine
		self.pending_plugins = []

	def start_plugin(self, collector, plugin):
		"""Start the given plugin with the given collector.
		@type collector: Collector
		"""
		logger.debug("starting plugin %r", plugin)
		def completion(fut):
			self.pending_plugins.remove(fut)
			try:
				fut.result()
			except Exception as exc:
				logger.error("plugin %r failed to complete due to %r", plugin, exc, exc_info=True)
				collector.add_alert(report.Alert(report.CRITICAL, "plugin %r failed to complete with error %r" % (plugin, exc)))
			else:
				logger.debug("completed plugin %r", plugin)
		try:
			fut = plugin(self, collector)
		except Exception:
			logger.exception("swallowing exception from plugin")
		else:
			self.pending_plugins.append(fut)
			fut.add_done_callback(completion)

	def step(self):
		"""Run an engine step and return whether more steps are needed to finish
		the started plugins.
		@rtype: bool
		"""
		workleft = self.engine.step()
		if self.pending_plugins and not workleft:
			logger.error("some plugins failed to complete")
			return False
		return bool(self.pending_plugins)

	def run(self, collector, plugins):
		"""Start the given plugins and iterate engine steps until all plugins
		finish."""
		for plugin in plugins:
			self.start_plugin(collector, plugin)

		while self.step():
			pass
