$(function() {
	if (!window.history.pushState) {
		return;
	}
	
	var pushState,
		$content = $("#content .body"),
		$window = $(window),
		load = function(url, ignoreState) {
			//don't allow the same page to load again
			//need to allow the request to go through on history.back()
			if (!ignoreState && url == window.location.pathname) {
				return;
			}
		
			$content.stop().fadeTo('slow', .5);
			$.ajax({
				url: url,
				success: function(data) {
					//idea + regex shameless stolen from jQuery $.load() source
					//don't allow scripts to load
					var $page = $("<div />").append(data.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, ''));
					
					//inject the response into the body
					//two chained finds is substantially faster than 1 big selector
					$content.html($page.find("#content").find(".body"));
					
					//set the title
					document.title = $page.find("title").text();
					
					//and use the fancy pushState stuff
					//unless we're going back in history
					ignoreState || window.history.pushState(null, null, url);
				},
				error: function(data) {
					$content.html("Aww, snap!  I can't load that page for you!  <a href='" + url + "'>Try again?</a>");
				},
				complete: function() {
					$content.stop().fadeTo('slow', 1);
					$window.scrollTop(0);
				}
			});
		}
	;
	
	$(window).bind('popstate', function(e) {
		load(document.location.pathname, true);
	});
	
	$("a:not([href^='http'])").live('click', function() {
		load($(this).attr("href"));
		return false;
	});
});
