.PHONY: all reload data check

all:            ## regenerate outputs and Figure 1 (uses caches when present)
	python run_all.py

reload:         ## rebuild everything from data/, ignoring caches
	python run_all.py --reload

data:           ## download public inputs and verify all inputs
	python download_data.py

check:          ## assert headline numbers
	python check_results.py
