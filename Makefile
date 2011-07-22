all:
	../jekyll/bin/jekyll --server

production: clean
	JEKYLL_ENV=production ../jekyll/bin/jekyll --no-auto
	mkdir _site/assets/
	java -jar lib/yuicompressor-2.4.6.jar -o _site/assets/all.css _site/css/*
	find _site/js/ -name "*.js" -exec cat {} \; | java -jar lib/yuicompressor-2.4.6.jar --type js -o _site/assets/all.js
	find _site -name "*.html" -exec java -jar lib/htmlcompressor-1.4.jar {} -o {} \;
	rm -rf _site/css/ _site/js/

clean:
	rm -rf _site/
