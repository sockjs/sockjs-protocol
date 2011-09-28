
build: venv/.ok
	./venv/bin/pycco sockjs-protocol*.py

venv/.ok:
	rm -rf venv
	virtualenv venv
	./venv/bin/pip install pycco
	./venv/bin/pip install unittest2
	./venv/bin/pip install -e git+https://github.com/liris/websocket-client.git#egg=websocket
	# My fork is better - fixes bug #7:
	#     https://github.com/Lawouach/WebSocket-for-Python/pull/7
	./venv/bin/pip install git+https://github.com/majek/WebSocket-for-Python.git
	-rm distribute-*.tar.gz || true
	touch venv/.ok

clean:
	rm -rf venv *.pyc

serve: venv/.ok
	@while [ 1 ]; do			\
		make build;			\
		sleep 0.1;			\
		inotifywait -r -q -e modify .;	\
	done

upload: build
	@node -v > /dev/null
	[ -e ../sockjs-protocol-gh-pages ] || 				\
		git clone `git remote -v|tr "[:space:]" "\t"|cut -f 2`	\
			--branch gh-pages ../sockjs-protocol-gh-pages
	(cd ../sockjs-protocol-gh-pages; git pull;)
	cp docs/* ../sockjs-protocol-gh-pages
	(cd ../sockjs-protocol-gh-pages; git add sockjs*html; git commit sockjs*html -m "Content regenerated";)
	(cd ../sockjs-protocol-gh-pages; node generate_index.js > index.html;)
	(cd ../sockjs-protocol-gh-pages; git add index.html; git commit index.html -m "Index regenerated";)
	@echo ' [*] Now run:'
	@echo '(cd ../sockjs-protocol-gh-pages; git push;)'
