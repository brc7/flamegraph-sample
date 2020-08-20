# flamegraph-sample
The MacOS sample command is a quick and dirty tool to get stack traces. This turns the output of sample into an input for flamegraph.pl (see Brendan Gregg's flamegraph tool)

Suppose you've captured profiling information on MacOS using sample, like this 

``` sample processName -f samples.txt```

To make a flamegraph, run 

``` python stackcollapse-sample.py samples.txt > samples.folded```

Then run flamegraph (from [here](https://github.com/brendangregg/FlameGraph)) 

``` $ ./flamegraph.pl samples.folded > samples.svg ```

and open the SVG with your web browser.
