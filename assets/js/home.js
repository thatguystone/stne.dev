$(function() {
	if (window.wordCloudData) {
		var $el = $('#' + wordCloudData.id);

		if (!WordCloud.isSupported) {
			$el.remove();
			return;
		}

		WordCloud(
			$el[0],
			{
				gridSize: 3,
				list: wordCloudData.data,
				rotateRatio: .8,
				weightFactor: .4,
			});
	}
});
