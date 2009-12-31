<div class="header">
	<div class="logo"><a href="."><img src="images/clovar.png" alt="Home"></a></div>
	<div class="tabs">
		<a href="index.php"><img src="images/tab_home.png" alt="Home" <?= (strpos($_SERVER['SCRIPT_NAME'],"index")) ? "style=\"margin-bottom: -2px;\"" : ""; ?>></a>
		<a href="portfolio.php"><img src="images/tab_portfolio.png" alt="My Portfolio" <?= (strpos($_SERVER['SCRIPT_NAME'],"portfolio")) ? "style=\"margin-bottom: -2px;\"" : ""; ?>></a>
		<a href="projects.php"><img src="images/tab_projects.png" alt="My Projects" <?= (strpos($_SERVER['SCRIPT_NAME'],"projects")) ? "style=\"margin-bottom: -2px;\"" : ""; ?>></a>
		<a href="contact.php"><img src="images/tab_contact.png" alt="Contact Me" <?= (strpos($_SERVER['SCRIPT_NAME'],"contact")) ? "style=\"margin-bottom: -2px;\"" : ""; ?>></a>
	</div>
</div>
