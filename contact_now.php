<?php
require_once('class.phpmailer.php');
include("includes/functions.php");

$name=$_POST['name'];
$body=$_POST['body'];
$email=$_POST['email'];
	if (checkEmail($email))
		header("Location: contact_confirm.php?error=1");

$mail = new PHPMailer(); // defaults to using php "mail()"

$mail->From = $email;
$mail->FromName = $name;
$mail->Subject = "Message from " . $name;
$mail->MsgHTML($body);
$mail->AddAddress("andrew@astonesplace.com", "Andrew Stone");

if(!$mail->Send()) {
	header("Location: contact_confirm.php?error=1");
} else {
	header("Location: contact_confirm.php?error=0");
}
?>
