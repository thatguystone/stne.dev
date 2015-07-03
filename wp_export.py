import xml.etree.ElementTree as ET
import os
import datetime

tree = ET.parse('wp_export.xml')
root = tree.getroot()

ns = {
	'content': 'http://purl.org/rss/1.0/modules/content/',
	'wp': 'http://wordpress.org/export/1.2/',
}

post_format = '''---
title: "{title}"
---

{{% extends "base.j2" %}}

{{% block content %}}
{{% filter markdown %}}

<!-- >8 more -->

{content}

{{% endfilter %}}
{{% endblock %}}
'''

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

	with open(page, 'w') as f:
		f.write(post_format.format(
			title=title,
			content=content))
