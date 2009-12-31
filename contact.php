<?php include("includes/main.php"); ?>
<html>
<head>
<?php include("includes/htmlhead.php"); ?>
<script type="text/javascript" language="javascript">
function checkForm() {
	//For holding the alert message of what needs to be filled in
	message="";
	//The Regex for the email filter
	emailfilter=/^([\w-]+(?:\.[\w-]+)*)@((?:[\w-]+\.)*\w[\w-]{0,66})\.([a-z]{2,6}(?:\.[a-z]{2})?)$/i
	
	if (document.frmContact.name.value=="")
		message+="Your Name\n";
	if (document.frmContact.email.value=="" || !emailfilter.test(document.frmContact.email.value))
		message+="A valid E-Mail Address\n";
	if (document.frmContact.body.value=="")
		message+="The message you would like to send\n";
	
	
	if (message!="") {
		alert("Please fill in the following areas:\n"+
		       "_____________________________\n\n"+
		       message);
		
		return false;
	} else {
		return true;
	}
}
</script>
</head>

<body>
<div class="borders"><div class="topleft"></div><div class="topspan"></div><div class="topright"></div></div>
<div class="outside">
<div class="wrapper">
	<?php include("includes/header.php"); ?>	
	<div class="content">
		<form action="contact_now.php" method="post" name="frmContact" onSubmit="return checkForm();">
			<table>
				<tr>
					<td>Your Name:</td>
					<td><input type="text" name="name"></td>
				</tr>
				<tr>
					<td>Your E-Mail Address:</td>
					<td><input type="text" name="email"></td>
				</tr>
				<tr>
					<td colspan="2">Body:</td>
				</tr>
				<tr>
					<td colspan="2"><textarea name="body"></textarea></td>
				</tr>
				<tr>
					<td colspan="2" align="center"><input type="submit" value="Send!"></td>
				</tr>
			</table>
		</form>
	</div>
	<?php include("includes/footer.php"); ?>
</div>
</div>
<div class="borders"><div class="bottomleft"></div><div class="bottomspan"></div><div class="bottomright"></div></div>
</body>

</html>
