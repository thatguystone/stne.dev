debug:
	go run ./site

publish:
	go run ./site crawl

clean:
	rm -rf public/
	rm -rf .cache/
