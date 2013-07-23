# -*- encoding: utf-8 -*-

import logging

from . import report

logger = logging.getLogger(__name__)

class Controller(object):
	def __init__(self, engine):
		self.engine = engine
		self.pending_plugins = []

	def start_plugin(self, collector, plugin):
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

	def run(self, collector, plugins):
		for plugin in plugins:
			self.start_plugin(collector, plugin)

		workleft = self.engine.step()
		while self.pending_plugins:
			if not workleft:
				logger.error("some plugins failed to complete")
				return
			workleft = self.engine.step()
