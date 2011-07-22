/**
 * In place Fisher-Yates shuffle.
 *   http://dtm.livejournal.com/38725.html
 *   http://en.wikipedia.org/wiki/Fisher-Yates_shuffle
 */
Array.prototype.shuffle = function() {
  var j, tmp;
  for (var i = 1; i < this.length; i++) {
    j = Math.floor(Math.random() * (1 + i));  // choose j in [0..i]
    if (j != i) {
      tmp = this[i];                        // swap list[i] and list[j]
      this[i] = this[j];
      this[j] = tmp;
    }
  }
  return this;
};
