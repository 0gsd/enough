# The Thym suite's inputs are data, never tests: tiny-tool/tests/test_counting.py is that fixture program's own
# test, read by tests/test_thym_code.py as a file of a folder and never collected or run here.
collect_ignore_glob = ["tiny-tool/*"]
