#!/usr/bin/env python3
# coding: utf8

import argparse
import hashlib
import sys
from wcmatch import glob

parser = argparse.ArgumentParser(description='Generates a SHA256 hash over multiple files based on a given pattern.')

parser.add_argument('pattern', type=str, 
                    help='A list of glob patterns used for matching the files. Use \'!\' to negate.',)

args = parser.parse_args()

patterns = list(map(str.strip, args.pattern.strip('\'').replace(';', '\n').splitlines()))
excluded = list(map(lambda x: x[1:], filter(lambda x: x.startswith('!'), patterns)))
patterns = list(filter(lambda x: not x.startswith('!'), patterns))
patterns = ['**'] if len(patterns) == 0 else patterns


files = glob.glob(patterns=patterns, exclude=excluded, flags=glob.GLOBSTAR)
if len(files) == 0:
    print("")
    sys.exit(0)

hasher = hashlib.sha256()

for filename in files:
    with open(filename, 'rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            hasher.update(block)

result = hasher.digest()

# GitHub `hashFiles()` returns the hash over the hash of all file contents..
print(hashlib.sha256(result).hexdigest())
