
all: venv/.ok
	./venv/bin/pycco sockjs-protocol*.py

venv/.ok:
	rm -rf venv
	virtualenv venv
	./venv/bin/pip install pycco
	./venv/bin/pip install unittest2
	-rm distribute-*.tar.gz
	touch venv/.ok

serve: venv/.ok
	@while [ 1 ]; do			\
		make all;			\
		sleep 0.1;			\
		inotifywait -r -q -e modify .;	\
	done

clean:
	rm -rf venv *.pyc
