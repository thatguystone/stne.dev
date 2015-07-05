import datetime
import functools
import hashlib
import json
import math
import multiprocessing
import multiprocessing.managers
import operator
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

URLRE = re.compile(r'url\((.*?)\)')
SCALEDRE = re.compile(r'.*(\.s(\d*x\d*c?)).*')
IDENTIFY_DIMS = re.compile(r'\d*x\d*')

SCISSORS = '<!-- >8 stas-content -->'
SCISSORS_END = '<!-- stas-content 8< -->'
MORE = '<!-- >8 more -->'

# Only set from pool processes
_globals = None

class Globals(object):
	# There are tons of issues passing jinja through pickle, so just have it
	# passed as an argument across the fork
	jinja = None
	unused_content = None
	jobq = None

class Stas(object):
	def __init__(self, conf):
		self.conf = self._conf_dict(conf)

	def build(self):
		assets_cache = self.conf['CACHE_DIR'] + '/webassets'
		_makedirs(assets_cache)

		debug = bool(self.conf['DEBUG'])
		combined = 'all'
		if debug:
			combined = 'debug'

		assets = webassets.Environment(
			self.conf['PUBLIC_DIR'] + '/assets/', '/assets',
			load_path=(self.conf['ASSETS_DIR'], ),
			debug=debug,
			cache=assets_cache,
			pyscss_debug_info=False)

		assets.register('js', webassets.Bundle(
			*self.conf['JS'],
			filters=['closure_js'],
			output=combined + '.js'))

		assets.register('css', webassets.Bundle(
			*self.conf['CSS'],
			filters=['pyscss', 'cssmin'],
			output=combined + '.css'))

		manager = SetManager()
		manager.start()

		self.cpus = multiprocessing.cpu_count()
		self.gs = Globals()
		self.gs.jinja = Jinja.init(self.conf, assets)
		self.gs.unused_content = manager.set()
		self.gs.jobq = multiprocessing.Queue()

		# Build the assets before running templates, or each subprocess
		# tries to build them independently
		asset_urls = []
		for bundle in assets:
			asset_urls += bundle.urls()

		scalers = []
		for _ in range(self.cpus):
			scaler = multiprocessing.Process(target=self._jobq)
			scaler.start()
			scalers.append(scaler)

		with self.pool() as pool:
			self._load(pool, assets)
			pool.close()
			pool.join()

		self.pages.sort()
		self._process_assets(asset_urls)
		self.gs.jinja.globals.update({
			'conf': self.conf,
			'data': self.data,
			'imgs': self.imgs,
			'pages': self.pages,
		})

		list_pages = []
		with self.pool() as pool:
			for page in self.pages.iter():
				if page.metadata.get('list_page', False):
					list_pages.append(page)
				else:
					def cb(page):
						def ret(c):
							page.content = c
						return ret

					pool.apply_async(page.build,
						callback=cb(page),
						error_callback=_throw)

			self._copy_blobs(pool)
			pool.close()
			pool.join()

		# Yet another spawn to get updated page content to these guys
		with self.pool() as pool:
			self._build_list_pages(list_pages, pool)
			pool.close()
			pool.join()

		for _ in range(len(scalers)):
			self.gs.jobq.put(None)
		for s in scalers:
			s.join()

		# Sorted in reverse, this should make sure that any empty directories
		# are removed recursively
		for k in sorted(self.gs.unused_content.copy(), reverse=True):
			if os.path.isfile(k):
				os.unlink(k)
			else:
				try:
					os.rmdir(k)
				except OSError:
					pass

	def pool(self):
		return multiprocessing.Pool(self.cpus, self._winit)

	def _conf_dict(self, conf):
		d = {}
		for k in dir(conf):
			if k.startswith('_') or k.upper() != k:
				continue
			d[k] = getattr(conf, k)
		return d

	def _winit(self):
		signal.signal(signal.SIGINT, signal.SIG_IGN)

		global _globals
		_globals = self.gs

	def _jobq(self):
		self._winit()

		while True:
			job = self.gs.jobq.get()
			if not job:
				return
			job()

	def _load(self, pool, assets):
		pages = self.pages = Pages()
		imgs = self.imgs = Images()
		data = self.data = {}
		self.blobs = []

		path = pathlib.Path(self.conf['DATA_DIR'])
		for f in path.glob('*'):
			pool.apply_async(
				_load_data,
				(self.conf, f, ),
				callback=lambda r: operator.setitem(data, r[0], r[1]),
				error_callback=_throw)

		path = pathlib.Path(self.conf['CONTENT_DIR'])
		for f in path.glob('**/*'):
			if f.suffix == '.j2':
				pool.apply_async(
					_load_page,
					(self.conf, f, ),
					callback=lambda r: pages.add(r),
					error_callback=_throw)
			elif f.suffix in IMG_EXTS:
				pool.apply_async(
					_load_img,
					(self.conf, f, ),
					callback=lambda r: imgs.add(r),
					error_callback=_throw)
			elif f.is_file() and f.suffix != '.meta':
				self.blobs.append(f)

		uuc = set()
		path = pathlib.Path(self.conf['PUBLIC_DIR'])
		for f in path.glob('**/*'):
			uuc.add(str(f))

		# Bulk update after reading, it's faster
		self.gs.unused_content.update(uuc)

	def _process_assets(self, urls):
		for url in urls:
			if not url.startswith(self.conf['PUBLIC_DIR']):
				url = self.conf['PUBLIC_DIR'] + '/%s' % url

			_mark_used(urllib.parse.urlparse(url).path, gs=self.gs)

			if '.css' in url:
				path = urllib.parse.urlparse(url).path
				with open(path) as f:
					css = f.read()

				for rel, css_path in self._css_find_urls(css):
					match = SCALEDRE.match(rel)
					if match:
						rel = rel.replace(match.group(1), '')
						final = self._scale_css_img(rel, match.group(2))
					else:
						final = self._scale_css_img(rel, None)

					css = css.replace(css_path, '"%s"' % final)

				with open(path, 'w') as f:
					f.write(css)

	def _css_find_urls(self, sheet):
		for url in URLRE.findall(sheet):
			path = url.replace('"', '').replace("'", '')
			if path.startswith("/assets/"):
				yield path[1:], url

	def _scale_css_img(self, url, scale):
		img = Image(self.conf, pathlib.Path(url), None)

		if not scale:
			return img.scale(0, 0, False, gs=self.gs)

		crop = scale.endswith('c')
		if crop:
			scale = scale[:-1]

		sizes = scale.split('x')
		width = int(sizes[0])
		height = int(sizes[1])

		return img.scale(width, height, crop, gs=self.gs)

	def _build_list_pages(self, list_pages, pool):
		for page in list_pages:
			if not page.category:
				pool.apply_async(page.build,
					callback=lambda r: r,
					error_callback=_throw)
			else:
				subs = len(self.pages.cats[page.category])
				page_count = math.ceil(subs / self.conf['PER_PAGE'])

				for page_num in range(page_count):
					list_start = page_num * self.conf['PER_PAGE']
					list_end = list_start + self.conf['PER_PAGE']
					pool.apply_async(page.build,
						kwds={
							'page_num': page_num,
							'list_start': list_start,
							'list_end': list_end,
							'list_has_next': page_num < (page_count - 1),
						},
						callback=lambda r: r,
						error_callback=_throw)

	def _copy_blobs(self, pool):
		for blob in self.blobs:
			pool.apply_async(
				_copy_blob,
				(self.conf, blob, ),
				callback=lambda r: r,
				error_callback=_throw)

class SetManager(multiprocessing.managers.BaseManager):
	pass
SetManager.register('set', set)

class Pages(object):
	def __init__(self):
		self.cats = {}

	def add(self, page):
		cat = self.cats.setdefault(page.category, [])
		cat.append(page)

	def sort(self):
		for posts in self.cats.values():
			posts.sort(key=lambda p: str(p.src), reverse=True)

	def _filter_posts(self, cat):
		return [p for p in self.cats[cat] if p.date]

	def posts(self, cat=None):
		if cat:
			return self._filter_posts(cat)

		posts = []
		for cat in self.cats:
			posts += self._filter_posts(cat)

		posts.sort(key=lambda p: str(p.src), reverse=True)

		return posts

	def iter(self):
		for cat in self.cats.values():
			for page in cat:
				yield page

class Page(object):
	def __init__(self, conf, file, fm):
		self.src = file
		self.conf = conf
		self.tmpl_content = fm.content
		self.metadata = fm.metadata

		self.name, self.category, self.dst, self.date = _determine_dest(
			conf, file,
			is_page=True)

		self.abs_url = '/' + str(self.dst.relative_to(self.conf['PUBLIC_DIR']).parent) + '/'

	def summary(self):
		more = self.content.find(MORE)
		if more < 0:
			raise Exception('%s is missing more scissors' % self.src)

		return self.content[:more]

	def build(self, page_num=0, list_start=0, list_end=0, **kwargs):
		try:
			jinja = _globals.jinja

			if self.category:
				page_list = jinja.globals['pages'].posts(self.category)
				page_list = page_list[list_start:list_end]
			else:
				page_list = jinja.globals['pages'].posts()[:self.conf['PER_PAGE']]

			tmpl = jinja.from_string(self.tmpl_content)
			content = tmpl.render(
				conf=self.conf,
				page=self,
				page_num=page_num,
				page_list=page_list,
				**kwargs)

			dst = self.dst
			if page_num:
				dst = pathlib.Path('%s/page/%d/%s' % (
					dst.parent,
					page_num,
					dst.name))

			_makedirs(dst)
			with dst.open('w') as f:
				f.write(content)

			if not self.conf['DEBUG']:
				# From: https://github.com/tdewolff/minify/tree/master/cmd/minify
				status = subprocess.call([
					'minify',
					'-o', str(dst),
					str(dst)])
				if status:
					raise Exception('failed to minify %s' % self.src)

			_mark_used(dst)

			scissors = content.find(SCISSORS)
			scissors_end = content.find(SCISSORS_END)
			if scissors >= 0 and scissors_end >= 0:
				return content[scissors+len(SCISSORS):scissors_end]

			return ''

		except Exception as e:
			# Wrap all exceptions: there are issues with pickling and custom
			# exceptions from jinja
			raise Exception('in %s: %s' % (self.src, str(e)))

class Images(object):
	def __init__(self):
		self.imgs = {}

	def get(self, path):
		return self.imgs[path]

	def all(self):
		imgs = [str(img.src) for img in self.imgs.values() if img.gallery]
		imgs.sort(reverse=True)
		return imgs

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

		self.gallery = self.metadata.get('gallery', True)

		self.name, \
			self.category, \
			self.dst, \
			self.date = _determine_dest(conf, file)
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

	def _scale(self, dst, scale_dims, crop, dims, quality):
		_mark_used(dst)
		if self._changed(dst):
			args = [
				'convert',
				str(self.src),
				'-quality', str(quality),
				'-scale', scale_dims]

			if crop:
				args += ['-gravity', 'center', '-extent', dims]

			_makedirs(dst)
			status = subprocess.call(args + [str(dst)])
			if status:
				raise Exception('failed to scale image %s' % self.src)

			os.utime(str(dst), (0, self.stat.st_mtime))

	def title(self):
		return self.metadata.get('title', '')

	def scale(self, width, height, crop, quality=92, ext=None, gs=None):
		if not gs:
			gs = _globals

		if not ext:
			ext = self.dst.suffix

		if ext[0] != '.':
			ext = '.' + ext

		if not width and not height and not crop and ext == self.dst.suffix:
			self._copy()
			return self.abs

		width = int(width)
		height = int(height)

		if not width:
			width = ''
		if not height:
			height = ''

		# Use something like '400x' to scale to a width of 400
		dims = '%sx%s' % (str(width), str(height))
		scale_dims = dims
		suffix = dims
		if crop:
			suffix += 'c'
			scale_dims += '^'

		final_name = '%s.s%s%s' % (self.dst.stem, suffix, ext)
		dst = self.dst.with_name(final_name)
		abs_path = self.abs.with_name(final_name)

		gs.jobq.put(functools.partial(self._scale,
			dst,
			scale_dims,
			crop,
			dims,
			quality))

		return abs_path

class Jinja(object):
	def init(conf, assets):
		jinja = jinja2.Environment(
			loader=jinja2.FileSystemLoader(conf['TEMPLATE_DIR']),
			extensions=[
				'webassets.ext.jinja2.AssetsExtension',
			])
		jinja.filters['markdown'] = Jinja._filter_markdown
		jinja.assets_environment = assets

		jinja.globals['now'] = Jinja._now
		jinja.globals['get_img'] = Jinja._get_img

		return jinja

	def _now(format):
		return datetime.datetime.now().strftime(format)

	def _filter_markdown(text):
		return jinja2.Markup(markdown.markdown(text))

	@jinja2.contextfunction
	def _get_img(ctx, src):
		conf = ctx['conf']

		to = src
		if not src.startswith(conf['CONTENT_DIR']):
			to = str(ctx['page'].src.parent) + '/' + src

		to = os.path.normpath(to)

		try:
			return ctx['imgs'].get(to)
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

	return name, category, pathlib.Path(dst), date

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
	_, _, dst, _ = _determine_dest(conf, file)
	_makedirs(dst)
	_mark_used(dst)
	shutil.copyfile(str(file), str(dst))

def _mark_used(dst, gs=None):
	if not gs:
		gs = _globals

	if gs:
		dst = os.path.normpath(str(dst))
		gs.unused_content.discard(dst)

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

def _throw(e):
	raise e
