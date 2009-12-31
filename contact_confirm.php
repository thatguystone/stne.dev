<?php include("includes/main.php"); ?>
<html>
<head>
<?php include("includes/htmlhead.php"); ?>
</head>

<body>
<div class="borders"><div class="topleft"></div><div class="topspan"></div><div class="topright"></div></div>
<div class="outside">
<div class="wrapper">
	<?php include("includes/header.php"); ?>	
	<div class="content">
		<? if ($_GET['error']==0) { ?>
		Thank you for your correspondence. I will get back to you as soon as possible!
		<? } else { ?>
		There was an error sending your message. Please use the back button and try again.
		<? }?>
	</div>
	<?php include("includes/footer.php"); ?>
</div>
</div>
<div class="borders"><div class="bottomleft"></div><div class="bottomspan"></div><div class="bottomright"></div></div>
</body>

</html>
