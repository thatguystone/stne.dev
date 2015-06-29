debug: ve
	./build.py --debug

publish: ve clean
	./build.py
	# rsync public/ stoney.io:/var/www/stoney.io/

clean:
	rm -rf public/

ve:
	virtualenv -p python3 ve
	ve/bin/pip install -r requirements.txt
