Object.keys = Object.keys || function(obj) {
	var k,
		keys = []
	;
	
	for (k in obj) {
		keys.push(k);
	}
	
	return keys;
};
