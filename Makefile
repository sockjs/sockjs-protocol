

#### General

all: pycco_deps test_deps build

build: pycco_deps
	pycco sockjs-protocol*.py

clean:
	rm -rf venv *.pyc


#### Dependencies

venv:
	virtualenv venv --no-site-packages --distribute
	-rm distribute-*.tar.gz || true
	source ./venv/bin/activate

pycco_deps:
	pip install -r requirements_dev.txt

test_deps:
	pip install -r requirements.txt


#### Development

serve: pycco_deps
	@while [ 1 ]; do			\
		make build;			\
		sleep 0.1;			\
		inotifywait -r -q -e modify .;	\
	done


#### Deployment

upload: build
	@node -v > /dev/null
	[ -e ../sockjs-protocol-gh-pages ] || 				\
		git clone `git remote -v|tr "[:space:]" "\t"|cut -f 2`	\
			--branch gh-pages ../sockjs-protocol-gh-pages
	(cd ../sockjs-protocol-gh-pages; git pull;)
	cp docs/* ../sockjs-protocol-gh-pages
	(cd ../sockjs-protocol-gh-pages; git add pycco.css sockjs*html; git commit sockjs*html -m "Content regenerated";)
	(cd ../sockjs-protocol-gh-pages; node generate_index.js > index.html;)
	(cd ../sockjs-protocol-gh-pages; git add index.html; git commit index.html -m "Index regenerated";)
	@echo ' [*] Now run:'
	@echo '(cd ../sockjs-protocol-gh-pages; git push;)'
