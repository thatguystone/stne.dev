<?
$test=array("hi","no");

$test2=&$test;
$test3=$test;
$test4=$test2;
$test5=new test(&$test2);

$test2[0]="edited";
$test3[0]="another";

$test5->change();

echo "test&nbsp;&nbsp;: ";
print_r($test);
echo "<br>test2: ";
print_r($test2);
echo "<br>test3: ";
print_r($test3);
echo "<br>test4: ";
print_r($test4);
$test2[0]="after all";
echo "<br>test5: ";
print_r($test5->array);

class test {
	public $array;
	
	function test($array) {
		$this->array=&$array;
		$this->array[1]="from class";
	}
	
	function change() {
		$this->array[1]="function change";
	}
}
?>
