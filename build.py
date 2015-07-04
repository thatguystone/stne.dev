#! ve/bin/python

import argparse
import http.server
import importlib
import os
import pathlib
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

	def build(self, debug=True):
		try:
			import stas
			importlib.reload(stas)
			stas.Stas(self.conf).build()
		except:
			if not debug:
				raise
			traceback.print_exc()

class Reloader(watchdog.events.FileSystemEventHandler):
	def __init__(self, cfg_file, server):
		self.cfg_file = cfg_file
		self.server = server

	def on_any_event(self, event):
		if self.cfg_file in event.src_path or 'stas.py' in event.src_path:
			print("Python change detected, reloading...")
			self.server.shutdown()

class RequestHandler(http.server.SimpleHTTPRequestHandler):
	def translate_path(self, path):
		path = os.path.join(self.conf.PUBLIC_DIR, '.' + path)
		return super().translate_path(path)

def main(cfg_file):
	conf_mod = pathlib.Path(cfg_file).stem
	conf = importlib.import_module(conf_mod)
	importlib.reload(conf)

	builder = Builder(conf)
	builder.build(debug=conf.DEBUG)

	if not conf.DEBUG:
		return False

	RequestHandler.conf = conf
	server = http.server.HTTPServer(('', conf.DEBUG_PORT), RequestHandler)
	reloader = Reloader(cfg_file, server)

	observer = watchdog.observers.Observer()
	observer.schedule(builder, conf.CONTENT_DIR, recursive=True)
	observer.schedule(builder, conf.DATA_DIR, recursive=True)
	observer.schedule(builder, conf.TEMPLATE_DIR, recursive=True)
	observer.schedule(builder, conf.ASSETS_DIR, recursive=True)
	observer.schedule(reloader, '.')
	observer.start()

	sys.stderr.write('Serving on port {0} ...\n'.format(conf.DEBUG_PORT))
	server.serve_forever()
	server.socket.close()
	observer.stop()

	return True

if __name__ == '__main__':
	arg_parser = argparse.ArgumentParser(description='build this site')
	arg_parser.add_argument('config',
		metavar='CONFIG',
		type=str)
	args = arg_parser.parse_args()

	while main(args.config):
		pass

