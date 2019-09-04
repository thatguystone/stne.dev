publish:
	rsync -av --progress --delete ./public/ stne.dev:/var/www/stne.dev/www/
