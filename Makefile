JEKYLL=../jekyll/bin/jekyll

all:
	$(JEKYLL) --server

production: clean
	JEKYLL_ENV=production $(JEKYLL) --no-auto
	mkdir _site/assets/
	ruby lib/dump.rb css | java -jar lib/yuicompressor-2.4.6.jar --type css -o _site/assets/all.css
	ruby lib/dump.rb js | java -jar lib/yuicompressor-2.4.6.jar --type js -o _site/assets/all.js
	find _site -name "*.html" -exec java -jar lib/htmlcompressor-1.4.jar --compress-js {} -o {} \;
	rm -rf _site/css/ _site/js/
	cp .htaccess _site
	rsync -avhz --delete --progress _site/ clovar.com:/var/www/clovar.com/jekyll/

clean:
	rm -rf _site/
