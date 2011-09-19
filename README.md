

To generate literate-programming html, type:

    make

To run the tests against your server (the source assumes your server
is at [http://localhost:8080](http://localhost:8080)):

    ./venv/bin/python sockjs-protocol-0.0.4-incomplete.py -v

You can run specific tests like that:

    ./venv/bin/python sockjs-protocol-0.0.4-incomplete.py Protocol


If you see `pygments.util.ClassNotFound`, take a look [here](https://github.com/fitzgen/pycco/issues/39).
