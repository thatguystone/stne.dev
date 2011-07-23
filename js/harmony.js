/*!
 * Mad props to Mr. Doob: http://mrdoob.com/projects/harmony/ (https://github.com/mrdoob/harmony)
 */
(function($) {
	//the brushses need these guys
	BRUSH_SIZE = 1;
	COLOR = [62,97,29];
	BRUSH_PRESSURE = 1;
	brushes = {};
	
	var init = function() {
		var width, brush,
			$window = $(window),
			$container = $("#header"),
			height = $container.height(),
			$canvas = $('<canvas class="drawing" height="' + height + '" />'),
			context = $canvas[0].getContext('2d'),
			newBrush = function() {
				brush = new brushes[Object.keys(brushes).shuffle()[0]](context);
			}
		;
		
		$window
			.resize(function() {
				SCREEN_WIDTH = $window.width();
				SCREEN_HEIGHT = $window.height();
				
				width = $container.width();
				if ($canvas.attr('width') != width) {
					$canvas.attr('width', width);
				}
			})
			.resize()
		;
		
		$canvas
			.hover(
				function(e) {
					brush.strokeStart(e.clientX, e.clientY);
				},
				function() {
					brush.strokeEnd();
				}
			)
			.mousemove(function(e) {
				brush.stroke(e.clientX, e.clientY);
			})
			.click(function() {
				context.clearRect(0, 0, width, height);
				newBrush();
			})
		;
		
		$container.append($canvas);
		newBrush();
	};
	
	$(init);
})(jQuery);
