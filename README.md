SockJS family:

  * [SockJS-client](https://github.com/sockjs/sockjs-client) JavaScript client library
  * [SockJS-node](https://github.com/sockjs/sockjs-node) Node.js server
  * [SockJS-erlang](https://github.com/sockjs/sockjs-erlang) Erlang server
  * [SockJS-tornado](https://github.com/MrJoes/sockjs-tornado) Python/Tornado server
  * [vert.x](https://github.com/vert-x/vert.x) Java/vert.x server
  * [Xitrum](http://ngocdaothanh.github.io/xitrum/) Scala server

Work in progress:

  * [SockJS-ruby](https://github.com/nyarly/sockjs-ruby)
  * [SockJS-netty](https://github.com/cgbystrom/sockjs-netty)
  * [SockJS-gevent](https://github.com/sdiehl/sockjs-gevent) ([SockJS-gevent fork](https://github.com/njoyce/sockjs-gevent))
  * [pyramid-SockJS](https://github.com/fafhrd91/pyramid_sockjs)
  * [wildcloud-websockets](https://github.com/wildcloud/wildcloud-websockets)
  * [SockJS-cyclone](https://github.com/flaviogrossi/sockjs-cyclone)
  * [SockJS-twisted](https://github.com/Fugiman/sockjs-twisted/)
  * [wai-SockJS](https://github.com/Palmik/wai-sockjs)
  * [SockJS-perl](https://github.com/vti/sockjs-perl)
  * [SockJS-go](https://github.com/igm/sockjs-go/)


SockJS-protocol
===============

This project attempts to provide a definition of SockJS protocol. The
documentation is in a form of a Python test suite decorated with some
prose in literate-programming style. You can see current documentation
here:

 * Current stable: [sockjs-protocol-0.3.3.html](http://sockjs.github.com/sockjs-protocol/sockjs-protocol-0.3.3.html)


Running tests
-------------

You must have Python 2.X and `virtualenv` installed. You can install
it via `pip install virtualenv` or `sudo apt-get install
python-virtualenv`.

To run the test suite against your server, first checkout
dependencies:

    make test_deps

And you're ready to run the tests against your server. By default we
assume that your test server is at
[http://localhost:8081](http://localhost:8081):

    ./venv/bin/python sockjs-protocol-0.3.3.py

You can specify the test server URL manually:

    SOCKJS_URL=http://localhost:1234 ./venv/bin/python sockjs-protocol-0.3.3.py -v

You can run specific tests providing test class as an optional argument:

    ./venv/bin/python sockjs-protocol-0.3.3.py Protocol.test_simpleSession


There is also another test, intended to look for some http quirks:

    ./venv/bin/python http-quirks.py -v


Genrating literate html
-----------------------

If you edited `sockjs-protocol` files, you may want to see how it
looks rendered to html. To generate the html type:

    make build

You should see generated html files in `docs` subdirectory.

If you see `pygments.util.ClassNotFound`, take a look
[here](https://github.com/fitzgen/pycco/issues/39).
