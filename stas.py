import datetime
import functools
import hashlib
import json
import multiprocessing
import multiprocessing.managers
import os
import pathlib
import re
import shutil
import signal
import subprocess
import urllib.parse

import frontmatter
import jinja2
import markdown
import webassets

IMG_EXTS = [
	'.gif',
	'.jpg',
	'.png',
]

URLRE = re.compile(r'url\((.*)\)')
SCALEDRE = re.compile(r'.*(\.s(\d*x\d*c?)).*')

# Only set from pool processes
jinja = None
used_content = None

class Stas(object):
	def __init__(self, conf):
		self.conf = self._conf_dict(conf)

	def build(self):
		assets_cache = self.conf['CACHE_DIR'] + '/webassets'
		_makedirs(assets_cache)

		assets = webassets.Environment(
			self.conf['PUBLIC_DIR'] + '/assets/', '/assets',
			load_path=(self.conf['ASSETS_DIR'], ),
			debug=bool(self.conf['DEBUG']),
			cache=assets_cache)

		assets.register('js', webassets.Bundle(
			*self.conf['JS'],
			filters=['closure_js'],
			output='all.js'))

		assets.register('css', webassets.Bundle(
			*self.conf['CSS'],
			filters=['pyscss', 'cssmin'],
			output='all.css'))

		jinja = Jinja.init(self.conf, assets)
		cpus = multiprocessing.cpu_count() * 2
		manager = SetManager()
		manager.start()

		# Build the assets before running templates, or each subprocess
		# tries to build them independently
		asset_urls = []
		for bundle in assets:
			asset_urls += bundle.urls()

		with multiprocessing.Pool(cpus, self._worker_init, (jinja, )) as pool:
			publics, pages, imgs, data, blobs = self._load(pool, assets)
			jinja.globals.update({
				'conf': self.conf,
				'data': data,
				'imgs': imgs,
				'pages': pages,
			})

		uc = manager.set(publics)

		with multiprocessing.Pool(cpus, self._worker_init, (jinja, uc)) as pool:
			jobs = []

			self._build_pages(pages, pool, jobs)
			self._copy_blobs(blobs, pool, jobs)
			self._finalize_assets(asset_urls, pool, jobs, uc)

			for job in jobs:
				job.get()

		# Sorted in reverse, this should make sure that any empty directories
		# are removed recursively
		for k in sorted(uc.copy(), reverse=True):
			if os.path.isfile(k):
				os.unlink(k)
			else:
				try:
					os.rmdir(k)
				except OSError:
					pass

	def _conf_dict(self, conf):
		d = {}
		for k in dir(conf):
			if k.startswith('_') or k.upper() != k:
				continue
			d[k] = getattr(conf, k)
		return d

	def _worker_init(self, j, uc=None):
		signal.signal(signal.SIGINT, signal.SIG_IGN)

		# There are tons of issues passing jinja through pickle, so just have
		# it passed as an argument across the fork
		global jinja, used_content
		jinja = j
		used_content = uc

	def _load(self, pool, assets):
		publics = set()
		pages = Pages()
		imgs = Images()
		data = {}
		blobs = []

		data_jobs = []
		page_jobs = []
		img_jobs = []

		path = pathlib.Path(self.conf['DATA_DIR'])
		for f in path.glob('*'):
			data_jobs.append(pool.apply_async(
				_load_data,
				(self.conf, f, )))

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

		path = pathlib.Path(self.conf['PUBLIC_DIR'])
		for f in path.glob('**/*'):
			publics.add(str(f))

		for job in data_jobs:
			d = job.get()
			data[d[0]] = d[1]

		for job in page_jobs:
			pages.add(job.get())

		for job in img_jobs:
			imgs.add(job.get())

		return publics, pages, imgs, data, blobs

	def _finalize_assets(self, urls, pool, jobs, uc):
		for url in urls:
			if not url.startswith(self.conf['PUBLIC_DIR']):
				url = self.conf['PUBLIC_DIR'] + '/%s' % url

			_mark_used(urllib.parse.urlparse(url).path, uc=uc)

			if '.css' in url:
				path = urllib.parse.urlparse(url).path
				with open(path) as f:
					css = f.read()

				for rel, css_path in _css_find_urls(css):
					match = SCALEDRE.match(rel)
					if match:
						rel = rel.replace(match.group(1), '')
						final, job = self._scale_css_img(rel, match.group(2))
					else:
						final, job = self._scale_css_img(rel, None)

					jobs.append(pool.apply_async(job))
					css = css.replace(css_path, '"%s"' % final)

				with open(path, 'w') as f:
					f.write(css)

	def _scale_css_img(self, url, scale):
		img = Image(self.conf, pathlib.Path(url), None)

		if not scale:
			return img.scale(0, 0, False, None, as_job=True)

		crop = scale.endswith('c')
		if crop:
			scale = scale[:-1]

		sizes = scale.split('x')
		width = int(sizes[0])
		height = int(sizes[1])

		return img.scale(width, height, crop, None, as_job=True)

	def _build_pages(self, pages, pool, jobs):
		for page in pages.iter():
			jobs.append(pool.apply_async(page.build))

	def _copy_blobs(self, blobs, pool, jobs):
		for blob in blobs:
			jobs.append(pool.apply_async(
				_copy_blob,
				(self.conf, blob, )))

class SetManager(multiprocessing.managers.BaseManager):
	pass
SetManager.register('set', set)

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

	def build(self):
		try:
			tmpl = jinja.from_string(self.content)
			content = tmpl.render(page=self)

			_makedirs(self.dst)
			with self.dst.open('w') as f:
				f.write(content)

			if not self.conf['DEBUG']:
				# From: https://github.com/tdewolff/minify/tree/master/cmd/minify
				status = subprocess.call([
					'minify',
					'-o', str(self.dst),
					str(self.dst)])
				if status:
					raise Exception('failed to minify %s' % self.src)

			_mark_used(self.dst)

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

	def _copy(self):
		_mark_used(self.dst)
		if self._changed(self.dst):
			_makedirs(self.dst)
			shutil.copyfile(str(self.src), str(self.dst))

	def _scale(self, dst, scale_dims, crop, dims):
		_mark_used(dst)
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

	def scale(self, width, height, crop, ext, as_job=False):
		if not ext:
			ext = self.dst.suffix

		if ext[0] != '.':
			ext = '.' + ext

		if not width and not height and not crop and ext == self.dst.suffix:
			if as_job:
				return self.abs, self._copy
			self._copy()
			return self.abs

		dims = '%dx%d' % (width, height)
		scale_dims = dims
		suffix = dims
		if crop:
			suffix += 'c'
			scale_dims += '^'

		final_name = '%s.s%s%s' % (self.dst.stem, suffix, ext)
		dst = self.dst.with_name(final_name)
		abs_path = self.abs.with_name(final_name)

		if as_job:
			return abs_path, functools.partial(self._scale, dst, scale_dims, crop, dims)

		self._scale(dst, scale_dims, crop, dims)
		return abs_path

class Jinja(object):
	def init(conf, assets):
		jinja = jinja2.Environment(
			loader=jinja2.FileSystemLoader(conf['TEMPLATE_DIR']),
			extensions=[
				'webassets.ext.jinja2.AssetsExtension',
			])
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

def _load_data(conf, file):
	cache = pathlib.Path(conf['CACHE_DIR'] + '/' + str(file))

	if cache.exists() and not _src_changed(file, cache):
		with cache.open() as f:
			data = json.load(f)
		if datetime.datetime.fromtimestamp(data[0]) > datetime.datetime.now():
			return file.name, data[1]

	if os.access(str(file), os.X_OK):
		p = subprocess.Popen([str(file)], stdout=subprocess.PIPE)
		stdout = p.communicate()[0]
		if p.returncode != 0:
			raise Exception('failed to execute %s: status=%d' % (
				file.name,
				p.returncode))

		res = None
		if stdout:
			stdout = stdout.decode('utf-8').strip()
			res = json.loads(stdout)

		if isinstance(res, dict):
			exp = res.get('stas_expires', 0)
			del res['stas_expires']
			if exp > 0:
				_makedirs(cache)
				with cache.open('w') as f:
					json.dump([exp, res], f)
				os.utime(str(cache), (0, file.stat().st_mtime))

		return file.name, res

	with file.open() as f:
		return file.name, json.load(f)

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
	_mark_used(dst)
	shutil.copyfile(str(file), str(dst))

def _css_find_urls(sheet):
	for url in URLRE.findall(sheet):
		path = url.replace('"', '').replace("'", '')
		if path.startswith("/assets/"):
			yield path[1:], url

def _mark_used(dst, uc=None):
	if not uc:
		uc = used_content

	if uc:
		dst = os.path.normpath(str(dst))
		uc.discard(dst)

def _src_changed(src, dst):
	try:
		srcs = src.stat()
		dsts = dst.stat()
		if srcs.st_mtime == dsts.st_mtime:
			return False
	except FileNotFoundError:
		pass

	return True

def _makedirs(dst):
	if isinstance(dst, pathlib.Path):
		dst = str(dst.parent)

	os.makedirs(dst, exist_ok=True)
