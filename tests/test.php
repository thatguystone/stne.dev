<?
require('db.class.php');
$db=new db('game');

echo unserialize(serialize($db));
?>
