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

IMG_EXTS = [
	'.gif',
	'.jpg',
	'.png',
]

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

			cats, imgs, blobs = self._load_pages(pool)
			self._build_pages(cats, pool)
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

	def _load_pages(self, pool):
		page_jobs = []
		img_jobs = []

		cats = {}
		imgs = []
		blobs = []

		path = pathlib.Path(self.conf['CONTENT_DIR'])
		for f in path.glob('**/*'):
			if f.suffix == '.j2':
				page_jobs.append(pool.apply_async(
					_load_page,
					(self.conf, f, )))
			elif f.suffix in IMG_EXTS:
				img_jobs.append(pool.apply_async(
					_load_img,
					(f, )))
			else:
				blobs.append(f)

		for job in page_jobs:
			p = job.get()
			cat = cats.setdefault(p.category, [])
			cat.append(p)

		for job in img_jobs:
			imgs.append(job.get())

		return cats, imgs, blobs

	def _build_pages(self, cats, pool):
		jobs = []

		for pages in cats.values():
			for page in pages:
				jobs.append(pool.apply_async(
					_build_page,
					(self.conf, page, cats, )))

		for job in jobs:
			job.get()

class Page(object):
	def __init__(self, conf, file, fm):
		self.content = fm.content
		self.metadata = fm.metadata

		if len(file.parts) == 2:
			self.name = file.stem
			self.category = '__page'

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

class Image(object):
	def __init__(self, file):
		self.file = file

def _load_page(conf, file):
	with file.open() as f:
		content = f.read()

	fm = frontmatter.loads(content)
	return Page(conf, file, fm)

def _build_page(conf, page, cats):
	try:
		tmpl = jinja.from_string(page.content)

		content = tmpl.render(
			conf=conf,
			page=page,
			meta=page.metadata,
			cats=cats)

		if not conf['DEBUG']:
			content = htmlmin.minify(content,
				remove_comments=True,
				reduce_boolean_attributes=True)

		os.makedirs(os.path.dirname(page.dst), exist_ok=True)
		with open(page.dst, 'w') as f:
			f.write(content)

	except Exception as e:
		# Wrap all exceptions: there are issues with pickling and custom
		# exceptions from jinja
		raise Exception(str(e))

def _load_img(file):
	return Image(file)
