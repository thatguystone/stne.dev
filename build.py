#! /usr/bin/env python

import argparse
import http.server
import importlib
import os
import sys

import pelican
import pelican.server
import watchdog.events
import watchdog.observers

class Builder(watchdog.events.FileSystemEventHandler):
	def __init__(self, conf_file, conf):
		self.conf_file = conf_file
		self.conf = conf

	def on_any_event(self, event):
		print("Change detected, rebuilding...")

		if event.src_path.startswith(self.conf.PLUGINS_PATH):
			for plugin in self.conf.PLUGINS:
				p = importlib.import_module(plugin)
				importlib.reload(p)

		self.build()

	def build(self):
		sys.argv = [
			'-r', self.conf.PATH,
			'-o', self.conf.PUB_PATH,
			'-s', self.conf_file]
		try:
			pelican.main()
		except Exception as e:
			print("failed to build site:", e)

class Reloader(watchdog.events.FileSystemEventHandler):
	def __init__(self, conf_file, server):
		self.conf_file = conf_file
		self.server = server

	def on_any_event(self, event):
		if self.conf_file in event.src_path:
			print("Config change detected, reloading...")
			self.server.shutdown()

class RequestHandler(pelican.server.ComplexHTTPRequestHandler):
	allow_reuse_address = True

	def log_message(self, format, *args):
		return

	def do_GET(self):
		self.path = os.path.join(self.conf.PUB_PATH, '.' + self.path)
		super().do_GET()

def main(debug):
	conf_mod = 'conf_debug'
	if not debug:
		conf_mod = 'conf_publish'
	conf_file = conf_mod + '.py'

	conf = importlib.import_module(conf_mod)
	importlib.reload(conf)

	builder = Builder(conf_file, conf)
	builder.build()

	if not debug:
		return

	RequestHandler.conf = conf
	server = http.server.HTTPServer(('', conf.PORT), RequestHandler)
	reloader = Reloader(conf_file, server)

	observer = watchdog.observers.Observer()
	observer.schedule(builder, conf.PATH)
	observer.schedule(builder, conf.PLUGINS_PATH)
	observer.schedule(reloader, '.')
	observer.start()

	sys.stderr.write('Serving on port {0} ...\n'.format(conf.PORT))
	server.serve_forever()
	server.socket.close()
	observer.stop()

if __name__ == '__main__':
	arg_parser = argparse.ArgumentParser(description='build this site')
	arg_parser.add_argument('--debug',
		action='store_const',
		const=True,
		help='build in debug mode')
	args = arg_parser.parse_args()

	if not args.debug:
		main(False)
	else:
		while True:
			main(True)
