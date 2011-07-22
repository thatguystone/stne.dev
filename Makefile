all:
	../jekyll/bin/jekyll --server

production:
	rm -rf _site/
	JEKYLL_ENV=production ../jekyll/bin/jekyll --no-auto
	mkdir _site/assets/
	java -jar lib/yuicompressor-2.4.6.jar -o _site/assets/all.css _site/css/* > /dev/null 2>&1 || true
	java -jar lib/yuicompressor-2.4.6.jar -o _site/assets/all.js _site/js/* > /dev/null 2>&1 || true
	rm -rf _site/js/ _site/css/
	find _site -name "*.html" -exec java -jar lib/htmlcompressor-1.4.jar {} -o {} \;
