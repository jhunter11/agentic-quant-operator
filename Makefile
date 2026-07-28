.PHONY: help menu demo evidence test check clean

help:                ## show this help
	@grep -E '^[a-z-]+:.*?##' $(MAKEFILE_LIST) \
	  | sed 's/:.*##/\t/' | awk -F'\t' '{printf "  make %-10s %s\n", $$1, $$2}'

menu:                ## the interactive menu (start here)
	@python3 explore.py

demo:                ## watch the guardrails refuse six actions
	@python3 -m quantdesk.scenarios

evidence:            ## recompute the gate metrics from the raw ledgers
	@python3 -m quantdesk.score

check:               ## verify the frozen control plane
	@python3 -m quantdesk.integrity --check

test:                ## run the test suite
	@python3 -m unittest discover -s tests -t .

clean:               ## remove runtime state and caches
	@rm -rf runtime __pycache__ */__pycache__ .pytest_cache
