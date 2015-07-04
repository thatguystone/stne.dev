import datetime
import multiprocessing
import os
import pathlib
import re
import urllib.request
import xml.etree.ElementTree as ET

from pyquery import PyQuery as pq

tree = ET.parse('wp_export.xml')
root = tree.getroot()

ns = {
	'content': 'http://purl.org/rss/1.0/modules/content/',
	'wp': 'http://wordpress.org/export/1.2/',
}

meta_format = '''---
title: "%s"
---
'''

post_format = '''---
title: "{title}"
---

{{% extends "post.j2" %}}

{{% block post %}}

<!-- >8 more -->

{content}

{{% endblock %}}
'''

dims = re.compile('-\d{3}x\d{3}')

def fetch(url, dst):
	res = urllib.request.urlopen(url)
	with open(dst, 'wb') as f:
		f.write(res.read())

cpus = multiprocessing.cpu_count() * 4
pool = multiprocessing.Pool(cpus)
jobs = []

for item in root.findall('channel')[0].findall('item'):
	title = item.find('title', ns).text
	content = item.find('content:encoded', ns).text
	date = item.find('wp:post_date', ns).text
	slug = item.find('wp:post_name', ns).text

	date = datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S')

	path = 'content/blog/%s-%s' % (date.strftime('%Y-%m-%d'), slug)
	if '<img' in content:
		page = '%s/index.j2' % path
		os.makedirs(path, exist_ok=True)
	else:
		page = '%s.j2' % path

	pqc = pq(content)
	imgas = pqc.find('a').filter(lambda i: pq(this).find('img'))
	for imga in imgas:
		img = pq(imga).find('img')
		img_title = img.attr('title')
		src = img.attr('src')
		src = re.sub(dims, '', src)
		base = os.path.basename(src)

		repl = '{{ macros.img("%s") }}' % (base)
		pq(imga).replaceWith(repl)

		dst = path + '/' + base

		with open(dst + '.meta', 'w') as f:
			f.write(meta_format % img_title.replace('"', '\\"'))

		# jobs.append(pool.apply_async(fetch, (src, dst)))

	content = pqc.html()
	content = content.replace('  ', ' ')

	# with open(page, 'w') as f:
	# 	f.write(post_format.format(
	# 		title=title,
	# 		content=content))

for job in jobs:
	job.get()
