import webassets

TITLE = 'Andrew Stone'
SITEURL = ''

DEBUG = True
DEBUG_PORT = 8000

ASSETS_DIR = 'assets/'
CONTENT_DIR = 'content/'
TEMPLATE_DIR = 'templates/'

PUBLIC_DIR = 'public/'

ASSETS = {
	'js': webassets.Bundle(
		'js/main.js',
		filters='closure_js',
		output='all.js'),
	'css': webassets.Bundle(
		'css/main.scss',
		filters='pyscss,cssmin',
		output='all.css'),
}
