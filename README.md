SockJS family:

  * [SockJS-client](https://github.com/sockjs/sockjs-client) JavaScript client library
  * [SockJS-node](https://github.com/sockjs/sockjs-node) Node.js server
  * [SockJS-erlang](https://github.com/sockjs/sockjs-erlang) Erlang server


SockJS-protocol
===============

This project attempts to provide a definition of SockJS protocol. The
documentation is in a form of a Python test suite decorated with some
prose in literate-programming style. You can see current documentation
here:

 * [sockjs-protocol-0.0.4-incomplete.html](http://sockjs.github.com/sockjs-protocol/sockjs-protocol-0.0.4-incomplete.html)



To generate the html type:

    make

This assumes you have Python package virtualenv. If not,
you can install it via `pip install virtualenv`.

Once you run make, you can also run the tests against
your server (the source assumes your server is at
[http://localhost:8080](http://localhost:8080)):

    ./venv/bin/python sockjs-protocol-0.0.4-incomplete.py -v

You can run specific tests providing test class as an optional argument:

    ./venv/bin/python sockjs-protocol-0.0.4-incomplete.py Protocol

The test class is one of the classes in `sockjs-protocol-0.0.4-incomplete.py` inherited from class `Test` (or `unittest.TestCase` in general).

To run the http-quirks tests:

    ./venv/bin/python http-quirks.py -v


If you see `pygments.util.ClassNotFound`, take a look
[here](https://github.com/fitzgen/pycco/issues/39).
