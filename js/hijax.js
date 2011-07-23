$(function() {
	if (!window.history.pushState) {
		return;
	}
	
	var pushState,
		$content = $("#content .body"),
		load = function(url) {
			//don't allow the same page to load again
			if (url == window.location.pathname) {
				return;
			}
		
			$content.fadeTo('slow', .5);
			$.ajax({
				url: url,
				success: function(data) {
					//idea + regex shameless stolen from jQuery $.load() source
					//don't allow scripts to load
					var $page = $("<div />").append(data.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, ''));
					
					//inject the response into the body
					$content.html($page.find("#content .body"));
					
					//set the title
					document.title = $page.find("title").text();
					
					//and use the fancy pushState stuff
					window.history.pushState(null, null, url);
				},
				error: function(data) {
					$content.html("Aww, snap!  I can't load that page for you!  <a href='" + url + "'>Try again?</a>");
				},
				complete: function() {
					$content.stop().fadeTo('slow', 1);
				}
			});
		}
	;
	
	$(window).bind('popstate', function(e) {
		load(e.target.location.href);
	});
	
	$("a:not([href^='http'])").live('click', function() {
		load($(this).attr("href"));
		return false;
	});
});
