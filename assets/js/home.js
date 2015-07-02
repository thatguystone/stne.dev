$(function() {
	if (window.wordCloudData) {
		var $el = $('#' + wordCloudData.id);

		if (!WordCloud.isSupported) {
			$el.remove();
			return;
		}

		WordCloud($el[0], {
			gridSize: 5,
			list: wordCloudData.data
		});
	}
});
