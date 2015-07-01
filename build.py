#! ve/bin/python

import argparse
import http.server
import importlib
import os
import sys
import traceback

import watchdog.events
import watchdog.observers

class Builder(watchdog.events.FileSystemEventHandler):
	def __init__(self, conf):
		self.conf = conf

	def on_any_event(self, event):
		print("Change detected, rebuilding...")
		self.build()

	def build(self):
		try:
			import stas
			importlib.reload(stas)
			stas.Stas(self.conf).build()
		except:
			traceback.print_exc()

class Reloader(watchdog.events.FileSystemEventHandler):
	def __init__(self, conf_file, server):
		self.conf_file = conf_file
		self.server = server

	def on_any_event(self, event):
		if self.conf_file in event.src_path or 'stas.py' in event.src_path:
			print("Python change detected, reloading...")
			self.server.shutdown()

class RequestHandler(http.server.SimpleHTTPRequestHandler):
	allow_reuse_address = True

	def do_GET(self):
		self.path = os.path.join(self.conf.PUBLIC_DIR, '.' + self.path)
		super().do_GET()

def main(debug):
	conf_mod = 'conf_debug'
	if not debug:
		conf_mod = 'conf_publish'
	conf_file = conf_mod + '.py'

	conf = importlib.import_module(conf_mod)
	importlib.reload(conf)

	builder = Builder(conf)
	builder.build()

	if not debug:
		return

	RequestHandler.conf = conf
	server = http.server.HTTPServer(('', conf.DEBUG_PORT), RequestHandler)
	reloader = Reloader(conf_file, server)

	observer = watchdog.observers.Observer()
	observer.schedule(builder, conf.CONTENT_DIR, recursive=True)
	observer.schedule(builder, conf.TEMPLATE_DIR, recursive=True)
	observer.schedule(builder, conf.ASSETS_DIR, recursive=True)
	observer.schedule(reloader, '.')
	observer.start()

	sys.stderr.write('Serving on port {0} ...\n'.format(conf.DEBUG_PORT))
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
