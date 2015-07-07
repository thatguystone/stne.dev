debug:
	acrylic conf_debug.yml

publish:
	acrylic conf_debug.yml conf_publish.yml
	# rsync -av --delete public/ stoney.io:/var/www/stoney.io/

clean:
	rm -rf public/
