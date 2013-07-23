# -*- encoding: utf-8 -*-

"""A future is a result, that does not yet exist. It will become available in
some future. This is what the Future class encapsulates."""

import functools
import logging
import sys

logger = logging.getLogger(__name__)

FT_PENDING = 0
FT_COMPLETED = 1
FT_ERROR = 2


class Future(object):
	"""PEP3148/PEP3156 inspired future class"""
	state = FT_PENDING
	value = None

	def __init__(self):
		self.callbacks = []

	def done(self):
		return self.state != FT_PENDING

	def set_result(self, result):
		assert self.state == FT_PENDING
		self.value = result
		self.state = FT_COMPLETED
		self._run_callbacks()

	def set_exception(self, exc):
		assert self.state == FT_PENDING
		assert isinstance(exc, Exception)
		self.value = exc
		self.state = FT_ERROR
		self._run_callbacks()

	def add_done_callback(self, func):
		self.callbacks.append(func)
		if self.state > FT_PENDING:
			self._run_callbacks()

	def result(self):
		assert self.state > FT_PENDING
		if self.state == FT_ERROR:
			raise self.value
		assert self.state == FT_COMPLETED
		return self.value

	def exception(self):
		assert self.state > FT_PENDING
		if self.state == FT_ERROR:
			return self.value
		assert self.state == FT_COMPLETED
		return None

	def _run_callbacks(self):
		assert self.state > FT_PENDING
		while self.callbacks:
			callback = self.callbacks.pop(0)
			try:
				callback(self)
			except Exception:
				logger.exception("swallowing exception from callback")


def attach_traceback(exception, exc_info=None):
	"""Attach a __traceback__ attribute to the given exception.
	@type exception: Exception
	@param exc_info: if it is None, it is replaced with the return value of
			sys.exc_info(). If it is a tuple, it is assumed to be a return
			value of sys.exc_info() and the third element is used as a
			traceback object. Otherwise exc_info is assumed to be a traceback
			object itself. If the traceback obtained is not None, it is
			attached to the exception as __traceback__ unless that attribute
			already exists.
	@returns: exception
	"""
	if exc_info is None:
		exc_info = sys.exc_info()
	traceback = exc_info[2] if isinstance(exc_info, tuple) else exc_info
	if traceback is not None and not hasattr(exception, "__traceback__"):
		try:
			exception.__traceback__ = traceback
		except AttributeError:
			pass  # if the exception has __slots__, we cannot add attributes
	return exception

def attach_cause(exception, cause):
	"""Attach a __cause__ attribute to the given exception unless it is
	already defined and non-zero.
	@type exception: Exception
	@type cause: Exception
	@param cause: is assigned to exception.__cause__
	@returns: exception
	"""
	if cause is not None and not (hasattr(exception, "__cause__") and exception.__cause__):
		try:
			exception.__cause__ = cause
		except AttributeError:
			pass  # if the exception has __slots__, we cannot add attributes
	return exception


def complete_future(obj):
	"""Create a new future and set its result to the passed object.
	@rtype: Future
	"""
	future = Future()
	future.set_result(obj)
	return future


def complete_with(fut, function):
	"""Use the result or exception from the passed function when invoked
	without parameters as the result or exception of the given future.
	"""
	try:
		result = function()
	except Exception as exc:
		attach_traceback(exc)
		logger.debug("forwarding exception from function %r", function, exc_info=True)
		fut.set_exception(exc)
	else:
		fut.set_result(result)

def future_completer(fut):
	"""Decorate a function to complete a Future when being called. The fut
	given to the decorator specifies a Future or the argument or keyword
	argument that contains the Future, that is to be completed. Since the
	Future consumes exceptions raised or values returned from the function,
	the decorated function retuns None.
	@type fut: Future or int or str
	@param fut: if fut is a Future, this is the future to be completed. If it
			is an integer, it is treated as an index into the argument vector
			passed to the decorated function. If it is a str it is treated as
			the key of a keyword argument. In both of the latter cases the
			actual future is taken from the argument of the decorated
			function.
	@returns: a function decorator
	"""
	assert isinstance(fut, (int, str, Future))
	def wrapper(fut, function):
		@functools.wraps(function)
		def wrapped(fut, *args, **kwargs):
			if isinstance(fut, int):
				fut = args[fut]
			elif isinstance(fut, str):
				fut = kwargs[fut]
			assert isinstance(fut, Future)
			try:
				result = function(*args, **kwargs)
			except Exception as exc:
				attach_traceback(exc)
				fut.set_exception(exc)
			else:
				fut.set_result(result)
		return functools.partial(wrapped, fut)
	return functools.partial(wrapper, fut)


class GeneratedFuture(Future):
	"""Turn a generator into a future by treating the elements yielded as
	futures and passing back the results of these futures. If a StopIteration
	is raised with a value, this value is used as the result of the future.
	"""
	def __init__(self, generator):
		Future.__init__(self)
		self.generator = generator
		self.waiting = None
		try:
			next_ = self.generator.__next__
		except AttributeError:
			next_ = self.generator.next
		self._invoke(next_)

	def _invoke(self, func, *args):
		try:
			self.waiting = func(*args)
		except StopIteration as stop:
			if stop.args:
				self.set_result(stop.args[0])
			else:
				self.set_result(None)
		except Exception as exc:
			attach_traceback(exc)
			logger.debug("propagating exception from generator", exc_info=True)
			self.set_exception(exc)
		else:
			self.waiting.add_done_callback(self._handle_completion)

	def _handle_completion(self, future):
		assert self.waiting is future
		try:
			result = future.result()
		except Exception as exc:
			attach_traceback(exc)
			logger.debug("forwarding exception %s from future to generator", exc, exc_info=True)
			self._invoke(self.generator.throw, exc)
		else:
			self._invoke(self.generator.send, result)

	def __repr__(self):
		state = "finished" if self.done() else "waiting for %r" % self.waiting
		return "<GeneratedFuture %r %s>" % (self.generator, state)


def coroutine(function):
	"""The coroutine turns a function returning a generator into a function
	returning a Future. Each element of the generator must be a Future itself
	and the generator is continued when the yielded future is read with the
	value or exception of it. It may raise a StopIteration with a value. In
	that case the parameter is used as the result of returned Future.
	"""
	@functools.wraps(function)
	def wrapped(*args):
		return GeneratedFuture(function(*args))
	return wrapped


def return_(value=None):
	"""Can be used to return a value from a coroutine. It raises a
	StopIteration with the given value as required by coroutine."""
	if value is None:
		raise StopIteration
	raise StopIteration(value)
