SockJS family:

  * [SockJS-client](https://github.com/majek/sockjs-client) JavaScript client library
  * [SockJS-node](https://github.com/majek/sockjs-node) Node.js server
  * [SockJS-protocol](https://github.com/majek/sockjs-protocol) protocol documentation


SockJS-protocol
===============

This project attempts to provide a definition of SockJS protocol. The
documentation is in a form of a Python test suite decorated with some
prose in literate-programming style. You can see current documentation
here:

 * [sockjs-protocol-0.0.4-incomplete.html](http://majek.github.com/sockjs-protocol/sockjs-protocol-0.0.4-incomplete.html)



To generate the html type:

    make

To run the tests against your server (the source assumes your server
is at [http://localhost:8080](http://localhost:8080)):

    ./venv/bin/python sockjs-protocol-0.0.4-incomplete.py -v

You can run specific tests like that:

    ./venv/bin/python sockjs-protocol-0.0.4-incomplete.py Protocol

To run the http-quirks tests:

    ./venv/bin/python http-quirks.py -v


If you see `pygments.util.ClassNotFound`, take a look
[here](https://github.com/fitzgen/pycco/issues/39).
