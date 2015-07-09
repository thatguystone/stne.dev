debug:
	acrylic conf_debug.yml

publish: closure-compiler.jar
	acrylic conf_debug.yml conf_publish.yml
	rsync -av --delete public/ stoney.io:/var/www/stoney.io/

closure-compiler.jar:
	wget http://dl.google.com/closure-compiler/compiler-latest.zip
	unzip compiler-latest.zip compiler.jar
	rm compiler-latest.zip
	mv compiler.jar $@

clean:
	rm -rf public/
