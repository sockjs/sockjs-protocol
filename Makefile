

#### General

BUILD_DIR = .build
SHELL = /bin/bash
VENV_DIR = $(BUILD_DIR)/venv
PIP = $(VENV_DIR)/bin/pip
PYTHON = $(VENV_DIR)/bin/python

all: pycco_deps test_deps build

build: pycco_deps
	pycco sockjs-protocol*.py

clean:
	@rm -rf $(BUILD_DIR)
	@find . -name "*.pyc" -delete


#### Dependencies

venv: $(VENV_DIR)

$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

$(VENV_DIR): $(BUILD_DIR)
	virtualenv $(VENV_DIR) --no-site-packages --distribute

$(BUILD_DIR)/pip.log: $(BUILD_DIR) requirements.txt
	$(PIP) install -Ur requirements.txt | tee $(BUILD_DIR)/pip.log

$(BUILD_DIR)/pip-dev.log: $(BUILD_DIR) requirements_dev.txt
	$(PIP) install -Ur requirements_dev.txt | tee $(BUILD_DIR)/pip-dev.log

pycco_deps: venv $(BUILD_DIR)/pip.log

test_deps: venv $(BUILD_DIR)/pip-dev.log


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
