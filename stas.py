import datetime
import multiprocessing
import os
import pathlib
import signal

import frontmatter
import htmlmin
import jinja2
import markdown
import webassets

# Only set from pool processes
jinja = None

class Stas(object):
	def __init__(self, conf):
		self.conf = self._conf_dict(conf)

	def build(self):
		assets = webassets.Environment(
			self.conf['PUBLIC_DIR'] + '/assets/', '/assets',
			load_path=(self.conf['ASSETS_DIR'], ),
			debug=bool(self.conf['DEBUG']))
		assets.register(self.conf['ASSETS'])

		jinja = jinja2.Environment(
			loader=jinja2.FileSystemLoader(self.conf['TEMPLATE_DIR']),
			extensions=[
			'webassets.ext.jinja2.AssetsExtension',
			'jinja2_highlight.HighlightExtension'])
		jinja.filters['markdown'] = self._safe_markdown
		jinja.assets_environment = assets

		try:
			cpus = multiprocessing.cpu_count()
			pool = multiprocessing.Pool(cpus * 2,
				self._worker_init, (jinja, ))
			self._build(pool)
		finally:
			pool.terminate()
			pool.join()

	def _conf_dict(self, conf):
		d = {}
		for k in dir(conf):
			if k.startswith('_') or k.upper() != k:
				continue
			d[k] = getattr(conf, k)
		return d

	def _worker_init(self, j):
		signal.signal(signal.SIGINT, signal.SIG_IGN)

		# There are tons of issues passing jinja through pickle, so just have
		# it passed as an argument across the fork
		global jinja
		jinja = j

	def _safe_markdown(self, text):
		return jinja2.Markup(markdown.markdown(text))

	def _build(self, pool):
		jobs = []

		path = pathlib.Path(self.conf['CONTENT_DIR'])
		for f in path.glob('**/*.j2'):
			jobs.append(pool.apply_async(_read, (self.conf, f, )))

		for job in jobs:
			job.get()

class Page(object):
	def __init__(self, conf, file):
		if len(file.parts) == 2:
			self.name = file.stem
			self.category = ''

			if self.name == 'index':
				self.dst = '%s/index.html' % conf['PUBLIC_DIR']
				return

		elif file.stem == 'index':
			self.name = file.parts[-2]
			self.category = file.parts[-3]
		else:
			self.name = file.stem
			self.category = file.parts[-2]

		try:
			self.date = datetime.datetime.strptime(
				self.name[:10],
				'%Y-%m-%d')
			self.name = self.name[11:]

			self.dst = '%s/%s/%s/%s' % (
				conf['PUBLIC_DIR'],
				self.category,
				self.date.strftime('%Y/%m/%d'),
				self.name)
		except ValueError:
			self.date = None
			self.dst = '%s/%s/%s' % (
				conf['PUBLIC_DIR'],
				self.category,
				self.name)

		self.dst += '/index.html'

def _read(conf, file):
	try:
		p = Page(conf, file)

		with file.open() as f:
			content = f.read()

		page = frontmatter.loads(content)
		tmpl = jinja.from_string(page.content)

		content = tmpl.render(
			conf=conf,
			page=p,
			meta=page.metadata)

		if not conf['DEBUG']:
			content = htmlmin.minify(content,
				remove_comments=True,
				reduce_boolean_attributes=True)

		os.makedirs(os.path.dirname(p.dst), exist_ok=True)
		with open(p.dst, 'w') as f:
			f.write(content)

		return p

	except Exception as e:
		# Wrap all exceptions: there are issues with pickling and custom
		# exceptions
		raise Exception(str(e))
