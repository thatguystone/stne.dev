debug: ve
	./build.py --debug

publish: ve
	./build.py
	rsync -av --delete public/ stoney.io:/var/www/stoney.io/

clean:
	rm -rf public/

ve:
	virtualenv -p python3 ve
	ve/bin/pip install -r requirements.txt
