<?php
//include("xmlrpc.inc");
//echo $_SERVER['REMOTE_ADDR'];

$f=xmlrpc_encode_request('xname.updateArecord',array(
		"user" => "litith",
		"password" => "",
		"zone" => "astonesplace.com",
		"name" => "astonesplace.com.",
		"oldaddress" => "*",
		"newaddress" => "24.152.155.73"
	)
);

$context = stream_context_create(array("http" => array(
	'method' => "POST",
	'host' => "www.xname.org",
	'header' => "Content-Type: application/x-www-url-encoded\r\nContent-length: " . strlen($f),
	'accept' => "*/*",
	'content' => $f
)));

/*
$file = file_get_contents("http://www.xname.org/xmlrpc.php", false, $context);
//echo "<pre>" . htmlspecialchars($f) . "</pre>";
echo "<pre>" . htmlspecialchars($file) . "</pre>";
$response = xmlrpc_decode($file);
*/

$server = 'www.xname.org';
$path = '/xmlrpc.php';

$sock = fsockopen("ssl://$server", 443, $errno, $errstr, 30);
if (!$sock) die("$errstr ($errno)\n");

fputs($sock, "POST $path HTTP/1.0\r\n");
fputs($sock, "Host: $server\r\n");
fputs($sock, "Content-type: application/x-www-url-encoded\r\n");
fputs($sock, "Content-length: " . strlen($f) . "\r\n");
fputs($sock, "Accept: */*\r\n");
fputs($sock, "\r\n");
fputs($sock, "$f\r\n");
fputs($sock, "\r\n");


# Headers
while ($str = trim(fgets($sock, 4096)))
	echo "$str<br>";

# Body
$body="";
while (!feof($sock))
$body.=fgets($sock, 4096);

echo $body;

/*
$f=new xmlrpcmsg('xname.updateArecord',array(
		"user" => "litith",
		"password" => "",
		"zone" => "astonesplace.com",
		"name" => "astonesplace.com.",
		"oldaddress" => "*",
		"newaddress" => "24.152.155.73"
	));
$c=new xmlrpc_client("/xmlrpc.php", "www.xname.org", 80, 'http');
$r=$c->send($f, 15);


  if (!$r) { die("send failed"); }
  $v=$r->value();
echo $v;
  if (!$r->faultCode()) {
        print "State number ". $HTTP_POST_VARS["stateno"] . " is " .
          $v->scalarval() . "<BR>";
         print "<HR>I got this value back<BR><PRE>" .
          htmlentities($r->serialize()). "</PRE><HR>\n";
  } else {
        print "Fault: ";
        print "Code: " . $r->faultCode() . 
          " Reason '" .$r->faultString()."'<BR>";
  }*/
?>
