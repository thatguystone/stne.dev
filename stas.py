import datetime
import hashlib
import multiprocessing
import os
import pathlib
import re
import shutil
import signal
import subprocess

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

URLRE = re.compile(r'url\((.*)\)')

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

		assets.register('js', webassets.Bundle(
			*self.conf['JS'],
			filters='closure_js',
			output='all.js'))

		assets.register('css', webassets.Bundle(
			*self.conf['CSS'],
			filters=['pyscss', CSSFilter(self.conf), 'cssmin'],
			output='all.css'))

		jinja = Jinja.init(self.conf, assets)

		try:
			cpus = multiprocessing.cpu_count()
			pool = multiprocessing.Pool(cpus * 2,
				self._worker_init, (jinja, ))

			pages, imgs, blobs = self._load_pages(pool)

			jobs = []
			self._build_pages(pages, imgs, jobs, pool)
			self._copy_blobs(blobs, jobs, pool)

			for job in jobs:
				job.get()
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

	def _load_pages(self, pool):
		page_jobs = []
		img_jobs = []

		pages = Pages()
		imgs = Images()
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
					(self.conf, f, )))
			elif f.is_file():
				blobs.append(f)

		for job in page_jobs:
			pages.add(job.get())

		for job in img_jobs:
			imgs.add(job.get())

		return pages, imgs, blobs

	def _build_pages(self, pages, imgs, jobs, pool):
		for page in pages.iter():
			jobs.append(pool.apply_async(
				page.build,
				(pages, imgs, )))

	def _copy_blobs(self, blobs, jobs, pool):
		for blob in blobs:
			jobs.append(pool.apply_async(
					_copy_blob,
					(self.conf, blob, )))

class CSSFilter(webassets.filter.Filter):
	name = 'stas_css'
	max_debug_level = None

	def __init__(self, conf):
		super().__init__()
		self.conf = conf

	def input(self, _in, out, **kwargs):
		out.write(_in.read())

	def output(self, _in, out, **kwargs):
		sheet = _in.read()
		for url in URLRE.findall(sheet):
			path = url.replace('"', '').replace("'", '')
			if not path.startswith("/assets/"):
				continue

			scaled = self.scale(path[1:])
			sheet = sheet.replace(url, '"%s"' % scaled)

		out.write(sheet)

	def scale(self, url):
		parts = url.split(':')
		img = Image(self.conf, pathlib.Path(parts[0]), None)

		if len(parts) == 1:
			return img.scale(0, 0, False, None)

		size = parts[1]
		parts = size.split('@')

		mul = 1
		if len(parts) > 1:
			mul = int(parts[1][0])

		size = parts[0]
		crop = size.endswith('c')
		if crop:
			size = size[:-1]

		sizes = size.split('x')
		width = int(sizes[0]) * mul
		height = int(sizes[1]) * mul

		return img.scale(width, height, crop, None)

class Pages(object):
	def __init__(self):
		self.cats = {}

	def add(self, page):
		cat = self.cats.setdefault(page.category, [])
		cat.append(page)

	def iter(self):
		for cat in self.cats.values():
			for page in cat:
				yield page

class Page(object):
	def __init__(self, conf, file, fm):
		self.src = file
		self.conf = conf
		self.content = fm.content
		self.metadata = fm.metadata

		self.name, self.category, self.dst = _determine_dest(
			conf, file,
			is_page=True)

	def build(self, pages, imgs):
		try:
			tmpl = jinja.from_string(self.content)

			content = tmpl.render(
				conf=self.conf,
				page=self,
				pages=pages,
				imgs=imgs,)

			if not self.conf['DEBUG']:
				content = htmlmin.minify(content,
					remove_comments=True,
					reduce_boolean_attributes=True)

			_makedirs(self.dst)
			with self.dst.open('w') as f:
				f.write(content)

		except Exception as e:
			# Wrap all exceptions: there are issues with pickling and custom
			# exceptions from jinja
			raise Exception(str(e))

class Images(object):
	def __init__(self):
		self.imgs = {}

	def get(self, path):
		return self.imgs[path]

	def add(self, img):
		self.imgs[str(img.src)] = img

class Image(object):
	def __init__(self, conf, file, fm):
		self.src = file
		self.stat = file.stat()

		if fm:
			self.metadata = fm.metadata
		else:
			self.metadata = {}

		self.name, self.category, self.dst = _determine_dest(conf, file)
		self.abs = pathlib.Path('/' + '/'.join(self.dst.parts[1:]))

	def _changed(self, dst):
		try:
			dsts = dst.stat()
			if dsts.st_mtime == self.stat.st_mtime:
				return False
		except FileNotFoundError:
			pass

		return True

	def scale(self, width, height, crop, ext):
		if not ext:
			ext = self.dst.suffix

		if ext[0] != '.':
			ext = '.' + ext

		if not width and not height and not crop and ext == self.dst.suffix:
			if self._changed(self.dst):
				_makedirs(self.dst)
				shutil.copyfile(str(self.src), str(self.dst))
			return self.abs

		dims = '%dx%d' % (width, height)
		scale_dims = dims
		suffix = dims
		if crop:
			suffix += 'c'
			scale_dims += '^'

		final_name = '%s.%s%s' % (self.dst.stem, suffix, ext)
		dst = self.dst.with_name(final_name)
		if self._changed(dst):
			args = [
				'convert',
				str(self.src),
				'-scale', scale_dims]

			if crop:
				args += ['-gravity', 'center', '-extent', dims]

			_makedirs(dst)
			status = subprocess.call(args + [str(dst)])
			if status:
				raise Exception('failed to scale image %s' % self.src)

			os.utime(str(dst), (0, self.stat.st_mtime))

		return self.abs.with_name(final_name)

class Jinja(object):
	def init(conf, assets):
		jinja = jinja2.Environment(
			loader=jinja2.FileSystemLoader(conf['TEMPLATE_DIR']),
			extensions=[
			'webassets.ext.jinja2.AssetsExtension',
			'jinja2_highlight.HighlightExtension'])
		jinja.filters['markdown'] = Jinja._filter_markdown
		jinja.filters['img'] = Jinja._filter_img
		jinja.assets_environment = assets

		jinja.globals['now'] = Jinja._now

		return jinja

	def _now(format):
		return datetime.datetime.now().strftime(format)

	def _filter_markdown(text):
		return jinja2.Markup(markdown.markdown(text))

	@jinja2.contextfilter
	def _filter_img(ctx, src, width=0, height=0, crop='', ext=''):
		to = str(ctx['page'].src.parent) + '/' + src
		to = os.path.normpath(to)

		try:
			img = ctx['imgs'].get(to)
			return img.scale(width, height, crop, ext)
		except KeyError:
			raise Exception('img %s does not exist' % to)

def _parse_datetime(dir):
	date = datetime.datetime.strptime(
		dir[:10],
		'%Y-%m-%d')
	dir = dir[11:]

	return date, dir

def _determine_dest(conf, file, is_page=False):
	parts = file.parts
	if file.parts[0] == conf['CONTENT_DIR'].strip('/'):
		parts = parts[1:]

	if file.suffix == '.j2':
		if len(parts) == 1:
			parts = ('', ) + parts

		name = file.stem
		if name == 'index':
			name = parts[-2]
	else:
		name = file.stem

	# See if in a sub-dir that's really just holding content
	dir = None
	if len(parts) > 1:
		try:
			date, dir = _parse_datetime(parts[-2])
			name = file.stem
			parts = parts[:-1]
		except ValueError:
			pass

	category = "/".join(parts[:-1])

	if not dir:
		try:
			date, dir = _parse_datetime(name)
		except ValueError:
			date = None
			dir = ''

	if date:
		dst = '%s/%s/%s/%s' % (
			conf['PUBLIC_DIR'],
			category,
			date.strftime('%Y/%m/%d'),
			dir)
	else:
		dst = '%s/%s/%s' % (
			conf['PUBLIC_DIR'],
			category,
			dir)

	if is_page:
		dst += '/index.html'
	else:
		dst += '/%s%s' % (name, file.suffix)

	return name, category, pathlib.Path(dst)

def _load_page(conf, file):
	with file.open() as f:
		content = f.read()

	fm = frontmatter.loads(content)
	return Page(conf, file, fm)

def _load_img(conf, file):
	meta = file.with_name(file.name + '.meta')

	fm = None
	if meta.exists():
		fm = frontmatter.load(str(meta))

	return Image(conf, file, fm)

def _copy_blob(conf, file):
	_, _, dst = _determine_dest(conf, file)
	_makedirs(dst)
	shutil.copyfile(str(file), str(dst))

def _makedirs(dst):
	os.makedirs(str(dst.parent), exist_ok=True)
