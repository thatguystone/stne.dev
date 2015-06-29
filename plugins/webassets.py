from pelican import signals

def test(sender):
	pass

def register():
    signals.initialized.connect(test)
