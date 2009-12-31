<?
/**
 * This function checks that the supplied email address is valid.
 * @param $email - the email address in question
 * @return true/false - if valid email or not
 */
function checkEmail($email) {
	if(preg_match("/^( [a-zA-Z0-9] )+( [a-zA-Z0-9\._-] )*@( [a-zA-Z0-9_-] )+( [a-zA-Z0-9\._-] +)+$/" , $email)) {
		/** Not implemented for Windows, only linux.
			// gets domain name
			list($username,$domain)=split('@',$email);
			// checks for if MX records in the DNS
		
			if(!checkdnsrr($domain, 'MX')) {
				return false;
			}
		
			// attempts a socket connection to mail server
			if(!fsockopen($domain,25,$errno,$errstr,30)) {
				return false;
			}
		*/
		return true;
	}
	
	return false;
}
?>
